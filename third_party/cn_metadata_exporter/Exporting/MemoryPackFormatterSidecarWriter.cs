using System.Text;
using System.Text.Json;

namespace CnMetadataExporter;

internal static class MemoryPackFormatterSidecarWriter
{
    private const string FormatterBasePrefix = "MemoryPack.MemoryPackFormatter<";
    private const string MethodBodyReason = "Formatter method body analysis is not implemented by cn_metadata_exporter.";
    private const string UnionMappingReason = "Union tag mapping is unavailable from metadata-only exporter.";

    public static void Write(ResolvedExportArtifact artifact, string outputPath)
    {
        var formatters = artifact.Types
            .Select(TryBuildFormatter)
            .Where(formatter => formatter is not null)
            .Cast<Dictionary<string, object?>>()
            .ToArray();

        var fullPath = Path.GetFullPath(outputPath);
        Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
        var options = new JsonSerializerOptions { WriteIndented = true };
        File.WriteAllText(
            fullPath,
            JsonSerializer.Serialize(new { version = 1, formatters }, options),
            new UTF8Encoding(false));
    }

    private static Dictionary<string, object?>? TryBuildFormatter(
        ResolvedExportTypeModel type)
    {
        var targetType = ExtractFormatterTargetType(type.BaseType);
        if (string.IsNullOrWhiteSpace(targetType))
            return null;

        return targetType switch
        {
            "MX.AppData.DAO.Battle.SkillVisualDAO" => BuildSkillVisualFormatter(
                type,
                targetType),
            "MX.GameData.DAO.Battle.SkillLogicDAO" => BuildUnresolvedUnionFormatter(
                type,
                targetType),
            "MX.GameData.DAO.Battle.LogicEffectDAO" => BuildUnresolvedUnionFormatter(
                type,
                targetType),
            _ => BuildUnresolvedFormatter(type, targetType),
        };
    }

    private static Dictionary<string, object?> BuildSkillVisualFormatter(
        ResolvedExportTypeModel formatterType,
        string targetType)
    {
        return BuildBaseFormatter(formatterType, targetType)
            .With("kind", "object")
            .With("object_header", true)
            .With("members", new object[]
            {
                Member("name", "string"),
                Member("VisualDataKey", "string"),
                Member("GuidePrefabPath", "string"),
                Member("ActionEffects", "object[]"),
                Member("EntityEffects", "object[]"),
                Member("LogicEffectVisuals", "object[]"),
                Member("BattleItems", "object[]"),
                Member("ParticleEffectDatas", "object[]"),
            })
            .With("union_tags", new Dictionary<string, string>())
            .With("reason", "");
    }

    private static Dictionary<string, object?> BuildUnresolvedUnionFormatter(
        ResolvedExportTypeModel formatterType,
        string targetType)
    {
        return BuildBaseFormatter(formatterType, targetType)
            .With("kind", "union")
            .With("tag_type", "byte")
            .With("members", Array.Empty<object>())
            .With("union_tags", new Dictionary<string, string>())
            .With("reason", UnionMappingReason);
    }

    private static Dictionary<string, object?> BuildUnresolvedFormatter(
        ResolvedExportTypeModel formatterType,
        string targetType)
    {
        return BuildBaseFormatter(formatterType, targetType)
            .With("kind", "unresolved")
            .With("members", Array.Empty<object>())
            .With("union_tags", new Dictionary<string, string>())
            .With("reason", MethodBodyReason);
    }

    private static Dictionary<string, object?> BuildBaseFormatter(
        ResolvedExportTypeModel formatterType,
        string targetType)
    {
        var deserializeMethod = formatterType.Methods
            .FirstOrDefault(method => string.Equals(
                method.DisplayName,
                "Deserialize",
                StringComparison.Ordinal));

        return new Dictionary<string, object?>
        {
            ["target_type"] = targetType,
            ["formatter_type"] = BuildFormatterTypeName(formatterType),
            ["formatter_token"] = ToHex(formatterType.TypeToken),
            ["method_token"] = deserializeMethod.Token == 0
                ? ""
                : ToHex(deserializeMethod.Token),
            ["method_rva"] = "",
        };
    }

    private static Dictionary<string, object?> Member(string name, string csType)
    {
        return new Dictionary<string, object?>
        {
            ["name"] = name,
            ["cs_type"] = csType,
            ["source"] = "verified-cn-layout",
        };
    }

    private static string ExtractFormatterTargetType(string? baseType)
    {
        if (string.IsNullOrWhiteSpace(baseType))
            return "";
        if (!baseType.StartsWith(FormatterBasePrefix, StringComparison.Ordinal))
            return "";
        if (!baseType.EndsWith(">", StringComparison.Ordinal))
            return "";
        return baseType[FormatterBasePrefix.Length..^1];
    }

    private static string BuildFormatterTypeName(ResolvedExportTypeModel type)
    {
        if (!string.IsNullOrWhiteSpace(type.DeclaringType) &&
            !type.FullName.StartsWith(type.DeclaringType + ".", StringComparison.Ordinal))
        {
            return $"{type.DeclaringType}.{type.FullName}";
        }
        return type.FullName;
    }

    private static string ToHex(uint value) => $"0x{value:X8}";

    private static Dictionary<string, object?> With(
        this Dictionary<string, object?> formatter,
        string key,
        object? value)
    {
        formatter[key] = value;
        return formatter;
    }
}
