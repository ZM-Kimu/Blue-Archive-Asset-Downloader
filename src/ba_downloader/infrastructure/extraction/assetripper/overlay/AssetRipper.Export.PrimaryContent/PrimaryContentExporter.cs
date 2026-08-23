using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using AssetRipper.Assets;
using AssetRipper.Assets.Bundles;
using AssetRipper.Export.Configuration;
using AssetRipper.Export.PrimaryContent.Audio;
using AssetRipper.Export.PrimaryContent.Models;
using AssetRipper.Export.PrimaryContent.Textures;
using AssetRipper.Import.Configuration;
using AssetRipper.Import.Logging;
using AssetRipper.Processing;
using AssetRipper.Processing.Prefabs;
using AssetRipper.SourceGenerated.Classes.ClassID_1;
using AssetRipper.SourceGenerated.Classes.ClassID_2;
using AssetRipper.SourceGenerated.Classes.ClassID_21;
using AssetRipper.SourceGenerated.Classes.ClassID_28;
using AssetRipper.SourceGenerated.Classes.ClassID_3;
using AssetRipper.SourceGenerated.Classes.ClassID_43;
using AssetRipper.SourceGenerated.Classes.ClassID_49;
using AssetRipper.SourceGenerated.Classes.ClassID_83;
using AssetRipper.SourceGenerated.Classes.ClassID_128;
using AssetRipper.SourceGenerated.Classes.ClassID_213;

namespace AssetRipper.Export.PrimaryContent;

public sealed record SelectiveExportResult(
	IReadOnlyList<string> ResolvedTargetIds,
	IReadOnlyList<string> ExportedTargetIds,
	IReadOnlyList<SelectiveExportAsset> Assets,
	IReadOnlyList<SelectiveExportFailure> Failures
);

public sealed record SelectiveExportFile(string Path, long Size, long MtimeNs, string Sha256);

public sealed record SelectiveExportAsset(
	string StableId,
	string AssetType,
	string ReadableName,
	string Collection,
	string NormalizedCollection,
	long PathId,
	int ClassId,
	IReadOnlyList<string> SourceTargetIds,
	IReadOnlyList<SelectiveExportFile> Files
);

public sealed record SelectiveExportFailure(
	string StableId,
	IReadOnlyList<string> SourceTargetIds,
	string Error
);

internal sealed record ExportDescriptor(
	ExportCollectionBase Collection,
	string StableId,
	string AssetType,
	string ReadableName,
	string CollectionName,
	string NormalizedCollection,
	long PathId,
	int ClassId,
	string Identity,
	string[] SourceTargetIds,
	string SortKey
);

internal sealed record PlannedDescriptor(ExportDescriptor Descriptor, PlannedExport Plan);

public sealed class PrimaryContentExporter
{
	private readonly ObjectHandlerStack<IContentExtractor> exporters = new();

	private PrimaryContentExporter()
	{
	}

	public void RegisterHandler<T>(IContentExtractor handler, bool allowInheritance = true) where T : IUnityObjectBase =>
		exporters.OverrideHandler(typeof(T), handler, allowInheritance);

	public static PrimaryContentExporter CreateDefault(GameData gameData, FullConfiguration settings)
	{
		PrimaryContentExporter exporter = new();
		exporter.RegisterDefaultHandlers();
		return exporter;
	}

	private void RegisterDefaultHandlers()
	{
		RegisterHandler<IUnityObjectBase>(EmptyContentExtractor.Instance);
		GlbModelExporter modelExporter = new();
		RegisterHandler<GameObjectHierarchyObject>(modelExporter);
		RegisterHandler<IGameObject>(modelExporter);
		RegisterHandler<IComponent>(modelExporter);
		RegisterHandler<ILevelGameManager>(modelExporter);
		RegisterHandler<IMesh>(new GlbMeshExporter());
		RegisterHandler<ITextAsset>(BinaryAssetContentExtractor.Instance);
		RegisterHandler<IFont>(BinaryAssetContentExtractor.Instance);
		RegisterHandler<IAudioClip>(new AudioContentExtractor());
		RegisterHandler<ITexture2D>(new TextureExporter(ImageExportFormat.Png));
		RegisterHandler<ISprite>(new SpritePngExporter());
	}

	public SelectiveExportResult ExportSelective(
		GameBundle fileCollection,
		FullConfiguration settings,
		FileSystem fileSystem,
		IReadOnlySet<string> targetIds,
		int concurrency)
	{
		if (concurrency <= 0)
		{
			throw new ArgumentOutOfRangeException(nameof(concurrency));
		}
		HashSet<string> handledEmptyTargetIds = new(StringComparer.Ordinal);
		List<ExportCollectionBase> collections = CreateCollections(
			fileCollection,
			targetIds,
			handledEmptyTargetIds);
		List<ExportDescriptor> descriptors = CreateDescriptors(
			collections,
			settings,
			fileSystem,
			targetIds,
			handledEmptyTargetIds);
		return ExportDescriptors(
			descriptors,
			settings,
			fileSystem,
			handledEmptyTargetIds,
			concurrency,
			AssetProvenanceRegistry.GetResolvedTargetIds(fileCollection));
	}

	private static List<ExportDescriptor> CreateDescriptors(
		IEnumerable<ExportCollectionBase> collections,
		FullConfiguration settings,
		FileSystem fileSystem,
		IReadOnlySet<string> targetIds,
		HashSet<string> handledEmptyTargetIds)
	{
		Dictionary<string, ExportDescriptor> descriptors = new(StringComparer.Ordinal);
		foreach (ExportCollectionBase collection in collections)
		{
			if (!collection.Exportable)
			{
				continue;
			}
			IUnityObjectBase? primary = collection.ExportableAssets.FirstOrDefault()
				?? collection.Assets.FirstOrDefault();
			string[] sourceTargetIds = collection.Assets
				.SelectMany(AssetProvenanceRegistry.ResolveProvenance)
				.Where(targetIds.Contains)
				.Distinct(StringComparer.Ordinal)
				.Order(StringComparer.Ordinal)
				.ToArray();
			if (primary is null)
			{
				handledEmptyTargetIds.UnionWith(sourceTargetIds);
				continue;
			}
			string normalizedCollection = NormalizeCollection(primary.Collection.Name);
			string identity = $"{normalizedCollection}\n{primary.ClassID}\n{primary.PathID}";
			string stableId = Convert.ToHexString(
				SHA256.HashData(Encoding.UTF8.GetBytes(identity))).ToLowerInvariant()[..20];
			string readableName = primary.GetBestName();
			if (string.IsNullOrWhiteSpace(readableName))
			{
				readableName = string.IsNullOrWhiteSpace(collection.Name)
					? primary.ClassName
					: collection.Name;
			}
			ExportDescriptor descriptor = new(
				collection,
				stableId,
				primary.ClassName,
				readableName,
				primary.Collection.Name,
				normalizedCollection,
				primary.PathID,
				primary.ClassID,
				identity,
				sourceTargetIds,
				collection.GetPathSortKey(settings.ExportRootPath, fileSystem));
			if (descriptors.TryGetValue(stableId, out ExportDescriptor? existing))
			{
				if (existing.Identity != identity)
				{
					throw new InvalidDataException($"Stable asset ID collision: {stableId}");
				}
				descriptors[stableId] = existing with
				{
					SourceTargetIds = existing.SourceTargetIds
						.Concat(sourceTargetIds)
						.Distinct(StringComparer.Ordinal)
						.Order(StringComparer.Ordinal)
						.ToArray(),
				};
				continue;
			}
			descriptors.Add(stableId, descriptor);
		}
		return descriptors.Values
			.OrderBy(item => item.SortKey, StringComparer.Ordinal)
			.ThenBy(item => item.NormalizedCollection, StringComparer.Ordinal)
			.ThenBy(item => item.ClassId)
			.ThenBy(item => item.PathId)
			.ToList();
	}

	private static SelectiveExportResult ExportDescriptors(
		IReadOnlyList<ExportDescriptor> descriptors,
		FullConfiguration settings,
		FileSystem fileSystem,
		HashSet<string> handledEmptyTargetIds,
		int requestedConcurrency,
		IReadOnlyList<string> resolvedTargetIds)
	{
		List<PlannedDescriptor> planned = new(descriptors.Count);
		foreach (ExportDescriptor descriptor in descriptors)
		{
			planned.Add(new PlannedDescriptor(
				descriptor,
				descriptor.Collection.PlanExport(settings.ExportRootPath, fileSystem)));
		}

		ConcurrentBag<SelectiveExportAsset> assets = [];
		ConcurrentBag<SelectiveExportFailure> failures = [];
		int completed = 0;
		Parallel.ForEach(
			planned,
			new ParallelOptions
			{
				MaxDegreeOfParallelism = Math.Min(requestedConcurrency, Environment.ProcessorCount),
			},
			item =>
			{
				try
				{
					if (!item.Descriptor.Collection.ExportPlanned(
						item.Plan,
						settings.ExportRootPath,
						fileSystem))
					{
						throw new InvalidDataException("The content extractor returned failure.");
					}
					assets.Add(ToExportedAsset(item, settings.ExportRootPath));
				}
				catch (Exception exception) when (exception is not OutOfMemoryException)
				{
					TryDelete(item.Plan.FilePath);
					failures.Add(new SelectiveExportFailure(
						item.Descriptor.StableId,
						item.Descriptor.SourceTargetIds,
						$"{exception.GetType().Name}: {exception.Message}"));
				}
				finally
				{
					int current = Interlocked.Increment(ref completed);
					Logger.Info(
						LogCategory.ExportProgress,
						$"({current}/{planned.Count}) Exporting '{item.Descriptor.ReadableName}'");
				}
			});

		SelectiveExportAsset[] orderedAssets = assets
			.OrderBy(item => item.Files[0].Path, StringComparer.Ordinal)
			.ThenBy(item => item.StableId, StringComparer.Ordinal)
			.ToArray();
		SelectiveExportFailure[] orderedFailures = failures
			.OrderBy(item => item.StableId, StringComparer.Ordinal)
			.ToArray();
		HashSet<string> exportedTargetIds = new(handledEmptyTargetIds, StringComparer.Ordinal);
		foreach (SelectiveExportAsset asset in orderedAssets)
		{
			exportedTargetIds.UnionWith(asset.SourceTargetIds);
		}
		return new SelectiveExportResult(
			resolvedTargetIds.Order(StringComparer.Ordinal).ToArray(),
			exportedTargetIds.Order(StringComparer.Ordinal).ToArray(),
			orderedAssets,
			orderedFailures);
	}

	private static SelectiveExportAsset ToExportedAsset(PlannedDescriptor item, string outputRoot)
	{
		FileInfo info = new(item.Plan.FilePath);
		if (!info.Exists || info.Length == 0)
		{
			throw new InvalidDataException("Asset export produced an empty file.");
		}
		string relativePath = Path.GetRelativePath(outputRoot, info.FullName).Replace('\\', '/');
		if (Path.IsPathRooted(relativePath) || relativePath.StartsWith("../", StringComparison.Ordinal))
		{
			throw new InvalidDataException("Asset output escaped its export root.");
		}
		using FileStream stream = info.Open(FileMode.Open, FileAccess.Read, FileShare.Read);
		string sha256 = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
		long mtimeNs = (info.LastWriteTimeUtc.Ticks - DateTime.UnixEpoch.Ticks) * 100;
		SelectiveExportFile file = new(relativePath, info.Length, mtimeNs, sha256);
		ExportDescriptor descriptor = item.Descriptor;
		return new SelectiveExportAsset(
			descriptor.StableId,
			descriptor.AssetType,
			descriptor.ReadableName,
			descriptor.CollectionName,
			descriptor.NormalizedCollection,
			descriptor.PathId,
			descriptor.ClassId,
			descriptor.SourceTargetIds,
			[file]);
	}

	private List<ExportCollectionBase> CreateCollections(
		GameBundle fileCollection,
		IReadOnlySet<string> targetIds,
		HashSet<string> handledEmptyTargetIds)
	{
		List<ExportCollectionBase> collections = [];
		HashSet<IUnityObjectBase> queued = [];
		foreach (IUnityObjectBase asset in fileCollection.FetchAssets())
		{
			if (!queued.Add(asset))
			{
				continue;
			}
			HashSet<string> provenance = AssetProvenanceRegistry.ResolveProvenance(asset);
			if (!provenance.Overlaps(targetIds))
			{
				continue;
			}
			ExportCollectionBase collection = CreateCollection(asset);
			if (collection is EmptyExportCollection)
			{
				handledEmptyTargetIds.UnionWith(provenance.Where(targetIds.Contains));
				continue;
			}
			foreach (IUnityObjectBase element in collection.Assets)
			{
				queued.Add(element);
			}
			collections.Add(collection);
		}
		return collections;
	}

	private ExportCollectionBase CreateCollection(IUnityObjectBase asset)
	{
		foreach (IContentExtractor exporter in exporters.GetHandlerStack(asset.GetType()))
		{
			if (exporter.TryCreateCollection(asset, out ExportCollectionBase? collection))
			{
				return collection;
			}
		}
		throw new InvalidDataException($"There is no content handler for '{asset.ClassName}'.");
	}

	private static string NormalizeCollection(string value) =>
		value.Replace('\\', '/').Trim().ToLowerInvariant();

	private static void TryDelete(string path)
	{
		try
		{
			File.Delete(path);
		}
		catch (IOException)
		{
		}
		catch (UnauthorizedAccessException)
		{
		}
	}
}
