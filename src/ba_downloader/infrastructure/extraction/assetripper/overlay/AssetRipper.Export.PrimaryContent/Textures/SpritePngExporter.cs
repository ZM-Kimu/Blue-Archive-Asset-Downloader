using AssetRipper.Assets;
using AssetRipper.Export.Configuration;
using AssetRipper.Export.Modules.Textures;
using AssetRipper.SourceGenerated.Classes.ClassID_213;

namespace AssetRipper.Export.PrimaryContent.Textures;

public sealed class SpritePngExporter : IContentExtractor
{
	public bool TryCreateCollection(IUnityObjectBase asset, [NotNullWhen(true)] out ExportCollectionBase? exportCollection)
	{
		if (asset is ISprite sprite && SpriteConverter.Supported(sprite))
		{
			exportCollection = new SpriteExportCollection(this, sprite);
			return true;
		}
		exportCollection = null;
		return false;
	}

	public bool Export(IUnityObjectBase asset, string path, FileSystem fileSystem)
	{
		if (!SpriteConverter.TryConvertToBitmap((ISprite)asset, out DirectBitmap bitmap))
		{
			return false;
		}
		using Stream stream = fileSystem.File.Create(path);
		bitmap.Save(stream, ImageExportFormat.Png);
		return true;
	}

	private sealed class SpriteExportCollection(IContentExtractor extractor, ISprite asset)
		: SingleExportCollection<ISprite>(extractor, asset)
	{
		protected override string ExportExtension => "png";
	}
}
