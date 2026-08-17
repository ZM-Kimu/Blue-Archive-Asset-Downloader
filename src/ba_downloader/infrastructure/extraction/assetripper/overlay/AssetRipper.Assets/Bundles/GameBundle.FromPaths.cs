using AssetRipper.Assets.Collections;
using AssetRipper.Assets.IO;
using AssetRipper.IO.Files;
using AssetRipper.IO.Files.CompressedFiles;
using AssetRipper.IO.Files.ResourceFiles;
using AssetRipper.IO.Files.SerializedFiles;
using AssetRipper.IO.Files.SerializedFiles.Parser;

namespace AssetRipper.Assets.Bundles;

partial class GameBundle
{
	/// <summary>
	/// Create and initialize a <see cref="GameBundle"/> from a set of paths.
	/// </summary>
	/// <param name="paths">The set of paths to load.</param>
	/// <param name="assetFactory">The factory for reading assets.</param>
	/// <param name="dependencyProvider"></param>
	/// <param name="resourceProvider"></param>
	/// <param name="defaultVersion">The default version to use if a file does not have a version, ie the version has been stripped.</param>
	public static GameBundle FromPaths(IEnumerable<string> paths, AssetFactoryBase assetFactory, FileSystem fileSystem, IGameInitializer? initializer = null)
	{
		GameBundle gameBundle = new();
		initializer?.OnCreated(gameBundle, assetFactory);
		gameBundle.InitializeFromPaths(paths, assetFactory, fileSystem, initializer);
		initializer?.OnPathsLoaded(gameBundle, assetFactory);
		gameBundle.InitializeAllDependencyLists(initializer?.DependencyProvider);
		initializer?.OnDependenciesInitialized(gameBundle, assetFactory);
		return gameBundle;
	}

	private void InitializeFromPaths(IEnumerable<string> paths, AssetFactoryBase assetFactory, FileSystem fileSystem, IGameInitializer? initializer)
	{
		ResourceProvider = initializer?.ResourceProvider;
		List<FileBase> fileStack = LoadFilesAndDependencies(paths, fileSystem, initializer);
		UnityVersion defaultVersion = initializer is null ? default : initializer.DefaultVersion;
		int total = fileStack.Count;
		int current = 0;

		while (fileStack.Count > 0)
		{
			switch (RemoveLastItem(fileStack))
			{
				case SerializedFile serializedFile:
					SerializedAssetCollection serializedCollection = SerializedAssetCollection.FromSerializedFile(this, serializedFile, assetFactory, defaultVersion);
					AssetProvenanceRegistry.RegisterCollection(serializedFile, serializedCollection);
					break;
				case FileContainer container:
					SerializedBundle serializedBundle = SerializedBundle.FromFileContainer(container, assetFactory, defaultVersion);
					AddBundle(serializedBundle);
					foreach (AssetCollection bundledCollection in serializedBundle.FetchAssetCollections())
					{
						AssetProvenanceRegistry.RegisterCollection(container, bundledCollection);
					}
					break;
				case ResourceFile resourceFile:
					AddResource(resourceFile);
					break;
				case FailedFile failedFile:
					AddFailed(failedFile);
					break;
			}
			current++;
			initializer?.LoadProgress?.Report(
				new GameLoadProgress(GameLoadProgressStage.CreatingCollections, current, total)
			);
		}
	}

	private static FileBase RemoveLastItem(List<FileBase> list)
	{
		int index = list.Count - 1;
		FileBase file = list[index];
		list.RemoveAt(index);
		return file;
	}

	private static List<FileBase> LoadFilesAndDependencies(IEnumerable<string> paths, FileSystem fileSystem, IGameInitializer? initializer)
	{
		List<string> inputPaths = paths as List<string> ?? paths.ToList();
		List<FileBase> files = new();
		HashSet<string> serializedFileNames = new();//Includes missing dependencies
		for (int i = 0; i < inputPaths.Count; i++)
		{
			string path = inputPaths[i];
			FileBase? file;
			try
			{
				file = SchemeReader.LoadFile(path, fileSystem);
				file.ReadContentsRecursively();
			}
			catch (Exception ex)
			{
				file = new FailedFile()
				{
					Name = fileSystem.Path.GetFileName(path),
					FilePath = path,
					StackTrace = ex.ToString(),
				};
			}
			while (file is CompressedFile compressedFile)
			{
				file = compressedFile.UncompressedFile;
			}
			if (file is not null)
			{
				AssetProvenanceRegistry.RegisterInput(file, path);
			}
			if (file is ResourceFile or FailedFile)
			{
				files.Add(file);
			}
			else if (file is SerializedFile serializedFile)
			{
				files.Add(file);
				serializedFileNames.Add(serializedFile.NameFixed);
			}
			else if (file is FileContainer container)
			{
				files.Add(file);
				foreach (SerializedFile serializedFileInContainer in container.FetchSerializedFiles())
				{
					serializedFileNames.Add(serializedFileInContainer.NameFixed);
				}
			}
			initializer?.LoadProgress?.Report(
				new GameLoadProgress(GameLoadProgressStage.LoadingFiles, i + 1, inputPaths.Count)
			);
		}

		int dependencyCurrent = 0;
		for (int i = 0; i < files.Count; i++)
		{
			FileBase file = files[i];
			if (file is SerializedFile serializedFile)
			{
				LoadDependencies(serializedFile, files, serializedFileNames, initializer?.DependencyProvider);
			}
			else if (file is FileContainer container)
			{
				foreach (SerializedFile serializedFileInContainer in container.FetchSerializedFiles())
				{
					LoadDependencies(serializedFileInContainer, files, serializedFileNames, initializer?.DependencyProvider);
				}
			}
			dependencyCurrent++;
			initializer?.LoadProgress?.Report(
				new GameLoadProgress(
					GameLoadProgressStage.ResolvingDependencies,
					dependencyCurrent,
					Math.Max(files.Count, dependencyCurrent)
				)
			);
		}

		return files;
	}

	private static void LoadDependencies(SerializedFile serializedFile, List<FileBase> files, HashSet<string> serializedFileNames, IDependencyProvider? dependencyProvider)
	{
		foreach (FileIdentifier fileIdentifier in serializedFile.Dependencies)
		{
			string name = fileIdentifier.GetFilePath();
			if (serializedFileNames.Add(name) && dependencyProvider?.FindDependency(fileIdentifier) is { } dependency)
			{
				files.Add(dependency);
			}
		}
	}
}
