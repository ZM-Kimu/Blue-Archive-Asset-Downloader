namespace CnMetadataExporter;

internal static class FlatBufferTypeRecovery
{
    private static readonly IReadOnlyDictionary<string, IReadOnlyDictionary<string, string>> KnownMemberElementTypes =
        new Dictionary<string, IReadOnlyDictionary<string, string>>(StringComparer.Ordinal)
        {
            ["FlatData.AnimatorData"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["DataList"] = "FlatData.AniStateData",
            },
            ["FlatData.AniStateData"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Events"] = "FlatData.AniEventData",
            },
            ["FlatData.AnimationBlendTable"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["DataList"] = "FlatData.BlendData",
            },
            ["FlatData.BlendData"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["InfoList"] = "FlatData.BlendInfo",
            },
            ["FlatData.GroundGridFlat"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Nodes"] = "FlatData.GroundNodeFlat",
            },
            ["FlatData.GroundGridFlatNew"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Nodes"] = "FlatData.GroundNodeFlatNew",
            },
            ["FlatData.GroundNodeFlat"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Position"] = "GroundVector3",
            },
            ["FlatData.GroundNodeFlatNew"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Position"] = "GroundVector3New",
            },
            ["FlatData.PropRootMotionFlat"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["RootMotions"] = "FlatData.PropMotion",
            },
            ["FlatData.PropMotion"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Positions"] = "FlatData.PropVector3",
                ["Rotations"] = "FlatData.PropVector3",
            },
            ["FlatData.RootMotionFlat"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Forms"] = "FlatData.Form",
                ["ExSkills"] = "FlatData.Motion",
                ["MoveLeft"] = "FlatData.Motion",
                ["MoveRight"] = "FlatData.Motion",
            },
            ["FlatData.Form"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["MoveEnd"] = "FlatData.MoveEnd",
                ["PublicSkill"] = "FlatData.Motion",
            },
            ["FlatData.MoveEnd"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Normal"] = "FlatData.Motion",
                ["Stand"] = "FlatData.Motion",
                ["Kneel"] = "FlatData.Motion",
            },
            ["FlatData.Motion"] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Positions"] = "FlatData.Position",
            },
        };

    public static string? ResolveMemberElementType(
        string declaringTypeFullName,
        string memberName,
        IReadOnlySet<string> typeFullNames)
    {
        if (KnownMemberElementTypes.TryGetValue(declaringTypeFullName, out var memberTypes) &&
            memberTypes.TryGetValue(memberName, out var knownType))
        {
            return typeFullNames.Contains(knownType) ? knownType : null;
        }

        return string.Equals(memberName, "DataList", StringComparison.OrdinalIgnoreCase)
            ? ResolveTableDataListElementType(declaringTypeFullName, typeFullNames)
            : null;
    }

    public static string? ResolveTableDataListElementType(
        string declaringTypeFullName,
        IReadOnlySet<string> typeFullNames)
    {
        if (!declaringTypeFullName.EndsWith("Table", StringComparison.Ordinal))
            return null;

        var candidate = declaringTypeFullName[..^"Table".Length];
        return typeFullNames.Contains(candidate) ? candidate : null;
    }

    public static string PreferFlatBufferType(
        string currentType,
        string desiredType,
        IReadOnlySet<string> typeFullNames)
    {
        if (string.IsNullOrWhiteSpace(desiredType))
            return currentType;
        if (IsWeakFlatBufferType(currentType) || ContainsMissingFlatDataType(currentType, typeFullNames))
            return desiredType;

        return currentType;
    }

    private static bool IsWeakFlatBufferType(string typeName)
        => string.IsNullOrWhiteSpace(typeName) ||
           typeName.Contains("Type_0x", StringComparison.Ordinal) ||
           string.Equals(typeName, "int", StringComparison.Ordinal) ||
           string.Equals(typeName, "long", StringComparison.Ordinal) ||
           string.Equals(typeName, "float", StringComparison.Ordinal) ||
           string.Equals(typeName, "System.Int32", StringComparison.Ordinal) ||
           string.Equals(typeName, "System.Int64", StringComparison.Ordinal) ||
           string.Equals(typeName, "System.Single", StringComparison.Ordinal);

    private static bool ContainsMissingFlatDataType(
        string typeName,
        IReadOnlySet<string> typeFullNames)
    {
        foreach (var token in ExtractTypeTokens(typeName))
        {
            if (token.StartsWith("FlatData.", StringComparison.Ordinal) &&
                !typeFullNames.Contains(token))
            {
                return true;
            }
        }

        return false;
    }

    private static IEnumerable<string> ExtractTypeTokens(string typeName)
    {
        var chars = typeName
            .Select(value => char.IsLetterOrDigit(value) || value is '_' or '.' ? value : ' ')
            .ToArray();
        return new string(chars).Split(' ', StringSplitOptions.RemoveEmptyEntries);
    }
}
