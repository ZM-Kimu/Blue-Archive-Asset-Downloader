using AssetRipper.Assets.Bundles;
using AssetRipper.Export.Configuration;
using AssetRipper.Export.UnityProjects.PathIdMapping;
using AssetRipper.Export.UnityProjects.Project;
using AssetRipper.Export.UnityProjects.Scripts;
using AssetRipper.Import.Configuration;
using AssetRipper.Import.Logging;
using AssetRipper.Import.Structure;
using AssetRipper.Processing;
using AssetRipper.Processing.Editor;
using AssetRipper.Processing.Prefabs;
using AssetRipper.Processing.Scenes;
using AssetRipper.Processing.Textures;

namespace AssetRipper.Export.UnityProjects;

public class ExportHandler
{
	protected FullConfiguration Settings { get; }

	public ExportHandler(FullConfiguration settings)
	{
		Settings = settings;
	}

	public GameData Load(IReadOnlyList<string> paths, FileSystem fileSystem, IGameLoadProgress? progress = null)
	{
		if (paths.Count == 1)
		{
			Logger.Info(LogCategory.Import, $"Attempting to read files from {paths[0]}");
		}
		else
		{
			Logger.Info(LogCategory.Import, $"Attempting to read files from {paths.Count} paths...");
		}

		GameStructure gameStructure = GameStructure.Load(paths, fileSystem, Settings, progress);
		GameData gameData = GameData.FromGameStructure(gameStructure);
		Logger.Info(LogCategory.Import, "Finished reading files");
		return gameData;
	}

	public GameData LoadPrimaryContent(
		IReadOnlyList<string> paths,
		FileSystem fileSystem,
		int concurrency,
		IGameLoadProgress? progress = null)
	{
		GameStructure gameStructure = GameStructure.LoadPrimaryContent(
			paths,
			fileSystem,
			Settings,
			progress,
			concurrency);
		return GameData.FromGameStructure(gameStructure);
	}

	public void Process(
		GameData gameData,
		Action<int, int, string>? progress = null)
	{
		Logger.Info(LogCategory.Processing, "Processing loaded assets...");
		IAssetProcessor[] processors = GetProcessors().ToArray();
		for (int index = 0; index < processors.Length; index++)
		{
			IAssetProcessor processor = processors[index];
			progress?.Invoke(index + 1, processors.Length, processor.GetType().Name);
			processor.Process(gameData);
		}
		Logger.Info(LogCategory.Processing, "Finished processing assets");
	}

	protected virtual IEnumerable<IAssetProcessor> GetProcessors()
	{
		yield return new SceneDefinitionProcessor();
		yield return new OriginalPathProcessor(Settings.ProcessingSettings.BundledAssetsExportMode);
		yield return new MainAssetProcessor();
		yield return new EditorFormatProcessor(Settings.ProcessingSettings.BundledAssetsExportMode);
		yield return new PrefabProcessor();
		yield return new SpriteProcessor();
	}

	public void Export(GameData gameData, string outputPath, FileSystem fileSystem)
	{
		Logger.Info(LogCategory.Export, "Starting export");
		Logger.Info(LogCategory.Export, $"Attempting to export assets to {outputPath}...");
		Logger.Info(LogCategory.Export, $"Game files have these Unity versions: {GetListOfVersions(gameData.GameBundle)}");
		Logger.Info(LogCategory.Export, $"Exporting to Unity version {gameData.ProjectVersion}");

		Settings.ExportRootPath = outputPath;
		Settings.SetProjectSettings(gameData.ProjectVersion);

		ProjectExporter projectExporter = new(Settings, gameData.AssemblyManager);
		BeforeExport(projectExporter);
		projectExporter.DoFinalOverrides(Settings);
		projectExporter.Export(gameData.GameBundle, Settings, fileSystem);

		Logger.Info(LogCategory.Export, "Finished exporting assets");

		foreach (IPostExporter postExporter in GetPostExporters())
		{
			postExporter.DoPostExport(gameData, Settings, fileSystem);
		}
		Logger.Info(LogCategory.Export, "Finished post-export");

		static string GetListOfVersions(GameBundle gameBundle)
		{
			return string.Join(' ', gameBundle
				.FetchAssetCollections()
				.Select(c => c.Version)
				.Distinct()
				.Select(v => v.ToString()));
		}
	}

	protected virtual void BeforeExport(ProjectExporter projectExporter)
	{
		// Needed for the premium edition
	}

	protected virtual IEnumerable<IPostExporter> GetPostExporters()
	{
		yield return new ProjectVersionPostExporter();
		yield return new PackageManifestPostExporter();
		yield return new StreamingAssetsPostExporter();
		yield return new DllPostExporter();
		yield return new PathIdMapExporter();
	}

	public GameData LoadAndProcess(IReadOnlyList<string> paths, FileSystem fileSystem)
	{
		GameData gameData = Load(paths, fileSystem);
		if (gameData.GameBundle.HasAnyAssetCollections())
		{
			Process(gameData);
		}
		return gameData;
	}

	public void LoadProcessAndExport(IReadOnlyList<string> inputPaths, string outputPath, FileSystem fileSystem)
	{
		GameData gameData = LoadAndProcess(inputPaths, fileSystem);
		Export(gameData, outputPath, fileSystem);
	}

	public void ThrowIfSettingsDontMatch(FullConfiguration settings)
	{
		if (Settings != settings)
		{
			throw new ArgumentException("Settings don't match");
		}
	}
}
