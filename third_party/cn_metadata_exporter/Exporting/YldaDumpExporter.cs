using System.Text;

namespace YldaDumpCsExporter;

internal sealed partial class YldaDumpExporter
{
    private const int WriterBufferSize = 1 << 20;

    private readonly ResolvedExportArtifact _artifact;
    private readonly PrivateMemberKinds _privateMembers;
    private readonly bool _methodAddressPlaceholders;

    public YldaDumpExporter(
        ResolvedExportArtifact artifact,
        PrivateMemberKinds privateMembers = PrivateMemberKinds.All,
        bool methodAddressPlaceholders = false)
    {
        _artifact = artifact;
        _privateMembers = privateMembers;
        _methodAddressPlaceholders = methodAddressPlaceholders;
    }

    public void Export(string outputPath, string? imageFilter = null, string? typeFilter = null)
    {
        var types = FilterTypes(imageFilter, typeFilter);
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);

        using var writer = new StreamWriter(outputPath, false, new UTF8Encoding(false), WriterBufferSize);
        writer.WriteLine("// CN custom metadata dump");
        writer.WriteLine($"// Baseline library: {_artifact.BaselineLibrary}");
        writer.WriteLine("// Special layers: CN restore + custom metadata parser + resolver-driven exporter");
        writer.WriteLine($"// Types exported: {types.Count}");
        writer.WriteLine($"// Private members: {FormatPrivateMemberKinds(_privateMembers)}");
        writer.WriteLine($"// Method address placeholders: {(_methodAddressPlaceholders ? "enabled" : "disabled")}");
        writer.WriteLine();

        string? currentImage = null;
        string? currentNamespace = null;
        var imageIndex = -1;

        foreach (var type in types)
        {
            if (!string.Equals(currentImage, type.ImageName, StringComparison.Ordinal))
            {
                currentImage = type.ImageName;
                imageIndex++;
                writer.WriteLine($"// Image {imageIndex}: {currentImage}");
            }

            if (!string.Equals(currentNamespace, type.NamespaceName, StringComparison.Ordinal))
            {
                currentNamespace = type.NamespaceName;
                writer.WriteLine($"// Namespace: {(currentNamespace == "<global>" ? "-" : currentNamespace)}");
            }

            WriteResolvedType(writer, type);
        }
    }

    private List<ResolvedExportTypeModel> FilterTypes(string? imageFilter, string? typeFilter)
    {
        IEnumerable<ResolvedExportTypeModel> types = _artifact.Types;

        if (!string.IsNullOrWhiteSpace(imageFilter))
        {
            types = types.Where(type => string.Equals(type.ImageName, imageFilter, StringComparison.OrdinalIgnoreCase));
        }

        if (!string.IsNullOrWhiteSpace(typeFilter))
            types = types.Where(type => type.FullName.Contains(typeFilter, StringComparison.OrdinalIgnoreCase));

        return types.ToList();
    }

    private static string FormatPrivateMemberKinds(PrivateMemberKinds kinds)
    {
        if (kinds == PrivateMemberKinds.All)
            return "all";
        if (kinds == PrivateMemberKinds.None)
            return "none";

        var values = new List<string>();
        if (kinds.HasFlag(PrivateMemberKinds.Fields))
            values.Add("fields");
        if (kinds.HasFlag(PrivateMemberKinds.Properties))
            values.Add("properties");
        if (kinds.HasFlag(PrivateMemberKinds.Events))
            values.Add("events");
        if (kinds.HasFlag(PrivateMemberKinds.Methods))
            values.Add("methods");
        return string.Join(",", values);
    }
}
