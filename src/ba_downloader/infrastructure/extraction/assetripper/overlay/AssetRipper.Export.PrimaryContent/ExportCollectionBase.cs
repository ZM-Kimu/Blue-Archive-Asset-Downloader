using AssetRipper.Assets;

namespace AssetRipper.Export.PrimaryContent;

public sealed record PlannedExport(string FilePath);

public abstract class ExportCollectionBase
{
	public abstract bool Contains(IUnityObjectBase asset);
	public abstract bool Export(string projectDirectory, FileSystem fileSystem);
	public virtual string GetPathSortKey(string projectDirectory, FileSystem fileSystem) => Name;
	public virtual PlannedExport PlanExport(string projectDirectory, FileSystem fileSystem) =>
		throw new NotSupportedException($"{GetType().Name} does not support planned export.");
	public virtual bool ExportPlanned(PlannedExport planned, string projectDirectory, FileSystem fileSystem) =>
		throw new NotSupportedException($"{GetType().Name} does not support planned export.");

	protected void ExportAsset(IUnityObjectBase asset, string path, string name, FileSystem fileSystem)
	{
		if (!fileSystem.Directory.Exists(path))
		{
			fileSystem.Directory.Create(path);
		}

		string fullName = $"{name}.{ExportExtension}";
		string uniqueName = fileSystem.GetUniqueName(path, fullName, FileSystem.MaxFileNameLength);
		string filePath = fileSystem.Path.Join(path, uniqueName);
		ContentExtractor.Export(asset, filePath, fileSystem);
	}

	protected string GetBaseFileName(IUnityObjectBase asset)
	{
		string fileName = asset.GetBestName();
		fileName = FileSystem.RemoveCloneSuffixes(fileName);
		fileName = FileSystem.RemoveInstanceSuffixes(fileName);
		fileName = fileName.Trim();
		if (string.IsNullOrEmpty(fileName))
		{
			fileName = asset.ClassName;
		}
		else
		{
			fileName = FileSystem.FixInvalidFileNameCharacters(fileName);
		}
		return $"{fileName}.{ExportExtension}";
	}

	protected string GetUniqueFileName(IUnityObjectBase asset, string dirPath, FileSystem fileSystem) =>
		GetUniqueFileName(dirPath, GetBaseFileName(asset), fileSystem);

	protected virtual string ExportExtension => "asset";

	protected static string GetUniqueFileName(string directoryPath, string fileName, FileSystem fileSystem)
	{
		return fileSystem.GetUniqueName(directoryPath, fileName, FileSystem.MaxFileNameLength);
	}

	public abstract IContentExtractor ContentExtractor { get; }
	public abstract IEnumerable<IUnityObjectBase> Assets { get; }
	public virtual IEnumerable<IUnityObjectBase> ExportableAssets => Assets;
	public virtual bool Exportable => true;
	public abstract string Name { get; }
}
