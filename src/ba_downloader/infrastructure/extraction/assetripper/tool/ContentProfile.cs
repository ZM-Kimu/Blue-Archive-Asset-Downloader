using AssetRipper.Export.Configuration;
using AssetRipper.Processing;
using AssetRipper.Processing.Editor;
using AssetRipper.Processing.Prefabs;
using AssetRipper.Processing.Scenes;
using AssetRipper.Processing.Textures;

namespace Baad.AssetRipper;

internal static class ContentProfile
{
    public static IAssetProcessor[] CreateProcessors(FullConfiguration settings) =>
    [
        new SceneDefinitionProcessor(),
        new OriginalPathProcessor(
            settings.ProcessingSettings.BundledAssetsExportMode
        ),
        new MainAssetProcessor(),
        new EditorFormatProcessor(
            settings.ProcessingSettings.BundledAssetsExportMode,
            processAnimationClips: false
        ),
        new PrefabProcessor(),
        new SpriteProcessor(),
    ];
}
