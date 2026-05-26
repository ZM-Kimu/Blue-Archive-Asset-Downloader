namespace CnMetadataExporter;

internal static class TypeNameHelpers
{
    public static string FormatTypeDisplayName(TypeDefinition type, IReadOnlyList<string> genericParameterNames)
    {
        var safeBaseName = ResolutionUtilities.SanitizeIdentifier(RemoveGenericAritySuffix(type.Name), $"type_{type.Index}");
        if (genericParameterNames.Count == 0)
            return safeBaseName;

        return $"{safeBaseName}<{string.Join(", ", genericParameterNames)}>";
    }

    public static string? ApplyGenericContext(string? typeName, IReadOnlyList<string> genericParameterNames)
    {
        if (string.IsNullOrWhiteSpace(typeName) || genericParameterNames.Count == 0)
            return typeName;
        if (typeName!.Contains('<', StringComparison.Ordinal))
            return typeName;

        var tickIndex = typeName.LastIndexOf('`');
        if (tickIndex <= 0 || tickIndex == typeName.Length - 1)
            return typeName;

        if (!int.TryParse(typeName[(tickIndex + 1)..], out var arity))
            return typeName;
        if (arity != genericParameterNames.Count)
            return typeName;

        return $"{typeName[..tickIndex]}<{string.Join(", ", genericParameterNames)}>";
    }

    public static string? BuildListType(string? elementType)
        => string.IsNullOrWhiteSpace(elementType) ? null : $"System.Collections.Generic.List<{elementType}>";

    public static string? BuildEnumerableType(string? elementType)
        => string.IsNullOrWhiteSpace(elementType) ? null : $"System.Collections.Generic.IEnumerable<{elementType}>";

    public static string? BuildIListType(string? elementType)
        => string.IsNullOrWhiteSpace(elementType) ? null : $"System.Collections.Generic.IList<{elementType}>";

    public static string? BuildArrayType(string? elementType)
        => string.IsNullOrWhiteSpace(elementType) ? null : $"{elementType}[]";

    public static string? BuildDictionaryType(string keyType, string? valueType)
        => string.IsNullOrWhiteSpace(valueType) ? null : $"System.Collections.Generic.Dictionary<{keyType}, {valueType}>";

    public static string? BuildClosedGenericType(string? genericTypeName, params string?[] argumentTypeNames)
    {
        if (string.IsNullOrWhiteSpace(genericTypeName) ||
            argumentTypeNames is null ||
            argumentTypeNames.Length == 0 ||
            argumentTypeNames.Any(string.IsNullOrWhiteSpace))
            return null;

        var tickIndex = genericTypeName!.LastIndexOf('`');
        var baseName = tickIndex > 0 ? genericTypeName[..tickIndex] : genericTypeName;
        return $"{baseName}<{string.Join(", ", argumentTypeNames!)}>";
    }

    public static string TypeKind(TypeDefinition type)
    {
        if ((type.Bitfield & 0x20) != 0)
            return "interface";
        if ((type.Bitfield & 0x2) != 0)
            return "enum";
        if ((type.Bitfield & 0x8) != 0)
            return "struct";
        return "class";
    }

    public static string PreferSpecificType(string currentType, string desiredType)
    {
        if (string.IsNullOrWhiteSpace(desiredType))
            return currentType;
        if (string.IsNullOrWhiteSpace(currentType) ||
            currentType.StartsWith("Type_0x", StringComparison.Ordinal) ||
            currentType == "int" ||
            currentType == "float")
        {
            return desiredType;
        }

        return currentType;
    }

    private static string RemoveGenericAritySuffix(string typeName)
    {
        var tickIndex = typeName.LastIndexOf('`');
        if (tickIndex <= 0 || tickIndex == typeName.Length - 1)
            return typeName;

        return int.TryParse(typeName[(tickIndex + 1)..], out _)
            ? typeName[..tickIndex]
            : typeName;
    }
}
