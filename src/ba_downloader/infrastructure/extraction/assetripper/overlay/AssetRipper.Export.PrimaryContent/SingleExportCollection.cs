using AssetRipper.Assets;

namespace AssetRipper.Export.PrimaryContent;

public class SingleExportCollection<T> : ExportCollectionBase where T : IUnityObjectBase
{
	public SingleExportCollection(IContentExtractor contentExtractor, T asset)
	{
		ContentExtractor = contentExtractor ?? throw new ArgumentNullException(nameof(contentExtractor));
		Asset = asset ?? throw new ArgumentNullException(nameof(asset));
	}

	public override bool Export(string projectDirectory, FileSystem fileSystem)
	{
		PlannedExport planned = PlanExport(projectDirectory, fileSystem);
		bool succeeded = ExportPlanned(planned, projectDirectory, fileSystem);
		if (!succeeded && fileSystem.File.Exists(planned.FilePath))
		{
			fileSystem.File.Delete(planned.FilePath);
		}
		return succeeded;
	}

	public override string GetPathSortKey(string projectDirectory, FileSystem fileSystem)
	{
		string directory = FileSystem.FixInvalidPathCharacters(Asset.GetBestDirectory());
		return $"{directory.Replace('\\', '/')}\n{GetBaseFileName(Asset)}";
	}

	public override PlannedExport PlanExport(string projectDirectory, FileSystem fileSystem)
	{
		string subPath = fileSystem.Path.Join(
			projectDirectory,
			FileSystem.FixInvalidPathCharacters(Asset.GetBestDirectory()));
		fileSystem.Directory.Create(subPath);
		string fileName = GetUniqueFileName(Asset, subPath, fileSystem);
		string filePath = fileSystem.Path.Join(subPath, fileName);
		using (fileSystem.File.Create(filePath))
		{
		}
		return new PlannedExport(filePath);
	}

	public override bool ExportPlanned(PlannedExport planned, string projectDirectory, FileSystem fileSystem) =>
		ExportInner(planned.FilePath, projectDirectory, fileSystem);

	public override bool Contains(IUnityObjectBase asset) => Asset.AssetInfo == asset.AssetInfo;

	protected virtual bool ExportInner(string filePath, string dirPath, FileSystem fileSystem) =>
		ContentExtractor.Export(Asset, filePath, fileSystem);

	public override IContentExtractor ContentExtractor { get; }
	public override IEnumerable<IUnityObjectBase> Assets
	{
		get { yield return Asset; }
	}
	public override string Name => Asset.GetBestName();
	public T Asset { get; }
}
