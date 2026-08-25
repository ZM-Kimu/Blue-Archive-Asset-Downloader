using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace BAAD.MediaArchiveExtractor;

internal static class MediaArchiveProtocol
{
    internal const int SchemaVersion = 0;
    private const int FileStreamBufferSize = 64 * 1024;
    private static readonly object ProgressLock = new();

    public static async Task<ExtractionRequest> ReadRequestAsync(string path)
    {
        await using FileStream stream = new(
            Path.GetFullPath(path),
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            FileStreamBufferSize,
            FileOptions.SequentialScan);
        ExtractionRequest? request =
            await JsonSerializer.DeserializeAsync<ExtractionRequest>(stream);
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

    public static void EmitProgress(MediaProgressSnapshot snapshot)
    {
        ProgressEvent progress = new()
        {
            SchemaVersion = SchemaVersion,
            Kind = "progress",
            CompletedArchives = snapshot.CompletedArchives,
            TotalArchives = snapshot.TotalArchives,
            CompletedMembers = snapshot.CompletedMembers,
            TotalMembers = snapshot.TotalMembers,
            ActiveWorkers = snapshot.ActiveWorkers,
            WorkerLimit = snapshot.WorkerLimit,
            FailedArchives = snapshot.FailedArchives,
        };
        lock (ProgressLock)
        {
            Console.Out.WriteLine(JsonSerializer.Serialize(progress));
            Console.Out.Flush();
        }
    }

    public static async Task WriteResultAtomicAsync(
        string path,
        ExtractionResult result)
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

    private static bool IsSimpleOutputName(string value)
    {
        return !string.IsNullOrWhiteSpace(value) && value is not "." and not ".." &&
            value.IndexOfAny(
                new[] { '/', '\\', Path.DirectorySeparatorChar,
                    Path.AltDirectorySeparatorChar }) < 0;
    }

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

        [JsonPropertyName("active_workers")]
        public int ActiveWorkers { get; set; }

        [JsonPropertyName("worker_limit")]
        public int WorkerLimit { get; set; }

        [JsonPropertyName("failed_archives")]
        public int FailedArchives { get; set; }
    }
}

internal readonly record struct MediaProgressSnapshot(
    int CompletedArchives,
    int TotalArchives,
    long CompletedMembers,
    long TotalMembers,
    int ActiveWorkers,
    int WorkerLimit,
    int FailedArchives);

internal sealed class ExtractionRequest
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

internal sealed class ArchiveRequest
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

internal sealed class ExtractionResult
{
    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; set; }

    [JsonPropertyName("succeeded")]
    public bool Succeeded { get; set; }

    [JsonPropertyName("archives")]
    public List<ArchiveResult> Archives { get; set; } = new();
}

internal sealed class ArchiveResult
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
