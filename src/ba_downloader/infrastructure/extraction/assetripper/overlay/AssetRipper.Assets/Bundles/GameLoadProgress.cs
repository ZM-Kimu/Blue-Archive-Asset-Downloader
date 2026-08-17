namespace AssetRipper.Assets.Bundles;

public enum GameLoadProgressStage
{
	ExtractingInputs,
	LoadingFiles,
	CreatingCollections,
	ResolvingDependencies,
}

public readonly record struct GameLoadProgress(
	GameLoadProgressStage Stage,
	int Current,
	int Total
);

public interface IGameLoadProgress
{
	void Report(GameLoadProgress progress);
}
