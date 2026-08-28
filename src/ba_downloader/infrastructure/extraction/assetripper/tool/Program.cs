using System.Collections.Concurrent;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using AssetRipper.Assets;
using AssetRipper.Assets.Bundles;
using AssetRipper.Export.Configuration;
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
using AssetRipper.SourceGenerated.Subclasses.StreamedResource;
using AssetRipper.SourceGenerated.Subclasses.StreamingInfo;
using Baad.AssetRipper;
using Baad.AssetRipper.PrimaryContent;

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
    ExportResult result;
    if (request.Operation == "scan_bundle_dependencies")
    {
        eventLogger.Enabled = false;
        result = ScanBundleDependencies(request);
    }
    else if (request.Operation == "materialize_bundle_entries")
    {
        eventLogger.Enabled = false;
        result = MaterializeBundleEntries(request);
    }
    else if (request.Operation == "export_primary_content")
    {
        result = ExportPrimaryContentGroups(request);
    }
    else
    {
        throw new InvalidDataException(
            $"Unsupported AssetRipper operation: {request.Operation}"
        );
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
            [],
            IsOutOfMemory(exception) ? "out_of_memory" : "export_failure",
            null,
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

static GroupExportResult ExportPrimaryContent(
    IReadOnlyList<ExportInput> exportInputs,
    string outputPath,
    int concurrency,
    GameData gameData,
    FullConfiguration settings,
    IReadOnlyDictionary<string, SelectiveExportAsset> exportedAssets
)
{
    Directory.CreateDirectory(outputPath);
    settings.ExportRootPath = outputPath;
    EventWriter.WritePhase("exporting");
    List<string> requestedTargetIds = exportInputs
        .Where(input => input.Target)
        .Select(input => input.NodeId)
        .Order(StringComparer.Ordinal)
        .ToList();
    SelectiveExportResult coverage = SelectivePrimaryContentExporter.CreateDefault(
        gameData,
        settings
    )
        .ExportSelective(
            gameData.GameBundle,
            settings,
            LocalFileSystem.Instance,
            requestedTargetIds.ToHashSet(StringComparer.Ordinal),
            concurrency,
            exportedAssets,
            (stableId, item, started, current, total) =>
                EventWriter.WriteAssetLifecycle(stableId, item, started, current, total)
        );
    return new GroupExportResult(
        new ExportResult(
            true,
            null,
            [],
            null,
            null,
            null,
            requestedTargetIds,
            coverage.ResolvedTargetIds.ToList(),
            coverage.ExportedTargetIds.ToList(),
            null,
            null,
            coverage.Assets.ToList(),
            coverage.Failures.ToList()
        ),
        coverage.ReusedAssets
    );
}

static ExportResult ExportPrimaryContentGroups(ExportRequest request)
{
    if (string.IsNullOrWhiteSpace(request.OutputDirectory))
    {
        throw new InvalidDataException("Exporter output directory is required.");
    }
    string outputPath = Path.GetFullPath(request.OutputDirectory);
    int concurrency = Math.Min(
        request.Concurrency ?? throw new InvalidDataException(
            "Exporter concurrency is required."
        ),
        Environment.ProcessorCount
    );
    List<ResolvedExportGroup> groups = request.GetExportGroups();
    Dictionary<string, SelectiveExportAsset> assets = new(StringComparer.Ordinal);
    Dictionary<string, SelectiveExportFailure> failures = new(StringComparer.Ordinal);
    HashSet<string> requestedTargetIds = new(StringComparer.Ordinal);
    HashSet<string> resolvedTargetIds = new(StringComparer.Ordinal);
    HashSet<string> exportedTargetIds = new(StringComparer.Ordinal);

    for (int groupOffset = 0; groupOffset < groups.Count; groupOffset++)
    {
        ResolvedExportGroup group = groups[groupOffset];
        EventWriter.SetGroup(group.GroupId, groupOffset + 1, groups.Count);
        EventWriter.WriteGroupStarted();
        AssetProvenanceRegistry.Configure(
            group.Inputs.Select(input =>
                new AssetProvenanceInput(input.Path, input.NodeId, input.Target)
            )
        );
        FullConfiguration settings = new();
        GameData? gameData = null;
        bool groupCompleted = false;
        try
        {
            EventWriter.WritePhase("loading");
            GameStructure gameStructure = GameStructure.LoadPrimaryContent(
                group.Inputs.Select(input => input.Path).ToList(),
                LocalFileSystem.Instance,
                settings,
                new BaadLoadProgress(),
                concurrency
            );
            gameData = GameData.FromGameStructure(gameStructure);
            HashSet<string> expectedInputIds = group.Inputs
                .Select(input => input.NodeId)
                .ToHashSet(StringComparer.Ordinal);
            HashSet<string> loadedInputIds = AssetProvenanceRegistry
                .GetLoadedInputIds()
                .ToHashSet(StringComparer.Ordinal);
            if (gameData.GameBundle.AnyFailed || !loadedInputIds.SetEquals(expectedInputIds))
            {
                throw new InvalidDataException(
                    $"AssetRipper could not load every input in group '{group.GroupId}'."
                );
            }
            if (gameData.GameBundle.HasAnyAssetCollections())
            {
                EventWriter.WritePhase("processing");
                ProcessWithHeartbeat(settings, gameData);
            }
            GroupExportResult groupExport = ExportPrimaryContent(
                group.Inputs,
                outputPath,
                concurrency,
                gameData,
                settings,
                assets
            );
            ExportResult groupResult = groupExport.Result;
            HashSet<string> unresolvedTargetIds = (groupResult.RequestedTargetIds ?? [])
                .Except(groupResult.ResolvedTargetIds ?? [], StringComparer.Ordinal)
                .ToHashSet(StringComparer.Ordinal);
            if (unresolvedTargetIds.Count > 0)
            {
                throw new InvalidDataException(
                    $"AssetRipper did not resolve {unresolvedTargetIds.Count} target input(s) "
                    + $"in group '{group.GroupId}'."
                );
            }
            requestedTargetIds.UnionWith(groupResult.RequestedTargetIds ?? []);
            resolvedTargetIds.UnionWith(groupResult.ResolvedTargetIds ?? []);
            exportedTargetIds.UnionWith(groupResult.ExportedTargetIds ?? []);
            foreach (SelectiveExportReuse reuse in groupExport.ReusedAssets)
            {
                if (!assets.TryGetValue(reuse.StableId, out SelectiveExportAsset? existing))
                {
                    throw new InvalidDataException(
                        $"Reused asset is missing from the export session: {reuse.StableId}"
                    );
                }
                failures.Remove(reuse.StableId);
                assets[reuse.StableId] = existing with
                {
                    SourceTargetIds = existing.SourceTargetIds
                        .Concat(reuse.SourceTargetIds)
                        .Distinct(StringComparer.Ordinal)
                        .Order(StringComparer.Ordinal)
                        .ToArray(),
                };
            }
            foreach (SelectiveExportFailure failure in groupResult.Failures ?? [])
            {
                if (failures.TryGetValue(failure.StableId, out SelectiveExportFailure? existing))
                {
                    failures[failure.StableId] = existing with
                    {
                        SourceTargetIds = existing.SourceTargetIds
                            .Concat(failure.SourceTargetIds)
                            .Distinct(StringComparer.Ordinal)
                            .Order(StringComparer.Ordinal)
                            .ToArray(),
                    };
                }
                else
                {
                    failures.Add(failure.StableId, failure);
                }
            }
            foreach (SelectiveExportAsset asset in groupResult.Assets ?? [])
            {
                failures.Remove(asset.StableId);
                if (!assets.TryGetValue(asset.StableId, out SelectiveExportAsset? existing))
                {
                    assets.Add(asset.StableId, asset);
                    continue;
                }
                if (
                    existing.NormalizedCollection != asset.NormalizedCollection
                    || existing.ClassId != asset.ClassId
                    || existing.PathId != asset.PathId
                )
                {
                    throw new InvalidDataException(
                        $"Stable asset ID collision: {asset.StableId}"
                    );
                }
                DeleteDuplicateAssetFiles(outputPath, asset.Files);
                assets[asset.StableId] = existing with
                {
                    SourceTargetIds = existing.SourceTargetIds
                        .Concat(asset.SourceTargetIds)
                        .Distinct(StringComparer.Ordinal)
                        .Order(StringComparer.Ordinal)
                        .ToArray(),
                };
            }
            groupCompleted = true;
        }
        finally
        {
            gameData?.AssemblyManager.Dispose();
            gameData?.GameBundle.Dispose();
            AssetProvenanceRegistry.Configure([]);
            if (groupCompleted)
            {
                EventWriter.WriteGroupCompleted();
            }
            EventWriter.ClearGroup();
        }
    }

    return new ExportResult(
        true,
        null,
        [],
        null,
        null,
        null,
        requestedTargetIds.Order(StringComparer.Ordinal).ToList(),
        resolvedTargetIds.Order(StringComparer.Ordinal).ToList(),
        exportedTargetIds.Order(StringComparer.Ordinal).ToList(),
        null,
        null,
        assets.Values.OrderBy(item => item.StableId, StringComparer.Ordinal).ToList(),
        failures.Values.OrderBy(item => item.StableId, StringComparer.Ordinal).ToList()
    );
}

static void DeleteDuplicateAssetFiles(
    string outputRoot,
    IReadOnlyList<SelectiveExportFile> files
)
{
    string root = Path.GetFullPath(outputRoot);
    foreach (SelectiveExportFile file in files)
    {
        string path = Path.GetFullPath(Path.Combine(root, file.Path));
        string relative = Path.GetRelativePath(root, path);
        if (
            Path.IsPathRooted(relative)
            || relative == ".."
            || relative.StartsWith($"..{Path.DirectorySeparatorChar}", StringComparison.Ordinal)
        )
        {
            throw new InvalidDataException("Duplicate asset output escaped its root.");
        }
        File.Delete(path);
    }
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
        try
        {
            scans.Add(
                new ArchiveScanResult(
                    archiveId,
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
                entry.Crc32,
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
            null,
            assetFactory
        ));
    }
    return results.OrderBy(item => item.EntryPath, StringComparer.Ordinal).ToList();
}

static BundleEntryScanResult ScanEntry(
    byte[] buffer,
    string filePath,
    string entryPath,
    uint? crc32,
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
        crc32,
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

static ExportResult MaterializeBundleEntries(ExportRequest request)
{
    if (string.IsNullOrWhiteSpace(request.OutputDirectory))
    {
        throw new InvalidDataException("Bundle entry cache root is required.");
    }
    string cacheRoot = Path.GetFullPath(request.OutputDirectory);
    Directory.CreateDirectory(cacheRoot);
    List<MaterializeEntryInput> inputs = request.GetMaterializeInputs();
    StringComparer pathComparer = OperatingSystem.IsWindows()
        ? StringComparer.OrdinalIgnoreCase
        : StringComparer.Ordinal;
    ConcurrentBag<MaterializedEntryResult> results = [];
    int completed = 0;
    int archiveCount = inputs
        .Select(item => item.Path)
        .Distinct(pathComparer)
        .Count();
    int concurrency = Math.Min(
        Math.Max(1, request.Concurrency ?? 1),
        Math.Min(Environment.ProcessorCount, archiveCount)
    );
    Parallel.ForEach(
        inputs.GroupBy(item => item.Path, pathComparer),
        new ParallelOptions { MaxDegreeOfParallelism = concurrency },
        group =>
        {
            if (Path.GetExtension(group.Key).Equals(".zip", StringComparison.OrdinalIgnoreCase))
            {
                using ZipArchive archive = ZipFile.OpenRead(group.Key);
                Dictionary<string, ZipArchiveEntry> entries = archive.Entries
                    .Where(entry => !string.IsNullOrEmpty(entry.Name))
                    .ToDictionary(entry => entry.FullName, StringComparer.Ordinal);
                foreach (MaterializeEntryInput input in group)
                {
                    if (!entries.TryGetValue(input.EntryPath, out ZipArchiveEntry? entry))
                    {
                        throw new InvalidDataException($"Bundle entry was not found: {input.NodeId}");
                    }
                    if (
                        entry.Length != input.Size
                        || (input.Crc32 is not null && entry.Crc32 != input.Crc32)
                    )
                    {
                        throw new InvalidDataException($"Bundle entry changed after dependency scanning: {input.NodeId}");
                    }
                    using Stream source = entry.Open();
                    results.Add(MaterializeEntry(source, input, cacheRoot));
                    int current = Interlocked.Increment(ref completed);
                    EventWriter.WriteCacheProgress(current, inputs.Count, input.NodeId);
                }
                return;
            }
            foreach (MaterializeEntryInput input in group)
            {
                using FileStream source = File.OpenRead(group.Key);
                results.Add(MaterializeEntry(source, input, cacheRoot));
                int current = Interlocked.Increment(ref completed);
                EventWriter.WriteCacheProgress(current, inputs.Count, input.NodeId);
            }
        }
    );
    return new ExportResult(
        true,
        null,
        [],
        null,
        null,
        null,
        [],
        [],
        [],
        null,
        results.OrderBy(item => item.NodeId, StringComparer.Ordinal).ToList()
    );
}

static bool IsOutOfMemory(Exception exception) =>
    exception is OutOfMemoryException
    || exception is AggregateException aggregate
        && aggregate.Flatten().InnerExceptions.Any(IsOutOfMemory);

static MaterializedEntryResult MaterializeEntry(
    Stream source,
    MaterializeEntryInput input,
    string cacheRoot
)
{
    string destination = Path.GetFullPath(input.Destination);
    string relative = Path.GetRelativePath(cacheRoot, destination);
    if (
        Path.IsPathRooted(relative)
        || relative == ".."
        || relative.StartsWith($"..{Path.DirectorySeparatorChar}", StringComparison.Ordinal)
    )
    {
        throw new InvalidDataException($"Bundle cache destination escaped its root: {input.NodeId}");
    }
    Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
    string temporary = destination + $".{Guid.NewGuid():N}.tmp";
    string? markerTemporary = null;
    try
    {
        using IncrementalHash digest = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        long written = 0;
        using (FileStream target = new(
            temporary,
            FileMode.CreateNew,
            FileAccess.Write,
            FileShare.None,
            1024 * 1024,
            FileOptions.SequentialScan
        ))
        {
            byte[] buffer = new byte[1024 * 1024];
            int count;
            while ((count = source.Read(buffer, 0, buffer.Length)) > 0)
            {
                target.Write(buffer, 0, count);
                digest.AppendData(buffer, 0, count);
                written += count;
            }
        }
        string actualHash = Convert.ToHexString(digest.GetHashAndReset()).ToLowerInvariant();
        if (written != input.Size || actualHash != input.Sha256)
        {
            throw new InvalidDataException($"Bundle entry changed after dependency scanning: {input.NodeId}");
        }
        File.Move(temporary, destination, true);
        string marker = destination + ".json";
        markerTemporary = marker + $".{Guid.NewGuid():N}.tmp";
        File.WriteAllText(
            markerTemporary,
            JsonSerializer.Serialize(
                new
                {
                    schema_version = 0,
                    identity = input.MarkerIdentity,
                },
                JsonOptions.Default
            )
        );
        File.Move(markerTemporary, marker, true);
        return new MaterializedEntryResult(input.NodeId, destination, written);
    }
    finally
    {
        File.Delete(temporary);
        if (markerTemporary is not null)
        {
            File.Delete(markerTemporary);
        }
    }
}

static void ProcessWithHeartbeat(FullConfiguration settings, GameData gameData)
{
    using CancellationTokenSource cancellation = new();
    Task heartbeat = Task.Run(async () =>
    {
        try
        {
            while (true)
            {
                await Task.Delay(TimeSpan.FromSeconds(1), cancellation.Token);
                EventWriter.WriteHeartbeat("processing");
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
        }
    });

    try
    {
        IAssetProcessor[] processors = ContentProfile.CreateProcessors(settings);
        for (int index = 0; index < processors.Length; index++)
        {
            IAssetProcessor processor = processors[index];
            EventWriter.WriteProcessorProgress(
                index + 1,
                processors.Length,
                processor.GetType().Name
            );
            processor.Process(gameData);
        }
    }
    finally
    {
        cancellation.Cancel();
        heartbeat.GetAwaiter().GetResult();
    }
}

internal sealed record ExportInput(string Path, string NodeId, bool Target);
internal sealed record ExportGroupInput(string NodeId, bool Target);
internal sealed record ExportGroupRequest(string GroupId, List<ExportGroupInput> Inputs);
internal sealed record ResolvedExportGroup(string GroupId, List<ExportInput> Inputs);
internal sealed record GroupExportResult(
    ExportResult Result,
    IReadOnlyList<SelectiveExportReuse> ReusedAssets
);

internal sealed record MaterializeEntryInput(
    string Path,
    string NodeId,
    string EntryPath,
    string Sha256,
    long Size,
    uint? Crc32,
    JsonElement MarkerIdentity,
    string Destination
);

internal sealed record ExportRequest(
    int? SchemaVersion,
    string Operation,
    List<JsonElement> Inputs,
    string? OutputDirectory,
    List<string>? ArchiveIds,
    int? Concurrency,
    List<ExportGroupRequest>? Groups
)
{
    public void Validate()
    {
        if (SchemaVersion is not 0)
        {
            throw new InvalidDataException("Exporter request schema is invalid.");
        }
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
            if (Concurrency is null or <= 0)
            {
                throw new InvalidDataException("Exporter concurrency must be positive.");
            }
            if (exportInputs.Select(input => input.NodeId).Distinct(StringComparer.Ordinal).Count() != exportInputs.Count)
            {
                throw new InvalidDataException("Exporter input node IDs must be unique.");
            }
            _ = GetExportGroups();
        }
        if (Operation == "materialize_bundle_entries")
        {
            List<MaterializeEntryInput> materializeInputs = GetMaterializeInputs();
            if (Concurrency is null or <= 0)
            {
                throw new InvalidDataException("Bundle entry cache concurrency must be positive.");
            }
            if (materializeInputs.Select(input => input.NodeId).Distinct(StringComparer.Ordinal).Count() != materializeInputs.Count)
            {
                throw new InvalidDataException("Bundle entry cache node IDs must be unique.");
            }
            StringComparer pathComparer = OperatingSystem.IsWindows()
                ? StringComparer.OrdinalIgnoreCase
                : StringComparer.Ordinal;
            if (materializeInputs.Select(input => input.Destination).Distinct(pathComparer).Count() != materializeInputs.Count)
            {
                throw new InvalidDataException("Bundle entry cache destinations must be unique.");
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

    public List<ResolvedExportGroup> GetExportGroups()
    {
        List<ExportInput> inputs = GetExportInputs();
        if (Groups is null || Groups.Count == 0)
        {
            return [new ResolvedExportGroup("all", inputs)];
        }
        Dictionary<string, ExportInput> byNodeId = inputs.ToDictionary(
            input => input.NodeId,
            StringComparer.Ordinal
        );
        HashSet<string> groupIds = new(StringComparer.Ordinal);
        HashSet<string> covered = new(StringComparer.Ordinal);
        List<ResolvedExportGroup> result = [];
        foreach (ExportGroupRequest group in Groups)
        {
            if (
                string.IsNullOrWhiteSpace(group.GroupId)
                || !groupIds.Add(group.GroupId)
                || group.Inputs.Count == 0
            )
            {
                throw new InvalidDataException("Exporter groups must have unique IDs and inputs.");
            }
            HashSet<string> local = new(StringComparer.Ordinal);
            List<ExportInput> resolved = [];
            foreach (ExportGroupInput item in group.Inputs)
            {
                if (
                    string.IsNullOrWhiteSpace(item.NodeId)
                    || !local.Add(item.NodeId)
                    || !byNodeId.TryGetValue(item.NodeId, out ExportInput? input)
                )
                {
                    throw new InvalidDataException("Exporter group input is invalid.");
                }
                covered.Add(item.NodeId);
                resolved.Add(input with { Target = item.Target });
            }
            result.Add(new ResolvedExportGroup(group.GroupId, resolved));
        }
        if (!covered.SetEquals(byNodeId.Keys))
        {
            throw new InvalidDataException("Exporter groups must cover every input.");
        }
        return result;
    }

    public List<MaterializeEntryInput> GetMaterializeInputs()
    {
        List<MaterializeEntryInput> result = [];
        foreach (JsonElement input in Inputs)
        {
            if (input.ValueKind != JsonValueKind.Object)
            {
                throw new InvalidDataException("Bundle entry cache inputs must be objects.");
            }
            MaterializeEntryInput? parsed = input.Deserialize<MaterializeEntryInput>(JsonOptions.Default);
            if (
                parsed is null
                || string.IsNullOrWhiteSpace(parsed.Path)
                || string.IsNullOrWhiteSpace(parsed.NodeId)
                || string.IsNullOrWhiteSpace(parsed.EntryPath)
                || string.IsNullOrWhiteSpace(parsed.Destination)
                || parsed.Size < 0
                || parsed.Sha256.Length != 64
                || parsed.Sha256.Any(character => !Uri.IsHexDigit(character))
            )
            {
                throw new InvalidDataException("Bundle entry cache input is invalid.");
            }
            result.Add(parsed with
            {
                Path = Path.GetFullPath(parsed.Path),
                Destination = Path.GetFullPath(parsed.Destination),
            });
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
    List<string>? ExportedTargetIds = null,
    string? FailureKind = null,
    List<MaterializedEntryResult>? MaterializedEntries = null,
    List<SelectiveExportAsset>? Assets = null,
    List<SelectiveExportFailure>? Failures = null,
    int SchemaVersion = 0
);
internal sealed record MaterializedEntryResult(
    string NodeId,
    string Path,
    long BytesWritten
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
    List<BundleEntryScanResult> Entries,
    string? Error
);
internal sealed record BundleEntryScanResult(
    string EntryPath,
    string Sha256,
    long Size,
    uint? Crc32,
    List<SerializedFileScanResult> SerializedFiles,
    List<string> ResourceFiles,
    List<StreamedResourceScanResult> StreamedResources,
    string? Error
);

internal sealed class BaadEventLogger : ILogger
{
    public bool Enabled { get; set; } = true;

    public void BlankLine(int numLines) { }

    public void Log(LogType type, LogCategory category, string message)
    {
        if (!Enabled)
        {
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
    private const int Version = 0;
    private static readonly object SyncRoot = new();
    private static GroupEventContext? CurrentGroup;

    public static void SetGroup(string groupId, int index, int total) =>
        CurrentGroup = new GroupEventContext(groupId, index, total);

    public static void ClearGroup() => CurrentGroup = null;

    public static void WriteGroupStarted()
    {
        GroupEventContext group = RequireGroup();
        Write(new
        {
            version = Version,
            kind = "group_started",
            group_id = group.GroupId,
            group_index = group.Index,
            group_total = group.Total,
        });
    }

    public static void WriteGroupCompleted()
    {
        GroupEventContext group = RequireGroup();
        Write(new
        {
            version = Version,
            kind = "group_completed",
            group_id = group.GroupId,
            group_index = group.Index,
            group_total = group.Total,
        });
    }

    public static void WritePhase(string phase)
    {
        GroupEventContext group = CurrentGroup ?? new GroupEventContext("", 0, 0);
        Write(new { version = Version, kind = "phase", phase, group_id = group.GroupId, group_index = group.Index, group_total = group.Total });
    }

    public static void WriteAssetLifecycle(
        string stableId,
        string item,
        bool started,
        int current,
        int total)
    {
        GroupEventContext group = RequireGroup();
        Write(new
        {
            version = Version,
            kind = started ? "asset_started" : "asset_completed",
            stable_id = stableId,
            item,
            current,
            total,
            group_id = group.GroupId,
            group_index = group.Index,
            group_total = group.Total,
        });
    }

    public static void WriteHeartbeat(string phase)
    {
        GroupEventContext group = CurrentGroup ?? new GroupEventContext("", 0, 0);
        Write(new
        {
            version = Version,
            kind = "heartbeat",
            phase,
            group_id = group.GroupId,
            group_index = group.Index,
            group_total = group.Total,
        });
    }

    public static void WriteProcessorProgress(
        int current,
        int total,
        string processor
    )
    {
        GroupEventContext group = CurrentGroup ?? new GroupEventContext("", 0, 0);
        Write(new
        {
            version = Version,
            kind = "processor_progress",
            current,
            total,
            processor,
            group_id = group.GroupId,
            group_index = group.Index,
            group_total = group.Total,
        });
    }

    public static void WriteLoadingProgress(string stage, int current, int total)
    {
        GroupEventContext group = CurrentGroup ?? new GroupEventContext("", 0, 0);
        Write(new
        {
            version = Version,
            kind = "progress",
            phase = "loading",
            stage,
            current,
            total,
            group_id = group.GroupId,
            group_index = group.Index,
            group_total = group.Total,
        });
    }

    public static void WriteScanProgress(int current, int total, string archiveId) =>
        Write(new
        {
            version = Version,
            kind = "scan_progress",
            current,
            total,
            archive_id = archiveId,
        });

    public static void WriteCacheProgress(int current, int total, string nodeId) =>
        Write(new
        {
            version = Version,
            kind = "cache_progress",
            current,
            total,
            node_id = nodeId,
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

    private static GroupEventContext RequireGroup() =>
        CurrentGroup ?? throw new InvalidOperationException("AssetRipper group context is unavailable.");

    private sealed record GroupEventContext(string GroupId, int Index, int Total);
}

internal static class JsonOptions
{
    public static readonly JsonSerializerOptions Default = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
    };
}
