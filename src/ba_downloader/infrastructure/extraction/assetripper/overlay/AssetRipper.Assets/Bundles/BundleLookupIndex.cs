using System.Runtime.CompilerServices;
using AssetRipper.Assets.Collections;
using AssetRipper.Assets.IO;
using AssetRipper.IO.Files;
using AssetRipper.IO.Files.ResourceFiles;
using AssetRipper.IO.Files.SerializedFiles.Parser;

namespace AssetRipper.Assets.Bundles;

public static class BundleLookupIndex
{
	private static readonly ConditionalWeakTable<GameBundle, Lookup> Lookups = new();

	public static void Register(GameBundle gameBundle)
	{
		ArgumentNullException.ThrowIfNull(gameBundle);
		Lookups.Remove(gameBundle);
		Lookups.Add(gameBundle, new Lookup(gameBundle));
	}

	public static bool TryResolveCollection(
		Bundle source,
		FileIdentifier identifier,
		out AssetCollection? collection)
	{
		if (!TryGetLookup(source, out Lookup? lookup))
		{
			collection = null;
			return false;
		}
		collection = lookup.ResolveCollection(source, identifier.GetFilePath());
		return true;
	}

	public static bool TryResolveResource(
		Bundle source,
		string name,
		out ResourceFile? resource)
	{
		if (!TryGetLookup(source, out Lookup? lookup))
		{
			resource = null;
			return false;
		}
		resource = lookup.ResolveResource(source, name);
		return true;
	}

	private static bool TryGetLookup(Bundle source, [NotNullWhen(true)] out Lookup? lookup)
	{
		if (source.GetRoot() is GameBundle root && Lookups.TryGetValue(root, out lookup))
		{
			return true;
		}
		lookup = null;
		return false;
	}

	private sealed class Lookup
	{
		private readonly Dictionary<Bundle, BundleEntries> entries = new(ReferenceEqualityComparer.Instance);

		public Lookup(GameBundle root)
		{
			Index(root);
		}

		public AssetCollection? ResolveCollection(Bundle source, string name)
		{
			AssetCollection? result = ResolveCollectionCore(source, name);
			if (result is not null)
			{
				return result;
			}
			string fixedName = SpecialFileNames.FixFileIdentifier(name);
			result = ResolveCollectionCore(source, fixedName);
			if (result is not null)
			{
				return result;
			}
			return fixedName switch
			{
				SpecialFileNames.DefaultResourceName1 => ResolveCollectionCore(source, SpecialFileNames.DefaultResourceName2),
				SpecialFileNames.DefaultResourceName2 => ResolveCollectionCore(source, SpecialFileNames.DefaultResourceName1),
				SpecialFileNames.BuiltinExtraName1 => ResolveCollectionCore(source, SpecialFileNames.BuiltinExtraName2),
				SpecialFileNames.BuiltinExtraName2 => ResolveCollectionCore(source, SpecialFileNames.BuiltinExtraName1),
				_ => null,
			};
		}

		public ResourceFile? ResolveResource(Bundle source, string name)
		{
			string fixedName = SpecialFileNames.FixFileIdentifier(name);
			Bundle? excluded = null;
			for (Bundle? current = source; current is not null; current = current.Parent)
			{
				BundleEntries item = entries[current];
				if (item.Resources.TryGetValue(fixedName, out ResourceFile? direct))
				{
					return direct;
				}
				if (item.ChildResources.TryGetValue(fixedName, out List<ChildResource>? children))
				{
					foreach (ChildResource child in children)
					{
						if (!ReferenceEquals(child.Bundle, excluded))
						{
							return child.Resource;
						}
					}
				}
				excluded = current;
			}
			return null;
		}

		private AssetCollection? ResolveCollectionCore(Bundle source, string name)
		{
			Bundle? excluded = null;
			for (Bundle? current = source; current is not null; current = current.Parent)
			{
				BundleEntries item = entries[current];
				if (item.Collections.TryGetValue(name, out AssetCollection? direct))
				{
					return direct;
				}
				if (item.ChildCollections.TryGetValue(name, out List<ChildCollection>? children))
				{
					foreach (ChildCollection child in children)
					{
						if (!ReferenceEquals(child.Bundle, excluded))
						{
							return child.Collection;
						}
					}
				}
				excluded = current;
			}
			return null;
		}

		private void Index(Bundle bundle)
		{
			Dictionary<string, AssetCollection> collections = new(StringComparer.Ordinal);
			foreach (AssetCollection collection in bundle.Collections)
			{
				collections.TryAdd(collection.Name, collection);
			}
			Dictionary<string, ResourceFile> resources = new(StringComparer.Ordinal);
			foreach (ResourceFile resource in bundle.Resources)
			{
				resources.TryAdd(resource.NameFixed, resource);
			}
			Dictionary<string, List<ChildCollection>> childCollections = new(StringComparer.Ordinal);
			Dictionary<string, List<ChildResource>> childResources = new(StringComparer.Ordinal);
			foreach (Bundle child in bundle.Bundles)
			{
				foreach (AssetCollection collection in child.Collections)
				{
					if (!childCollections.TryGetValue(collection.Name, out List<ChildCollection>? list))
					{
						list = [];
						childCollections.Add(collection.Name, list);
					}
					list.Add(new ChildCollection(child, collection));
				}
				foreach (ResourceFile resource in child.Resources)
				{
					if (!childResources.TryGetValue(resource.NameFixed, out List<ChildResource>? list))
					{
						list = [];
						childResources.Add(resource.NameFixed, list);
					}
					list.Add(new ChildResource(child, resource));
				}
			}
			entries.Add(bundle, new BundleEntries(collections, resources, childCollections, childResources));
			foreach (Bundle child in bundle.Bundles)
			{
				Index(child);
			}
		}
	}

	private sealed record BundleEntries(
		Dictionary<string, AssetCollection> Collections,
		Dictionary<string, ResourceFile> Resources,
		Dictionary<string, List<ChildCollection>> ChildCollections,
		Dictionary<string, List<ChildResource>> ChildResources
	);
	private sealed record ChildCollection(Bundle Bundle, AssetCollection Collection);
	private sealed record ChildResource(Bundle Bundle, ResourceFile Resource);
}
