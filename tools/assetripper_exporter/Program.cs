using System.Diagnostics;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using AssetRipper.Assets;
using AssetRipper.Assets.Bundles;
using AssetRipper.Export.Configuration;
using AssetRipper.Export.PrimaryContent;
using AssetRipper.Export.UnityProjects;
using AssetRipper.Import.AssetCreation;
using AssetRipper.Import.Logging;
using AssetRipper.Import.Structure;
using AssetRipper.Import.Structure.Assembly.Managers;
using AssetRipper.IO.Files;
using AssetRipper.IO.Files.CompressedFiles;
using AssetRipper.IO.Files.ResourceFiles;
using AssetRipper.IO.Files.SerializedFiles;
using AssetRipper.Processing;
using AssetRipper.SourceGenerated.Classes.ClassID_28;
using AssetRipper.SourceGenerated.Classes.ClassID_43;
using AssetRipper.SourceGenerated.Classes.ClassID_83;
using AssetRipper.SourceGenerated.Classes.ClassID_117;
using AssetRipper.SourceGenerated.Classes.ClassID_187;
using AssetRipper.SourceGenerated.Classes.ClassID_188;
using AssetRipper.SourceGenerated.Classes.ClassID_189;
using AssetRipper.SourceGenerated.Classes.ClassID_329;
using AssetRipper.SourceGenerated.Classes.ClassID_49;
using AssetRipper.SourceGenerated.Subclasses.StreamedResource;
using AssetRipper.SourceGenerated.Subclasses.StreamingInfo;

if (args.Length != 2)
{
    Console.Error.WriteLine("Usage: AssetRipperExporter <request.json> <result.json>");
    return 2;
}

string requestPath = Path.GetFullPath(args[0]);
string resultPath = Path.GetFullPath(args[1]);
BaadEventLogger eventLogger = new();
Logger.Add(eventLogger);
try
{
    ExportRequest request = JsonSerializer.Deserialize<ExportRequest>(
        File.ReadAllText(requestPath), JsonOptions.Default
    ) ?? throw new InvalidDataException("Exporter request is empty.");
    request.Validate();
    List<string> inputPaths = request.GetInputPaths();
    if (request.Operation == "export_primary_content")
    {
        AssetProvenanceRegistry.Configure(
            request.GetExportInputs().Select(input =>
                new AssetProvenanceInput(input.Path, input.NodeId, input.Target)
            )
        );
    }

    FullConfiguration settings = new();
    ExportHandler handler = new(settings);
    ExportResult result;
    if (request.Operation == "scan_bundle_dependencies")
    {
        eventLogger.Enabled = false;
        result = ScanBundleDependencies(request);
    }
    else
    {
        EventWriter.WritePhase("loading");
        GameData gameData = handler.Load(
            inputPaths,
            LocalFileSystem.Instance,
            new BaadLoadProgress()
        );
        if (request.Operation != "inspect_jp_runtime" && gameData.GameBundle.HasAnyAssetCollections())
        {
            EventWriter.WritePhase("processing");
            ProcessWithHeartbeat(handler, gameData);
        }
        result = request.Operation switch
        {
            "export_primary_content" => ExportPrimaryContent(request, gameData, settings),
            "inspect_jp_runtime" => InspectJpRuntime(gameData),
            _ => throw new InvalidDataException(
                $"Unsupported AssetRipper operation: {request.Operation}"
            ),
        };
    }
    WriteResult(resultPath, result);
    return 0;
}
catch (Exception exception)
{
    EventWriter.WriteLog(
        "error",
        "Exporter",
        $"{exception.GetType().Name}: {exception.Message}"
    );
    WriteResult(
        resultPath,
        new ExportResult(
            false,
            $"{exception.GetType().Name}: {exception.Message}",
            [],
            null,
            null,
            null,
            [],
            [],
            []
        )
    );
    Console.Error.WriteLine(exception);
    return 1;
}
finally
{
    Logger.Remove(eventLogger);
}

static void WriteResult(string resultPath, ExportResult result)
{
    Directory.CreateDirectory(Path.GetDirectoryName(resultPath)!);
    string temporaryPath = resultPath + ".tmp";
    File.WriteAllText(temporaryPath, JsonSerializer.Serialize(result, JsonOptions.Default));
    File.Move(temporaryPath, resultPath, true);
}

static ExportResult ExportPrimaryContent(
    ExportRequest request,
    GameData gameData,
    FullConfiguration settings
)
{
    if (string.IsNullOrWhiteSpace(request.OutputDirectory))
    {
        throw new InvalidDataException("Exporter output directory is required.");
    }
    string outputPath = Path.GetFullPath(request.OutputDirectory);
    Directory.CreateDirectory(outputPath);
    settings.ExportRootPath = outputPath;
    EventWriter.WritePhase("exporting");
    List<string> requestedTargetIds = request.GetExportInputs()
        .Where(input => input.Target)
        .Select(input => input.NodeId)
        .Order(StringComparer.Ordinal)
        .ToList();
    SelectiveExportResult coverage = PrimaryContentExporter.CreateDefault(gameData, settings)
        .ExportSelective(
            gameData.GameBundle,
            settings,
            LocalFileSystem.Instance,
            requestedTargetIds.ToHashSet(StringComparer.Ordinal)
        );
    List<ExportedFile> files = Directory.EnumerateFiles(
            outputPath, "*", SearchOption.AllDirectories
        )
        .Order(StringComparer.Ordinal)
        .Select(path => new ExportedFile(
            Path.GetRelativePath(outputPath, path).Replace('\\', '/'),
            new FileInfo(path).Length
        ))
        .ToList();
    return new ExportResult(
        true,
        null,
        files,
        null,
        null,
        null,
        requestedTargetIds,
        coverage.ResolvedTargetIds.ToList(),
        coverage.ExportedTargetIds.ToList()
    );
}

static ExportResult ScanBundleDependencies(ExportRequest request)
{
    List<string> inputs = request.GetInputPaths();
    if (request.ArchiveIds is null || request.ArchiveIds.Count != inputs.Count)
    {
        throw new InvalidDataException(
            "Dependency scan archive IDs must match input files."
        );
    }
    List<ArchiveScanResult> scans = [];
    for (int index = 0; index < inputs.Count; index++)
    {
        string input = Path.GetFullPath(inputs[index]);
        string archiveId = request.ArchiveIds[index];
        using FileStream inputStream = File.OpenRead(input);
        string sha256 = Convert.ToHexString(
            SHA256.HashData(inputStream)
        ).ToLowerInvariant();
        try
        {
            scans.Add(
                new ArchiveScanResult(
                    archiveId,
                    sha256,
                    ScanArchiveEntries(input),
                    null
                )
            );
        }
        catch (Exception exception)
        {
            scans.Add(
                new ArchiveScanResult(
                    archiveId,
                    sha256,
                    [],
                    $"{exception.GetType().Name}: {exception.Message}"
                )
            );
        }
        EventWriter.WriteScanProgress(index + 1, request.Inputs.Count, archiveId);
    }
    return new ExportResult(true, null, [], null, null, scans);
}

static List<BundleEntryScanResult> ScanArchiveEntries(string input)
{
    List<BundleEntryScanResult> results = [];
    using BaseManager assemblyManager = new(_ => { });
    GameAssetFactory assetFactory = new(assemblyManager);
    if (Path.GetExtension(input).Equals(".zip", StringComparison.OrdinalIgnoreCase))
    {
        using ZipArchive archive = ZipFile.OpenRead(input);
        foreach (ZipArchiveEntry entry in archive.Entries)
        {
            if (string.IsNullOrEmpty(entry.Name))
            {
                continue;
            }
            using Stream entryStream = entry.Open();
            using MemoryStream buffer = new(
                entry.Length is > 0 and <= int.MaxValue ? (int)entry.Length : 0
            );
            entryStream.CopyTo(buffer);
            results.Add(ScanEntry(
                buffer.ToArray(),
                input,
                entry.FullName,
                assetFactory
            ));
        }
    }
    else
    {
        results.Add(ScanEntry(
            File.ReadAllBytes(input),
            input,
            Path.GetFileName(input),
            assetFactory
        ));
    }
    return results.OrderBy(item => item.EntryPath, StringComparer.Ordinal).ToList();
}

static BundleEntryScanResult ScanEntry(
    byte[] buffer,
    string filePath,
    string entryPath,
    GameAssetFactory assetFactory
)
{
    string sha256 = Convert.ToHexString(SHA256.HashData(buffer)).ToLowerInvariant();
    List<SerializedFileScanResult> serializedFiles = [];
    HashSet<string> resourceFiles = new(StringComparer.Ordinal);
    List<StreamedResourceScanResult> streamedResources = [];
    string? error = null;
    try
    {
        ScanMetadataBuffer(
            buffer,
            filePath,
            entryPath,
            assetFactory,
            serializedFiles,
            resourceFiles,
            streamedResources
        );
    }
    catch (Exception exception)
    {
        error = $"{exception.GetType().Name}: {exception.Message}";
    }
    serializedFiles.Sort((left, right) =>
        StringComparer.Ordinal.Compare(left.LogicalName, right.LogicalName)
    );
    return new BundleEntryScanResult(
        entryPath,
        sha256,
        buffer.LongLength,
        serializedFiles,
        resourceFiles.Order(StringComparer.Ordinal).ToList(),
        streamedResources
            .Distinct()
            .OrderBy(item => item.SourceSerializedFile, StringComparer.Ordinal)
            .ThenBy(item => item.ResourcePath, StringComparer.Ordinal)
            .ThenBy(item => item.AssetType, StringComparer.Ordinal)
            .ToList(),
        error
    );
}

static void ScanMetadataBuffer(
    byte[] buffer,
    string filePath,
    string fileName,
    GameAssetFactory assetFactory,
    List<SerializedFileScanResult> serializedFiles,
    HashSet<string> resourceFiles,
    List<StreamedResourceScanResult> streamedResources
)
{
    FileBase? loadedFile = SchemeReader.ReadFile(buffer, filePath, fileName);
    if (loadedFile is null)
    {
        throw new InvalidDataException($"AssetRipper could not read '{fileName}'.");
    }
    FileBase file = loadedFile;
    try
    {
        file.ReadContentsRecursively();
        foreach (SerializedFile serializedFile in FetchSerializedFiles(file))
        {
            serializedFiles.Add(
                new SerializedFileScanResult(
                    serializedFile.NameFixed,
                    serializedFile.Dependencies
                        .ToArray()
                        .Select(item => item.GetFilePath())
                        .Distinct(StringComparer.Ordinal)
                        .Order(StringComparer.Ordinal)
                        .ToList()
                )
            );
            using GameBundle gameBundle = new();
            gameBundle.AddCollectionFromSerializedFile(serializedFile, assetFactory);
            ScanStreamedResources(gameBundle, streamedResources);
        }
        foreach (ResourceFile resourceFile in FetchResourceFiles(file))
        {
            resourceFiles.Add(resourceFile.NameFixed);
        }
    }
    finally
    {
        DisposeFileTree(file);
    }
}

static void DisposeFileTree(FileBase file)
{
    if (file is CompressedFile compressed && compressed.UncompressedFile is { } inner)
    {
        DisposeFileTree(inner);
    }
    else if (file is FileContainer container)
    {
        foreach (FileBase child in container.AllFiles)
        {
            DisposeFileTree(child);
        }
    }
    file.Dispose();
}

static IEnumerable<SerializedFile> FetchSerializedFiles(FileBase file) =>
    file switch
    {
        SerializedFile serializedFile => [serializedFile],
        FileContainer container => container.FetchSerializedFiles(),
        CompressedFile compressed when compressed.UncompressedFile is { } inner =>
            FetchSerializedFiles(inner),
        _ => [],
    };

static IEnumerable<ResourceFile> FetchResourceFiles(FileBase file)
{
    switch (file)
    {
        case ResourceFile resourceFile:
            yield return resourceFile;
            break;
        case FileContainer container:
            foreach (ResourceFile item in container.ResourceFiles)
            {
                yield return item;
            }
            foreach (FileContainer child in container.FileLists)
            {
                foreach (ResourceFile item in FetchResourceFiles(child))
                {
                    yield return item;
                }
            }
            break;
        case CompressedFile compressed when compressed.UncompressedFile is { } inner:
            foreach (ResourceFile item in FetchResourceFiles(inner))
            {
                yield return item;
            }
            break;
    }
}

static void ScanStreamedResources(
    GameBundle gameBundle,
    List<StreamedResourceScanResult> result
)
{
    foreach (IUnityObjectBase asset in gameBundle.FetchAssets())
    {
        string source = asset.Collection.Name;
        switch (asset)
        {
            case ITexture2D texture:
                AddStreamingInfo(result, source, texture.StreamData_C28, "Texture2D");
                break;
            case IMesh mesh:
                AddStreamingInfo(result, source, mesh.StreamData, "Mesh");
                break;
            case IAudioClip audio:
                AddStreamedResource(result, source, audio.Resource, "AudioClip");
                break;
            case ITexture3D texture:
                AddStreamingInfo(result, source, texture.StreamData, "Texture3D");
                break;
            case ITexture2DArray texture:
                AddStreamingInfo(result, source, texture.StreamData, "Texture2DArray");
                break;
            case ICubemapArray texture:
                AddStreamingInfo(result, source, texture.StreamData, "CubemapArray");
                break;
            case IImageTexture texture:
                AddStreamingInfo(result, source, texture.StreamData_C189, "ImageTexture");
                break;
            case IVideoClip video:
                AddStreamedResource(result, source, video.ExternalResources, "VideoClip");
                break;
        }
    }
}

static void AddStreamingInfo(
    List<StreamedResourceScanResult> result,
    string source,
    IStreamingInfo? info,
    string assetType
)
{
    string? path = info?.Path?.String;
    if (!string.IsNullOrEmpty(path))
    {
        result.Add(new StreamedResourceScanResult(source, path, assetType));
    }
}

static void AddStreamedResource(
    List<StreamedResourceScanResult> result,
    string source,
    IStreamedResource? resource,
    string assetType
)
{
    string? path = resource?.Source?.String;
    if (!string.IsNullOrEmpty(path))
    {
        result.Add(
            new StreamedResourceScanResult(source, path, assetType)
        );
    }
}

static void ProcessWithHeartbeat(ExportHandler handler, GameData gameData)
{
    using CancellationTokenSource cancellation = new();
    Stopwatch stopwatch = Stopwatch.StartNew();
    Task heartbeat = Task.Run(async () =>
    {
        try
        {
            while (true)
            {
                await Task.Delay(TimeSpan.FromSeconds(1), cancellation.Token);
                EventWriter.WriteHeartbeat("processing", stopwatch.Elapsed.TotalSeconds);
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
        }
    });

    try
    {
        handler.Process(gameData);
    }
    finally
    {
        cancellation.Cancel();
        heartbeat.GetAwaiter().GetResult();
    }
}

static ExportResult InspectJpRuntime(GameData gameData)
{
    ITextAsset? config = null;
    TypeTreeObject? playerSettings = null;
    foreach (IUnityObjectBase asset in gameData.GameBundle.FetchAssets())
    {
        if (config is null && asset is ITextAsset textAsset && textAsset.GetBestName() == "GameMainConfig")
        {
            config = textAsset;
        }
        if (playerSettings is null && asset is TypeTreeObject typeTree && typeTree.IsPlayerSettings)
        {
            playerSettings = typeTree;
        }
        if (config is not null && playerSettings is not null)
        {
            break;
        }
    }
    if (config is null)
    {
        throw new InvalidDataException("GameMainConfig TextAsset was not found.");
    }
    string? bundleVersion = null;
    if (playerSettings is not null)
    {
        var fields = playerSettings.ReleaseFields;
        if (fields.ContainsField("bundleVersion"))
        {
            bundleVersion = fields["bundleVersion"].AsString;
        }
    }
    return new ExportResult(
        true,
        null,
        [],
        Convert.ToBase64String(config.Script_C49.Data),
        bundleVersion
    );
}

internal sealed record ExportInput(string Path, string NodeId, bool Target);

internal sealed record ExportRequest(
    string Operation,
    List<JsonElement> Inputs,
    string? OutputDirectory,
    List<string>? ArchiveIds
)
{
    public void Validate()
    {
        if (Inputs.Count == 0)
        {
            throw new InvalidDataException("Exporter request must contain input files.");
        }
        if (string.IsNullOrWhiteSpace(Operation))
        {
            throw new InvalidDataException("Exporter operation is required.");
        }
        _ = GetInputPaths();
        if (Operation == "export_primary_content")
        {
            List<ExportInput> exportInputs = GetExportInputs();
            if (exportInputs.Select(input => input.NodeId).Distinct(StringComparer.Ordinal).Count() != exportInputs.Count)
            {
                throw new InvalidDataException("Exporter input node IDs must be unique.");
            }
        }
    }

    public List<string> GetInputPaths()
    {
        return Inputs.Select(input => input.ValueKind switch
        {
            JsonValueKind.String => input.GetString(),
            JsonValueKind.Object when input.TryGetProperty("path", out JsonElement path) => path.GetString(),
            _ => null,
        })
        .Select(path => string.IsNullOrWhiteSpace(path)
            ? throw new InvalidDataException("Exporter input path is invalid.")
            : Path.GetFullPath(path))
        .ToList();
    }

    public List<ExportInput> GetExportInputs()
    {
        List<ExportInput> result = [];
        foreach (JsonElement input in Inputs)
        {
            if (input.ValueKind != JsonValueKind.Object)
            {
                throw new InvalidDataException("Selective export inputs must be objects.");
            }
            ExportInput? parsed = input.Deserialize<ExportInput>(JsonOptions.Default);
            if (parsed is null || string.IsNullOrWhiteSpace(parsed.Path) || string.IsNullOrWhiteSpace(parsed.NodeId))
            {
                throw new InvalidDataException("Selective export input is invalid.");
            }
            result.Add(parsed with { Path = Path.GetFullPath(parsed.Path) });
        }
        return result;
    }
}

internal sealed record ExportedFile(string Path, long Size);
internal sealed record ExportResult(
    bool Succeeded,
    string? Error,
    List<ExportedFile> Files,
    string? GameMainConfigBase64,
    string? BundleVersion,
    List<ArchiveScanResult>? Scans = null,
    List<string>? RequestedTargetIds = null,
    List<string>? ResolvedTargetIds = null,
    List<string>? ExportedTargetIds = null
);
internal sealed record SerializedFileScanResult(
    string LogicalName,
    List<string> Dependencies
);
internal sealed record StreamedResourceScanResult(
    string SourceSerializedFile,
    string ResourcePath,
    string AssetType
);
internal sealed record ArchiveScanResult(
    string ArchiveId,
    string Sha256,
    List<BundleEntryScanResult> Entries,
    string? Error
);
internal sealed record BundleEntryScanResult(
    string EntryPath,
    string Sha256,
    long Size,
    List<SerializedFileScanResult> SerializedFiles,
    List<string> ResourceFiles,
    List<StreamedResourceScanResult> StreamedResources,
    string? Error
);

internal sealed class BaadEventLogger : ILogger
{
    private static readonly Regex ExportProgressPattern = new(
        @"^\((\d+)/(\d+)\) Exporting ",
        RegexOptions.CultureInvariant
    );

    public bool Enabled { get; set; } = true;

    public void BlankLine(int numLines) { }

    public void Log(LogType type, LogCategory category, string message)
    {
        if (!Enabled)
        {
            return;
        }
        if (type == LogType.Info && category == LogCategory.ExportProgress)
        {
            Match match = ExportProgressPattern.Match(message);
            if (
                match.Success
                && int.TryParse(match.Groups[1].Value, out int current)
                && int.TryParse(match.Groups[2].Value, out int total)
            )
            {
                EventWriter.WriteProgress(current, total);
            }
            return;
        }

        if (type == LogType.Warning || type == LogType.Error)
        {
            EventWriter.WriteLog(
                type == LogType.Warning ? "warning" : "error",
                category.ToString(),
                message
            );
        }
    }
}

internal sealed class BaadLoadProgress : IGameLoadProgress
{
    public void Report(GameLoadProgress progress) =>
        EventWriter.WriteLoadingProgress(
            progress.Stage switch
            {
                GameLoadProgressStage.ExtractingInputs => "extracting_inputs",
                GameLoadProgressStage.LoadingFiles => "loading_files",
                GameLoadProgressStage.CreatingCollections => "creating_collections",
                GameLoadProgressStage.ResolvingDependencies => "resolving_dependencies",
                _ => throw new ArgumentOutOfRangeException(),
            },
            progress.Current,
            progress.Total
        );
}

internal static class EventWriter
{
    private const string Prefix = "BAAD_ASSETRIPPER_EVENT ";
    private const int Version = 4;
    private static readonly object SyncRoot = new();

    public static void WritePhase(string phase) =>
        Write(new { version = Version, kind = "phase", phase });

    public static void WriteProgress(int current, int total) =>
        Write(new
        {
            version = Version,
            kind = "progress",
            phase = "exporting",
            stage = "exporting_assets",
            current,
            total,
        });

    public static void WriteHeartbeat(string phase, double elapsedSeconds) =>
        Write(new
        {
            version = Version,
            kind = "heartbeat",
            phase,
            elapsed_seconds = Math.Round(elapsedSeconds, 1),
        });

    public static void WriteLoadingProgress(string stage, int current, int total) =>
        Write(new
        {
            version = Version,
            kind = "progress",
            phase = "loading",
            stage,
            current,
            total,
        });

    public static void WriteScanProgress(int current, int total, string archiveId) =>
        Write(new
        {
            version = Version,
            kind = "scan_progress",
            current,
            total,
            archive_id = archiveId,
        });

    public static void WriteLog(string level, string category, string message) =>
        Write(new { version = Version, kind = "log", level, category, message });

    private static void Write(object payload)
    {
        lock (SyncRoot)
        {
            Console.Out.WriteLine(Prefix + JsonSerializer.Serialize(payload));
            Console.Out.Flush();
        }
    }
}

internal static class JsonOptions
{
    public static readonly JsonSerializerOptions Default = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
    };
}
