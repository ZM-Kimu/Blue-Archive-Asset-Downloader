namespace YldaDumpCsExporter;

internal abstract record CliCommand(bool Profile);

internal sealed record ExportCommand(
    string MetadataPath,
    string OutputPath,
    string? ImageFilter,
    string? TypeFilter,
    PrivateMemberKinds PrivateMembers,
    bool MethodAddressPlaceholders,
    string? RestoredMetadataOutputPath,
    uint KeyConstant,
    bool Profile) : CliCommand(Profile);

internal static class ExportOptions
{
    public static CliCommand Parse(string[] args)
        => ParseExport(args);

    public static void PrintUsage()
    {
        Console.WriteLine("Usage:");
        Console.WriteLine("  cn_metadata_exporter [--metadata PATH] [--output PATH] [--image DLL] [--type-filter TEXT] [--private-members all|none|fields,properties,events,methods] [--method-address-placeholders] [--restored-output PATH] [--key-constant 0xD96603C0] [--profile]");
    }

    private static ExportCommand ParseExport(string[] args)
    {
        var metadataPath = @"F:\cn_metadata\assets\bin\Data\Managed\Metadata\global-metadata.dat";
        var outputPath = @"C:\Users\Win10\Desktop\test_ba\artifacts\exports\cn_dump_cs_from_csharp.cs";
        string? imageFilter = null;
        string? typeFilter = null;
        var privateMembers = PrivateMemberKinds.All;
        var methodAddressPlaceholders = false;
        string? restoredMetadataOutputPath = null;
        var keyConstant = YldaMetadataRestorer.DefaultKeyConstant;
        var profile = false;

        for (var i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--metadata":
                    metadataPath = RequireValue(args, ref i);
                    break;
                case "--output":
                    outputPath = RequireValue(args, ref i);
                    break;
                case "--image":
                    imageFilter = RequireValue(args, ref i);
                    break;
                case "--type-filter":
                    typeFilter = RequireValue(args, ref i);
                    break;
                case "--private-members":
                    privateMembers = ParsePrivateMemberKinds(RequireValue(args, ref i));
                    break;
                case "--method-address-placeholders":
                    methodAddressPlaceholders = true;
                    break;
                case "--restored-output":
                case "--restored-metadata-output":
                    restoredMetadataOutputPath = RequireValue(args, ref i);
                    break;
                case "--key-constant":
                    keyConstant = ParseUInt32(RequireValue(args, ref i));
                    break;
                case "--profile":
                    profile = true;
                    break;
                case "--help":
                case "-h":
                    PrintUsage();
                    Environment.Exit(0);
                    break;
                default:
                    throw new ArgumentException($"Unknown argument: {args[i]}");
            }
        }

        return new ExportCommand(
            Path.GetFullPath(metadataPath),
            Path.GetFullPath(outputPath),
            imageFilter,
            typeFilter,
            privateMembers,
            methodAddressPlaceholders,
            restoredMetadataOutputPath is null ? null : Path.GetFullPath(restoredMetadataOutputPath),
            keyConstant,
            profile);
    }

    private static string RequireValue(string[] args, ref int index)
    {
        if (index + 1 >= args.Length)
            throw new ArgumentException($"Missing value after {args[index]}");
        index++;
        return args[index];
    }

    private static uint ParseUInt32(string text)
    {
        if (text.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
            return Convert.ToUInt32(text[2..], 16);
        return Convert.ToUInt32(text, 10);
    }

    private static PrivateMemberKinds ParsePrivateMemberKinds(string text)
    {
        if (string.Equals(text, "all", StringComparison.OrdinalIgnoreCase))
            return PrivateMemberKinds.All;
        if (string.Equals(text, "none", StringComparison.OrdinalIgnoreCase))
            return PrivateMemberKinds.None;

        var result = PrivateMemberKinds.None;
        foreach (var rawPart in text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            result |= rawPart.ToLowerInvariant() switch
            {
                "fields" => PrivateMemberKinds.Fields,
                "properties" => PrivateMemberKinds.Properties,
                "events" => PrivateMemberKinds.Events,
                "methods" => PrivateMemberKinds.Methods,
                _ => throw new ArgumentException($"Unknown private-member category: {rawPart}")
            };
        }

        return result;
    }
}
