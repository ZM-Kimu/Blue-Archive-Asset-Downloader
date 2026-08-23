using System.Collections.Concurrent;
using AssetRipper.Assets.Collections;
using AssetRipper.IO.Files;

namespace AssetRipper.Assets.Bundles;

public readonly record struct AssetProvenanceInput(
	string Path,
	string NodeId,
	bool Target
);

public static class AssetProvenanceRegistry
{
	private static readonly ConcurrentDictionary<string, AssetProvenanceInput> Inputs = new(StringComparer.OrdinalIgnoreCase);
	private static readonly ConcurrentDictionary<FileBase, AssetProvenanceInput> Files = new(ReferenceEqualityComparer.Instance);
	private static readonly ConcurrentDictionary<AssetCollection, HashSet<string>> Collections = new(ReferenceEqualityComparer.Instance);
	private static readonly ConcurrentDictionary<IUnityObjectBase, HashSet<string>> DerivedAssets = new(ReferenceEqualityComparer.Instance);
	private static readonly HashSet<string> TargetIds = new(StringComparer.Ordinal);

	public static void Configure(IEnumerable<AssetProvenanceInput> inputs)
	{
		Inputs.Clear();
		Files.Clear();
		Collections.Clear();
		DerivedAssets.Clear();
		TargetIds.Clear();
		foreach (AssetProvenanceInput input in inputs)
		{
			string path = Path.GetFullPath(input.Path);
			if (!Inputs.TryAdd(path, input with { Path = path }))
			{
				throw new InvalidDataException($"Duplicate AssetRipper input path: {path}");
			}
			if (input.Target && !TargetIds.Add(input.NodeId))
			{
				throw new InvalidDataException($"Duplicate AssetRipper target ID: {input.NodeId}");
			}
		}
	}

	public static void RegisterInput(FileBase file, string path)
	{
		if (Inputs.TryGetValue(Path.GetFullPath(path), out AssetProvenanceInput input))
		{
			Files[file] = input;
		}
	}

	public static void RegisterCollection(FileBase file, AssetCollection collection)
	{
		if (Files.TryGetValue(file, out AssetProvenanceInput input))
		{
			Collections[collection] = new HashSet<string>([input.NodeId], StringComparer.Ordinal);
		}
	}

	public static void RegisterDerived(IUnityObjectBase asset, object? source)
	{
		if (source is IUnityObjectBase sourceAsset)
		{
			HashSet<string> provenance = ResolveProvenance(sourceAsset);
			if (provenance.Count > 0)
			{
				DerivedAssets[asset] = provenance;
			}
		}
	}

	public static HashSet<string> ResolveProvenance(IUnityObjectBase asset)
	{
		return ResolveProvenance(asset, new HashSet<IUnityObjectBase>(ReferenceEqualityComparer.Instance));
	}

	public static IReadOnlyList<string> GetResolvedTargetIds(GameBundle gameBundle)
	{
		HashSet<string> resolved = new(StringComparer.Ordinal);
		foreach (AssetCollection collection in gameBundle.FetchAssetCollections())
		{
			if (Collections.TryGetValue(collection, out HashSet<string>? provenance))
			{
				resolved.UnionWith(provenance.Where(TargetIds.Contains));
			}
		}
		return resolved.Order(StringComparer.Ordinal).ToArray();
	}

	public static IReadOnlyList<string> GetLoadedInputIds() => Files.Values
		.Select(input => input.NodeId)
		.Distinct(StringComparer.Ordinal)
		.Order(StringComparer.Ordinal)
		.ToArray();

	private static HashSet<string> ResolveProvenance(
		IUnityObjectBase asset,
		HashSet<IUnityObjectBase> visiting
	)
	{
		if (Collections.TryGetValue(asset.Collection, out HashSet<string>? collectionProvenance))
		{
			return new HashSet<string>(collectionProvenance, StringComparer.Ordinal);
		}
		if (DerivedAssets.TryGetValue(asset, out HashSet<string>? derivedProvenance))
		{
			return new HashSet<string>(derivedProvenance, StringComparer.Ordinal);
		}
		HashSet<string> result = new(StringComparer.Ordinal);
		if (!visiting.Add(asset))
		{
			return result;
		}
		foreach ((_, Metadata.PPtr pointer) in asset.FetchDependencies())
		{
			if (asset.Collection.TryGetAsset(pointer) is { } dependency)
			{
				result.UnionWith(ResolveProvenance(dependency, visiting));
			}
		}
		visiting.Remove(asset);
		if (result.Count > 0)
		{
			DerivedAssets[asset] = new HashSet<string>(result, StringComparer.Ordinal);
		}
		return result;
	}
}
