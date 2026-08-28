using AssetRipper.Assets.Collections;
using AssetRipper.Assets.IO;
using AssetRipper.IO.Files;
using AssetRipper.IO.Files.CompressedFiles;
using AssetRipper.IO.Files.ResourceFiles;
using AssetRipper.IO.Files.SerializedFiles;

namespace AssetRipper.Assets.Bundles;

partial class GameBundle
{
	public static GameBundle FromPathsParallel(
		IReadOnlyList<string> paths,
		AssetFactoryBase assetFactory,
		FileSystem fileSystem,
		IGameInitializer? initializer,
		IGameLoadProgress? progress,
		int concurrency)
	{
		if (concurrency <= 0)
		{
			throw new ArgumentOutOfRangeException(nameof(concurrency));
		}
		GameBundle gameBundle = new();
		initializer?.OnCreated(gameBundle, assetFactory);
		gameBundle.ResourceProvider = initializer?.ResourceProvider;
		List<FileBase> files = LoadFilesAndDependenciesParallel(
			paths,
			fileSystem,
			initializer,
			progress,
			concurrency);
		gameBundle.InitializeFilesParallel(files, assetFactory, initializer, progress, concurrency);
		initializer?.OnPathsLoaded(gameBundle, assetFactory);
		BundleLookupIndex.Register(gameBundle);
		gameBundle.InitializeAllDependencyLists(initializer?.DependencyProvider);
		initializer?.OnDependenciesInitialized(gameBundle, assetFactory);
		return gameBundle;
	}

	private void InitializeFilesParallel(
		List<FileBase> files,
		AssetFactoryBase assetFactory,
		IGameInitializer? initializer,
		IGameLoadProgress? progress,
		int concurrency)
	{
		UnityVersion defaultVersion = initializer?.DefaultVersion ?? default;
		SerializedBundle?[] converted = new SerializedBundle?[files.Count];
		Parallel.For(
			0,
			files.Count,
			new ParallelOptions { MaxDegreeOfParallelism = concurrency },
			index =>
			{
				if (files[index] is FileContainer container)
				{
					converted[index] = SerializedBundle.FromFileContainer(
						container,
						assetFactory,
						defaultVersion);
				}
			});

		int current = 0;
		for (int index = files.Count - 1; index >= 0; index--)
		{
			FileBase file = files[index];
			switch (file)
			{
				case SerializedFile serializedFile:
					SerializedAssetCollection collection = SerializedAssetCollection.FromSerializedFile(
						this,
						serializedFile,
						assetFactory,
						defaultVersion);
					AssetProvenanceRegistry.RegisterCollection(serializedFile, collection);
					break;
				case FileContainer container:
					SerializedBundle bundle = converted[index]
						?? throw new InvalidDataException(
							"Parallel bundle conversion did not produce a result."
						);
					AddBundle(bundle);
					foreach (AssetCollection bundledCollection in bundle.FetchAssetCollections())
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
			progress?.Report(new GameLoadProgress(
				GameLoadProgressStage.CreatingCollections,
				current,
				files.Count));
		}
	}

	private static List<FileBase> LoadFilesAndDependenciesParallel(
		IReadOnlyList<string> inputPaths,
		FileSystem fileSystem,
		IGameInitializer? initializer,
		IGameLoadProgress? progress,
		int concurrency)
	{
		FileBase?[] loaded = new FileBase?[inputPaths.Count];
		int completed = 0;
		Parallel.For(
			0,
			inputPaths.Count,
			new ParallelOptions { MaxDegreeOfParallelism = concurrency },
			index =>
			{
				string path = inputPaths[index];
				FileBase? file;
				try
				{
					file = SchemeReader.LoadFile(path, fileSystem);
					file.ReadContentsRecursively();
				}
				catch (Exception exception)
				{
					file = new FailedFile
					{
						Name = fileSystem.Path.GetFileName(path),
						FilePath = path,
						StackTrace = exception.ToString(),
					};
				}
				while (file is CompressedFile compressedFile)
				{
					file = compressedFile.UncompressedFile;
				}
				loaded[index] = file;
				int current = Interlocked.Increment(ref completed);
				progress?.Report(new GameLoadProgress(
					GameLoadProgressStage.LoadingFiles,
					current,
					inputPaths.Count));
			});

		List<FileBase> files = [];
		HashSet<string> serializedFileNames = [];
		for (int index = 0; index < loaded.Length; index++)
		{
			FileBase? file = loaded[index];
			if (file is null)
			{
				continue;
			}
			AssetProvenanceRegistry.RegisterInput(file, inputPaths[index]);
			files.Add(file);
			if (file is SerializedFile serializedFile)
			{
				serializedFileNames.Add(serializedFile.NameFixed);
			}
			else if (file is FileContainer container)
			{
				foreach (SerializedFile child in container.FetchSerializedFiles())
				{
					serializedFileNames.Add(child.NameFixed);
				}
			}
		}

		int dependencyCurrent = 0;
		for (int index = 0; index < files.Count; index++)
		{
			FileBase file = files[index];
			if (file is SerializedFile serializedFile)
			{
				LoadDependencies(
					serializedFile,
					files,
					serializedFileNames,
					initializer?.DependencyProvider);
			}
			else if (file is FileContainer container)
			{
				foreach (SerializedFile child in container.FetchSerializedFiles())
				{
					LoadDependencies(
						child,
						files,
						serializedFileNames,
						initializer?.DependencyProvider);
				}
			}
			dependencyCurrent++;
			progress?.Report(new GameLoadProgress(
				GameLoadProgressStage.ResolvingDependencies,
				dependencyCurrent,
				Math.Max(files.Count, dependencyCurrent)));
		}
		return files;
	}
}
