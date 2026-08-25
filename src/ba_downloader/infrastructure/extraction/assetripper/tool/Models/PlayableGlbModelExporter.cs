using System.Diagnostics.CodeAnalysis;
using AssetRipper.Assets;
using AssetRipper.Export.Modules.Models;
using AssetRipper.Export.PrimaryContent;
using AssetRipper.Import.Logging;
using AssetRipper.IO.Files;
using AssetRipper.Processing.Prefabs;

namespace Baad.AssetRipper.Models;

public interface IPlayableGlbPostProcessor
{
	void Process(PlayableGlbBuildResult result);
}

public sealed class PlayableGlbModelExporter(
	IPlayableGlbPostProcessor? postProcessor = null) : IContentExtractor
{
	public bool TryCreateCollection(
		IUnityObjectBase asset,
		[NotNullWhen(true)] out ExportCollectionBase? exportCollection)
	{
		switch (asset.MainAsset)
		{
			case SceneHierarchyObject sceneHierarchyObject:
				exportCollection = new SceneExportCollection(this, sceneHierarchyObject);
				return true;
			case PrefabHierarchyObject prefabHierarchyObject:
				exportCollection = new PrefabExportCollection(this, prefabHierarchyObject);
				return true;
			default:
				exportCollection = null;
				return false;
		}
	}

	public bool Export(IEnumerable<IUnityObjectBase> assets, string path, FileSystem fileSystem)
	{
		IUnityObjectBase[] materialized = assets.ToArray();
		return ExportPlayableModel(
			materialized,
			path,
			materialized.FirstOrDefault() is SceneHierarchyObject,
			fileSystem);
	}

	private bool ExportPlayableModel(
		IEnumerable<IUnityObjectBase> assets,
		string path,
		bool isScene,
		FileSystem fileSystem)
	{
		PlayableGlbBuildResult result = PlayableGlbLevelBuilder.Build(assets, isScene);
		postProcessor?.Process(result);
		using Stream stream = fileSystem.File.Create(path);
		if (GlbWriter.TryWrite(result.Scene, stream, out string? error))
		{
			return true;
		}
		Logger.Error(LogCategory.Export, error);
		return false;
	}

	public static bool ExportModel(
		IEnumerable<IUnityObjectBase> assets,
		string path,
		bool isScene,
		FileSystem fileSystem) =>
		new PlayableGlbModelExporter().ExportPlayableModel(assets, path, isScene, fileSystem);

	private sealed class SceneExportCollection
		: MultipleExportCollection<SceneHierarchyObject>
	{
		public SceneExportCollection(IContentExtractor extractor, SceneHierarchyObject asset)
			: base(extractor, asset)
		{
			AddAssets(asset.Assets);
		}

		protected override string ExportExtension => "glb";
	}

	private sealed class PrefabExportCollection
		: MultipleExportCollection<PrefabHierarchyObject>
	{
		public PrefabExportCollection(IContentExtractor extractor, PrefabHierarchyObject asset)
			: base(extractor, asset)
		{
			AddAssets(asset.Assets);
		}

		protected override string ExportExtension => "glb";
	}
}
