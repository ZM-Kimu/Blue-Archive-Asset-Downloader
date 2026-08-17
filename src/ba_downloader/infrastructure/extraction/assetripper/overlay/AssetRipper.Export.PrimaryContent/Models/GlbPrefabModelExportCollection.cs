using AssetRipper.Assets;
using AssetRipper.Primitives;
using AssetRipper.Processing.Prefabs;
using System.Globalization;

namespace AssetRipper.Export.PrimaryContent.Models;

public sealed class GlbPrefabModelExportCollection : MultipleExportCollection<PrefabHierarchyObject>
{
	public GlbPrefabModelExportCollection(GlbModelExporter assetExporter, PrefabHierarchyObject asset) : base(assetExporter, asset)
	{
		AddAssets(asset.Assets);
	}

	public override bool Export(string projectDirectory, FileSystem fileSystem)
	{
		string basePath = fileSystem.Path.Join(
			projectDirectory,
			FileSystem.FixInvalidPathCharacters(
				((IUnityObjectBase)Asset).GetBestDirectory()));
		string subPath = fileSystem.Path.Join(basePath, GetStableDirectoryName(Asset));
		string fileName = GetUniqueFileName(Asset, subPath, fileSystem);

		fileSystem.Directory.Create(subPath);

		string filePath = fileSystem.Path.Join(subPath, fileName);
		return ExportInner(filePath, projectDirectory, fileSystem);
	}

	private static string GetStableDirectoryName(PrefabHierarchyObject asset)
	{
		string collectionName = asset.Root.Collection.Name;
		string identity = string.Concat(
			"PrefabHierarchy:",
			collectionName.Length.ToString(CultureInfo.InvariantCulture),
			":",
			collectionName,
			":",
			asset.Root.PathID.ToString(CultureInfo.InvariantCulture));
		return UnityGuid.Md5Hash(identity).ToString();
	}

	protected override string ExportExtension => "glb";
}
