using ICSharpCode.SharpZipLib.Checksum;
using ICSharpCode.SharpZipLib.Zip;

namespace BAAD.MediaArchiveExtractor;

internal static class MediaArchiveEngine
{
    private const int CopyBufferSize = 1024 * 1024;
    private const int FileStreamBufferSize = 64 * 1024;
    private const int ProgressMemberInterval = 64;

    public static async Task<ExtractionResult> ExecuteAsync(
        ExtractionRequest request,
        Action<MediaProgressSnapshot> emitProgress)
    {
        ArchivePlan?[] plans = new ArchivePlan?[request.Archives.Count];
        ArchiveResult[] results = new ArchiveResult[request.Archives.Count];
        long totalMembers = 0;
        int completedArchives = 0;
        int failedArchives = 0;

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
                failedArchives++;
            }
        }

        long completedMembers = 0;
        List<ArchivePlan> executablePlans = plans
            .Where(plan => plan is not null)
            .Select(plan => plan!)
            .ToList();
        int degree = Math.Min(
            Math.Min(request.Concurrency, Environment.ProcessorCount),
            executablePlans.Count);
        int activeWorkers = 0;
        emitProgress(new MediaProgressSnapshot(
            completedArchives,
            request.Archives.Count,
            completedMembers,
            totalMembers,
            activeWorkers,
            degree,
            failedArchives));

        ParallelOptions options = new()
        {
            MaxDegreeOfParallelism = Math.Max(degree, 1),
        };

        await Parallel.ForEachAsync(
            executablePlans,
            options,
            (plan, _) =>
            {
                int active = Interlocked.Increment(ref activeWorkers);
                emitProgress(new MediaProgressSnapshot(
                    Volatile.Read(ref completedArchives),
                    request.Archives.Count,
                    Volatile.Read(ref completedMembers),
                    totalMembers,
                    active,
                    degree,
                    Volatile.Read(ref failedArchives)));
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
                                emitProgress(new MediaProgressSnapshot(
                                    Volatile.Read(ref completedArchives),
                                    request.Archives.Count,
                                    members,
                                    totalMembers,
                                    Volatile.Read(ref activeWorkers),
                                    degree,
                                    Volatile.Read(ref failedArchives)));
                            }
                        });
                }
                catch (Exception exception)
                {
                    DeleteDirectory(plan.StagingPath);
                    results[plan.Index] = ArchiveResult.Failed(
                        plan.Request,
                        DescribeFailure(exception));
                    Interlocked.Increment(ref failedArchives);
                }
                int archives = Interlocked.Increment(ref completedArchives);
                active = Interlocked.Decrement(ref activeWorkers);
                emitProgress(new MediaProgressSnapshot(
                    archives,
                    request.Archives.Count,
                    Volatile.Read(ref completedMembers),
                    totalMembers,
                    active,
                    degree,
                    Volatile.Read(ref failedArchives)));
                return ValueTask.CompletedTask;
            });

        return new ExtractionResult
        {
            SchemaVersion = MediaArchiveProtocol.SchemaVersion,
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
}
