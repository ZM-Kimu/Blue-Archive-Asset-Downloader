using System.Text.Json;
using AssetRipper.Assets;
using AssetRipper.Assets.Bundles;
using AssetRipper.Import.Configuration;
using AssetRipper.Import.AssetCreation;
using AssetRipper.Import.Structure;
using AssetRipper.IO.Files;
using AssetRipper.SourceGenerated.Classes.ClassID_49;

if (args.Length != 2)
{
    Console.Error.WriteLine(
        "Usage: AssetRipperRuntimeInspector <request.json> <result.json>"
    );
    return 2;
}

string requestPath = Path.GetFullPath(args[0]);
string resultPath = Path.GetFullPath(args[1]);
try
{
    InspectionRequest request = JsonSerializer.Deserialize<InspectionRequest>(
        File.ReadAllText(requestPath),
        JsonOptions.Default
    ) ?? throw new InvalidDataException("Runtime inspection request is empty.");
    request.Validate();

    CoreConfiguration settings = new();
    using GameStructure gameStructure = GameStructure.Load(
        request.Inputs.Select(Path.GetFullPath),
        LocalFileSystem.Instance,
        settings
    );
    InspectionResult result = InspectRuntime(gameStructure.FileCollection);
    WriteResult(resultPath, result);
    return 0;
}
catch (Exception exception)
{
    WriteResult(
        resultPath,
        new InspectionResult(
            false,
            $"{exception.GetType().Name}: {exception.Message}",
            null,
            null
        )
    );
    Console.Error.WriteLine(exception);
    return 1;
}

static InspectionResult InspectRuntime(GameBundle gameBundle)
{
    ITextAsset? config = null;
    TypeTreeObject? playerSettings = null;
    foreach (IUnityObjectBase asset in gameBundle.FetchAssets())
    {
        if (
            config is null
            && asset is ITextAsset textAsset
            && textAsset.GetBestName() == "GameMainConfig"
        )
        {
            config = textAsset;
        }
        if (
            playerSettings is null
            && asset is TypeTreeObject typeTree
            && typeTree.IsPlayerSettings
        )
        {
            playerSettings = typeTree;
        }
        if (config is not null && playerSettings is not null)
        {
            break;
        }
    }
    if (config is null)
    {
        throw new InvalidDataException("GameMainConfig TextAsset was not found.");
    }

    string? bundleVersion = null;
    if (playerSettings is not null)
    {
        var fields = playerSettings.ReleaseFields;
        if (fields.ContainsField("bundleVersion"))
        {
            bundleVersion = fields["bundleVersion"].AsString;
        }
    }
    return new InspectionResult(
        true,
        null,
        Convert.ToBase64String(config.Script_C49.Data),
        bundleVersion
    );
}

static void WriteResult(string resultPath, InspectionResult result)
{
    Directory.CreateDirectory(Path.GetDirectoryName(resultPath)!);
    string temporaryPath = resultPath + ".tmp";
    File.WriteAllText(
        temporaryPath,
        JsonSerializer.Serialize(result, JsonOptions.Default)
    );
    File.Move(temporaryPath, resultPath, true);
}

internal sealed record InspectionRequest(string Operation, List<string> Inputs)
{
    public void Validate()
    {
        if (Operation != "inspect_jp_runtime")
        {
            throw new InvalidDataException(
                $"Unsupported runtime inspection operation: {Operation}"
            );
        }
        if (Inputs.Count != 1 || string.IsNullOrWhiteSpace(Inputs[0]))
        {
            throw new InvalidDataException(
                "Runtime inspection requires exactly one input directory."
            );
        }
        string inputPath = Path.GetFullPath(Inputs[0]);
        if (!Directory.Exists(inputPath))
        {
            throw new DirectoryNotFoundException(
                $"Runtime inspection input directory was not found: {inputPath}"
            );
        }
    }
}

internal sealed record InspectionResult(
    bool Succeeded,
    string? Error,
    string? GameMainConfigBase64,
    string? BundleVersion
);

internal static class JsonOptions
{
    public static readonly JsonSerializerOptions Default = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
    };
}
