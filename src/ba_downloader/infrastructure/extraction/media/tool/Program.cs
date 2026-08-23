using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using ICSharpCode.SharpZipLib.Checksum;
using ICSharpCode.SharpZipLib.Zip;

namespace BAAD.MediaArchiveExtractor;

internal static class Program
{
    private const int SchemaVersion = 1;
    private const int CopyBufferSize = 1024 * 1024;
    private const int FileStreamBufferSize = 64 * 1024;
    private const int ProgressMemberInterval = 64;
    private static readonly object ProgressLock = new();

    public static async Task<int> Main(string[] args)
    {
        if (args.Length != 2)
        {
            Console.Error.WriteLine(
                "Usage: MediaArchiveExtractor <request.json> <result.json>");
            return 2;
        }

        try
        {
            Request request = await ReadRequestAsync(args[0]);
            Result result = await ExecuteAsync(request);
            await WriteResultAtomicAsync(args[1], result);
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(
                $"Media archive extractor failed: {exception.GetType().Name}: " +
                exception.Message);
            return 1;
        }
    }

    private static async Task<Request> ReadRequestAsync(string path)
    {
        await using FileStream stream = new(
            Path.GetFullPath(path),
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            FileStreamBufferSize,
            FileOptions.SequentialScan);
        Request? request = await JsonSerializer.DeserializeAsync<Request>(stream);
        if (request is null || request.SchemaVersion != SchemaVersion)
        {
            throw new InvalidDataException("The request schema is invalid.");
        }
        if (request.Concurrency < 1 || request.Archives.Count == 0)
        {
            throw new InvalidDataException("The request has no usable work.");
        }

        request.StagingRoot = Path.GetFullPath(request.StagingRoot);
        Directory.CreateDirectory(request.StagingRoot);
        HashSet<string> outputNames = new(StringComparer.OrdinalIgnoreCase);
        foreach (ArchiveRequest archive in request.Archives)
        {
            archive.ArchivePath = Path.GetFullPath(archive.ArchivePath);
            if (!File.Exists(archive.ArchivePath))
            {
                throw new FileNotFoundException(
                    "A requested media archive does not exist.",
                    archive.ArchivePath);
            }
            if (!IsSimpleOutputName(archive.OutputName) ||
                !outputNames.Add(archive.OutputName))
            {
                throw new InvalidDataException(
                    "Media archive output names must be unique simple names.");
            }
            byte[] passwordBytes;
            try
            {
                passwordBytes = Convert.FromBase64String(archive.PasswordBase64);
            }
            catch (FormatException exception)
            {
                throw new InvalidDataException(
                    "A media archive password is not valid base64.", exception);
            }
            if (passwordBytes.Any(value => value > 0x7f))
            {
                throw new InvalidDataException(
                    "Media archive passwords must use ASCII bytes.");
            }
            archive.Password = Encoding.ASCII.GetString(passwordBytes);
        }
        return request;
    }

    private static async Task<Result> ExecuteAsync(Request request)
    {
        ArchivePlan?[] plans = new ArchivePlan?[request.Archives.Count];
        ArchiveResult[] results = new ArchiveResult[request.Archives.Count];
        long totalMembers = 0;
        int completedArchives = 0;

        for (int index = 0; index < request.Archives.Count; index++)
        {
            ArchiveRequest archive = request.Archives[index];
            try
            {
                ArchivePlan plan = ScanArchive(index, archive, request.StagingRoot);
                plans[index] = plan;
                totalMembers = checked(totalMembers + plan.Entries.Count);
            }
            catch (Exception exception)
            {
                results[index] = ArchiveResult.Failed(
                    archive,
                    DescribeFailure(exception));
                completedArchives++;
            }
        }

        long completedMembers = 0;
        EmitProgress(
            completedArchives,
            request.Archives.Count,
            completedMembers,
            totalMembers);

        int degree = Math.Min(
            Math.Min(request.Concurrency, Environment.ProcessorCount),
            request.Archives.Count);
        ParallelOptions options = new()
        {
            MaxDegreeOfParallelism = Math.Max(degree, 1),
        };

        await Parallel.ForEachAsync(
            plans.Where(plan => plan is not null).Select(plan => plan!),
            options,
            (plan, _) =>
            {
                try
                {
                    results[plan.Index] = ExtractArchive(
                        plan,
                        () =>
                        {
                            long members = Interlocked.Increment(
                                ref completedMembers);
                            if (members % ProgressMemberInterval == 0 ||
                                members == totalMembers)
                            {
                                EmitProgress(
                                    Volatile.Read(ref completedArchives),
                                    request.Archives.Count,
                                    members,
                                    totalMembers);
                            }
                        });
                }
                catch (Exception exception)
                {
                    DeleteDirectory(plan.StagingPath);
                    results[plan.Index] = ArchiveResult.Failed(
                        plan.Request,
                        DescribeFailure(exception));
                }
                int archives = Interlocked.Increment(ref completedArchives);
                EmitProgress(
                    archives,
                    request.Archives.Count,
                    Volatile.Read(ref completedMembers),
                    totalMembers);
                return ValueTask.CompletedTask;
            });

        return new Result
        {
            SchemaVersion = SchemaVersion,
            Succeeded = true,
            Archives = results.ToList(),
        };
    }

    private static ArchivePlan ScanArchive(
        int index,
        ArchiveRequest request,
        string stagingRoot)
    {
        FileInfo identity = new(request.ArchivePath);
        List<EntryPlan> entries = new();
        HashSet<string> targets = new(StringComparer.OrdinalIgnoreCase);
        HashSet<string> fileTargets = new(StringComparer.OrdinalIgnoreCase);
        long declaredBytes = 0;

        using FileStream archiveStream = OpenArchive(request.ArchivePath);
        using ZipFile archive = new(archiveStream);
        foreach (ZipEntry entry in archive)
        {
            ValidateEntryType(entry);
            string relativePath = NormalizeEntryPath(entry.Name, entry.IsDirectory);
            if (!targets.Add(relativePath))
            {
                throw new InvalidDataException(
                    $"Archive contains duplicate target '{relativePath}'.");
            }
            if (entry.Size < 0 || entry.CompressedSize < 0 || entry.Crc < 0)
            {
                throw new InvalidDataException(
                    $"Archive entry '{relativePath}' has invalid metadata.");
            }
            if (entry.IsDirectory && entry.Size != 0)
            {
                throw new InvalidDataException(
                    $"Archive directory '{relativePath}' declares file data.");
            }
            if (!entry.IsDirectory)
            {
                declaredBytes = checked(declaredBytes + entry.Size);
                fileTargets.Add(relativePath);
            }
            entries.Add(
                new EntryPlan(
                    relativePath,
                    entry.IsDirectory,
                    entry.Size,
                    entry.CompressedSize,
                    checked((uint)entry.Crc)));
        }

        foreach (string fileTarget in fileTargets)
        {
            string? parent = GetParent(fileTarget);
            while (parent is not null)
            {
                if (fileTargets.Contains(parent))
                {
                    throw new InvalidDataException(
                        $"Archive file '{parent}' is also used as a directory.");
                }
                parent = GetParent(parent);
            }
        }

        string stagingPath = Path.Combine(
            stagingRoot,
            $"archive-{index:D6}");
        EnsureContainedPath(stagingRoot, stagingPath);
        return new ArchivePlan(
            index,
            request,
            stagingPath,
            identity.Length,
            identity.LastWriteTimeUtc.Ticks,
            declaredBytes,
            entries);
    }

    private static ArchiveResult ExtractArchive(
        ArchivePlan plan,
        Action memberCompleted)
    {
        FileInfo identity = new(plan.Request.ArchivePath);
        if (identity.Length != plan.ArchiveLength ||
            identity.LastWriteTimeUtc.Ticks != plan.ArchiveWriteTicks)
        {
            throw new IOException("Archive changed after its central directory scan.");
        }

        Directory.CreateDirectory(plan.StagingPath);
        long outputBytes = 0;
        int memberCount = 0;
        byte[] copyBuffer = new byte[CopyBufferSize];
        using FileStream archiveStream = OpenArchive(plan.Request.ArchivePath);
        using ZipFile archive = new(archiveStream)
        {
            Password = plan.Request.Password,
        };
        if (archive.Count != plan.Entries.Count)
        {
            throw new InvalidDataException(
                "Archive member count changed after its central directory scan.");
        }

        for (int index = 0; index < archive.Count; index++)
        {
            ZipEntry entry = archive[index];
            EntryPlan expected = plan.Entries[index];
            string relativePath = NormalizeEntryPath(entry.Name, entry.IsDirectory);
            if (relativePath != expected.RelativePath ||
                entry.IsDirectory != expected.IsDirectory ||
                entry.Size != expected.Size ||
                entry.CompressedSize != expected.CompressedSize ||
                checked((uint)entry.Crc) != expected.Crc)
            {
                throw new InvalidDataException(
                    "Archive metadata changed after its central directory scan.");
            }

            string targetPath = Path.Combine(
                plan.StagingPath,
                relativePath.Replace('/', Path.DirectorySeparatorChar));
            EnsureContainedPath(plan.StagingPath, targetPath);
            if (entry.IsDirectory)
            {
                Directory.CreateDirectory(targetPath);
            }
            else
            {
                string? parent = Path.GetDirectoryName(targetPath);
                if (parent is not null)
                {
                    Directory.CreateDirectory(parent);
                }
                long written = ExtractEntry(
                    archive,
                    entry,
                    targetPath,
                    copyBuffer);
                outputBytes = checked(outputBytes + written);
            }
            memberCount++;
            memberCompleted();
        }

        if (outputBytes != plan.DeclaredBytes)
        {
            throw new InvalidDataException(
                "Archive output size does not match its declared size.");
        }
        return ArchiveResult.Success(
            plan.Request,
            plan.StagingPath,
            memberCount,
            outputBytes);
    }

    private static long ExtractEntry(
        ZipFile archive,
        ZipEntry entry,
        string targetPath,
        byte[] buffer)
    {
        Crc32 crc = new();
        long written = 0;
        using Stream input = archive.GetInputStream(entry);
        using FileStream output = new(
            targetPath,
            FileMode.CreateNew,
            FileAccess.Write,
            FileShare.None,
            FileStreamBufferSize,
            FileOptions.SequentialScan);
        while (true)
        {
            int count = input.Read(buffer, 0, buffer.Length);
            if (count == 0)
            {
                break;
            }
            output.Write(buffer, 0, count);
            crc.Update(new ArraySegment<byte>(buffer, 0, count));
            written = checked(written + count);
            if (written > entry.Size)
            {
                throw new InvalidDataException(
                    $"Archive entry '{entry.Name}' exceeds its declared size.");
            }
        }
        if (written != entry.Size || checked((uint)crc.Value) != checked((uint)entry.Crc))
        {
            throw new InvalidDataException(
                $"Archive entry '{entry.Name}' failed size or CRC validation.");
        }
        return written;
    }

    private static FileStream OpenArchive(string path)
    {
        return new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            FileStreamBufferSize,
            FileOptions.SequentialScan);
    }

    private static string NormalizeEntryPath(string rawName, bool isDirectory)
    {
        if (string.IsNullOrWhiteSpace(rawName) || rawName.IndexOf('\0') >= 0)
        {
            throw new InvalidDataException("Archive contains an invalid entry name.");
        }
        string normalized = rawName.Replace('\\', '/');
        if (normalized.StartsWith('/') || normalized.StartsWith("//") ||
            Path.IsPathRooted(rawName) || HasDrivePrefix(normalized))
        {
            throw new InvalidDataException(
                $"Archive entry '{rawName}' uses an absolute path.");
        }
        normalized = normalized.TrimEnd('/');
        string[] parts = normalized.Split('/');
        if (parts.Length == 0 || parts.Any(
            part => !IsSafePathSegment(part)))
        {
            throw new InvalidDataException(
                $"Archive entry '{rawName}' uses an unsafe path.");
        }
        if (isDirectory && !rawName.EndsWith('/') && !rawName.EndsWith('\\'))
        {
            throw new InvalidDataException(
                $"Archive directory '{rawName}' has an inconsistent name.");
        }
        return string.Join('/', parts);
    }

    private static void ValidateEntryType(ZipEntry entry)
    {
        int unixType = (entry.ExternalFileAttributes >> 16) & 0xf000;
        const int UnixRegularFile = 0x8000;
        const int UnixDirectory = 0x4000;
        if (unixType != 0 && unixType != UnixRegularFile && unixType != UnixDirectory)
        {
            throw new InvalidDataException(
                $"Archive entry '{entry.Name}' is not a regular file or directory.");
        }
        if ((unixType == UnixDirectory) != entry.IsDirectory && unixType != 0)
        {
            throw new InvalidDataException(
                $"Archive entry '{entry.Name}' has inconsistent type metadata.");
        }
    }

    private static bool HasDrivePrefix(string path)
    {
        return path.Length >= 2 && char.IsAsciiLetter(path[0]) && path[1] == ':';
    }

    private static bool IsSafePathSegment(string value)
    {
        if (string.IsNullOrEmpty(value) || value is "." or ".." ||
            value.EndsWith('.') || value.EndsWith(' ') ||
            value.Any(character => character < 0x20 || "<>:\"|?*".Contains(character)))
        {
            return false;
        }
        string deviceName = value.Split('.')[0];
        if (deviceName.Equals("CON", StringComparison.OrdinalIgnoreCase) ||
            deviceName.Equals("PRN", StringComparison.OrdinalIgnoreCase) ||
            deviceName.Equals("AUX", StringComparison.OrdinalIgnoreCase) ||
            deviceName.Equals("NUL", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }
        if (deviceName.Length == 4 &&
            (deviceName.StartsWith("COM", StringComparison.OrdinalIgnoreCase) ||
             deviceName.StartsWith("LPT", StringComparison.OrdinalIgnoreCase)) &&
            deviceName[3] is >= '1' and <= '9')
        {
            return false;
        }
        return true;
    }

    private static bool IsSimpleOutputName(string value)
    {
        return !string.IsNullOrWhiteSpace(value) && value is not "." and not ".." &&
            value.IndexOfAny(
                new[] { '/', '\\', Path.DirectorySeparatorChar,
                    Path.AltDirectorySeparatorChar }) < 0;
    }

    private static string? GetParent(string relativePath)
    {
        int separator = relativePath.LastIndexOf('/');
        return separator > 0 ? relativePath[..separator] : null;
    }

    private static void EnsureContainedPath(string root, string candidate)
    {
        string normalizedRoot = Path.GetFullPath(root)
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) +
            Path.DirectorySeparatorChar;
        string normalizedCandidate = Path.GetFullPath(candidate);
        StringComparison comparison = OperatingSystem.IsWindows()
            ? StringComparison.OrdinalIgnoreCase
            : StringComparison.Ordinal;
        if (!normalizedCandidate.StartsWith(normalizedRoot, comparison))
        {
            throw new InvalidDataException(
                "Archive target escapes the staging directory.");
        }
    }

    private static string DescribeFailure(Exception exception)
    {
        return $"{exception.GetType().Name}: {exception.Message}";
    }

    private static void DeleteDirectory(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
        }
        catch
        {
            // The Python owner removes the complete job root after the process exits.
        }
    }

    private static void EmitProgress(
        int completedArchives,
        int totalArchives,
        long completedMembers,
        long totalMembers)
    {
        ProgressEvent progress = new()
        {
            SchemaVersion = SchemaVersion,
            Kind = "progress",
            CompletedArchives = completedArchives,
            TotalArchives = totalArchives,
            CompletedMembers = completedMembers,
            TotalMembers = totalMembers,
        };
        lock (ProgressLock)
        {
            Console.Out.WriteLine(JsonSerializer.Serialize(progress));
            Console.Out.Flush();
        }
    }

    private static async Task WriteResultAtomicAsync(string path, Result result)
    {
        string target = Path.GetFullPath(path);
        string? parent = Path.GetDirectoryName(target);
        if (parent is null)
        {
            throw new InvalidDataException("Result path has no parent directory.");
        }
        Directory.CreateDirectory(parent);
        string temporary = Path.Combine(
            parent,
            $".{Path.GetFileName(target)}.{Guid.NewGuid():N}.tmp");
        try
        {
            await using (FileStream stream = new(
                temporary,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.None,
                FileStreamBufferSize,
                FileOptions.SequentialScan))
            {
                await JsonSerializer.SerializeAsync(stream, result);
                await stream.FlushAsync();
                stream.Flush(flushToDisk: true);
            }
            File.Move(temporary, target, overwrite: true);
        }
        finally
        {
            File.Delete(temporary);
        }
    }

    private sealed class Request
    {
        [JsonPropertyName("schema_version")]
        public int SchemaVersion { get; set; }

        [JsonPropertyName("concurrency")]
        public int Concurrency { get; set; }

        [JsonPropertyName("staging_root")]
        public string StagingRoot { get; set; } = string.Empty;

        [JsonPropertyName("archives")]
        public List<ArchiveRequest> Archives { get; set; } = new();
    }

    private sealed class ArchiveRequest
    {
        [JsonPropertyName("archive_path")]
        public string ArchivePath { get; set; } = string.Empty;

        [JsonPropertyName("output_name")]
        public string OutputName { get; set; } = string.Empty;

        [JsonPropertyName("password_base64")]
        public string PasswordBase64 { get; set; } = string.Empty;

        [JsonIgnore]
        public string Password { get; set; } = string.Empty;
    }

    private sealed class Result
    {
        [JsonPropertyName("schema_version")]
        public int SchemaVersion { get; set; }

        [JsonPropertyName("succeeded")]
        public bool Succeeded { get; set; }

        [JsonPropertyName("archives")]
        public List<ArchiveResult> Archives { get; set; } = new();
    }

    private sealed class ArchiveResult
    {
        [JsonPropertyName("archive_path")]
        public string ArchivePath { get; set; } = string.Empty;

        [JsonPropertyName("output_name")]
        public string OutputName { get; set; } = string.Empty;

        [JsonPropertyName("staging_path")]
        public string? StagingPath { get; set; }

        [JsonPropertyName("succeeded")]
        public bool Succeeded { get; set; }

        [JsonPropertyName("error")]
        public string? Error { get; set; }

        [JsonPropertyName("member_count")]
        public int MemberCount { get; set; }

        [JsonPropertyName("output_bytes")]
        public long OutputBytes { get; set; }

        public static ArchiveResult Success(
            ArchiveRequest request,
            string stagingPath,
            int memberCount,
            long outputBytes)
        {
            return new ArchiveResult
            {
                ArchivePath = request.ArchivePath,
                OutputName = request.OutputName,
                StagingPath = stagingPath,
                Succeeded = true,
                MemberCount = memberCount,
                OutputBytes = outputBytes,
            };
        }

        public static ArchiveResult Failed(ArchiveRequest request, string error)
        {
            return new ArchiveResult
            {
                ArchivePath = request.ArchivePath,
                OutputName = request.OutputName,
                Succeeded = false,
                Error = error,
            };
        }
    }

    private sealed record ArchivePlan(
        int Index,
        ArchiveRequest Request,
        string StagingPath,
        long ArchiveLength,
        long ArchiveWriteTicks,
        long DeclaredBytes,
        List<EntryPlan> Entries);

    private sealed record EntryPlan(
        string RelativePath,
        bool IsDirectory,
        long Size,
        long CompressedSize,
        uint Crc);

    private sealed class ProgressEvent
    {
        [JsonPropertyName("schema_version")]
        public int SchemaVersion { get; set; }

        [JsonPropertyName("kind")]
        public string Kind { get; set; } = string.Empty;

        [JsonPropertyName("completed_archives")]
        public int CompletedArchives { get; set; }

        [JsonPropertyName("total_archives")]
        public int TotalArchives { get; set; }

        [JsonPropertyName("completed_members")]
        public long CompletedMembers { get; set; }

        [JsonPropertyName("total_members")]
        public long TotalMembers { get; set; }
    }
}
