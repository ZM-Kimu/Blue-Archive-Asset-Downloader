using System.Text;

namespace YldaDumpCsExporter;

internal static class YldaResolutionUtilities
{
    public static string FormatType(uint typeIndex, IReadOnlyDictionary<uint, string> typeNameMap, string? fallback = null)
    {
        if (typeNameMap.TryGetValue(typeIndex, out var name))
            return SimplifyTypeName(name);
        if (!string.IsNullOrWhiteSpace(fallback))
            return SimplifyTypeName(fallback!);
        return $"Type_0x{typeIndex:X8}";
    }

    public static bool IsPrimitiveOrVoidTypeName(string? typeName)
    {
        if (string.IsNullOrWhiteSpace(typeName))
            return false;

        var normalized = NormalizeTypeCandidate(typeName!);
        return normalized is
            "System.Void" or
            "System.Boolean" or
            "System.Int32" or
            "System.UInt32" or
            "System.Int64" or
            "System.UInt64" or
            "System.Int16" or
            "System.UInt16" or
            "System.Byte" or
            "System.SByte" or
            "System.Char" or
            "System.Single" or
            "System.Double" or
            "System.Decimal" or
            "System.IntPtr" or
            "System.UIntPtr" or
            "void" or
            "bool" or
            "int" or
            "uint" or
            "long" or
            "ulong" or
            "short" or
            "ushort" or
            "byte" or
            "sbyte" or
            "char" or
            "float" or
            "double" or
            "decimal" or
            "nint" or
            "nuint";
    }

    public static bool LooksLikeReferenceSemanticName(string? memberName)
    {
        if (string.IsNullOrWhiteSpace(memberName))
            return false;

        if (memberName.StartsWith("Is", StringComparison.Ordinal) ||
            memberName.StartsWith("Has", StringComparison.Ordinal) ||
            memberName.StartsWith("Can", StringComparison.Ordinal) ||
            memberName.StartsWith("Need", StringComparison.Ordinal) ||
            memberName.StartsWith("Should", StringComparison.Ordinal) ||
            memberName.StartsWith("Use", StringComparison.Ordinal) ||
            memberName.StartsWith("Allow", StringComparison.Ordinal) ||
            memberName.StartsWith("Enable", StringComparison.Ordinal) ||
            memberName.StartsWith("Disable", StringComparison.Ordinal))
        {
            return false;
        }

        return memberName.Contains("Url", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("Root", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("Path", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("Name", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("File", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("Catalog", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("Manifest", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("Version", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("Callback", StringComparison.OrdinalIgnoreCase) ||
               memberName.Contains("Message", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(memberName, "Msg", StringComparison.OrdinalIgnoreCase);
    }

    public static bool TrySingularizeCollectionName(string? memberName, out string singularName)
    {
        singularName = string.Empty;
        if (string.IsNullOrWhiteSpace(memberName) || memberName!.Length < 2)
            return false;

        if (memberName.EndsWith("ies", StringComparison.Ordinal))
        {
            singularName = memberName[..^3] + "y";
            return true;
        }

        foreach (var suffix in new[] { "Urls", "Roots", "Paths", "Files", "Names", "Ids", "Values" })
        {
            if (!memberName.EndsWith(suffix, StringComparison.Ordinal))
                continue;

            singularName = memberName[..^1];
            return true;
        }

        if (memberName.EndsWith('s') && !memberName.EndsWith("ss", StringComparison.Ordinal))
        {
            singularName = memberName[..^1];
            return true;
        }

        return false;
    }

    public static string? ExplicitInterfacePrefix(string methodName)
    {
        if (!methodName.Contains('.') || methodName.StartsWith('<'))
            return null;

        var split = methodName.LastIndexOf('.');
        if (split <= 0)
            return null;

        var prefix = methodName[..split];
        var suffix = methodName[(split + 1)..];
        if (suffix.StartsWith("get_", StringComparison.Ordinal) ||
            suffix.StartsWith("set_", StringComparison.Ordinal) ||
            suffix.StartsWith("add_", StringComparison.Ordinal) ||
            suffix.StartsWith("remove_", StringComparison.Ordinal))
            return prefix;

        if (prefix.StartsWith("System.", StringComparison.Ordinal) ||
            prefix.StartsWith("UnityEngine.", StringComparison.Ordinal) ||
            prefix.StartsWith("TMPro.", StringComparison.Ordinal) ||
            prefix.StartsWith("MX.", StringComparison.Ordinal) ||
            prefix.StartsWith("Newtonsoft.", StringComparison.Ordinal) ||
            prefix.StartsWith("BestHTTP.", StringComparison.Ordinal) ||
            prefix.StartsWith("Cysharp.", StringComparison.Ordinal) ||
            prefix.StartsWith("FlatBuffers.", StringComparison.Ordinal))
            return prefix;

        if (prefix.Contains('<') && prefix.Contains('>'))
            return prefix;

        return null;
    }

    public static ExportMemberAccessibility MethodAccessibility(ushort flags) => (flags & YldaResolutionConstants.MethodAttrMemberAccessMask) switch
    {
        YldaResolutionConstants.MethodAttrPrivate => ExportMemberAccessibility.Private,
        YldaResolutionConstants.MethodAttrFamAndAssem => ExportMemberAccessibility.PrivateProtected,
        YldaResolutionConstants.MethodAttrAssembly => ExportMemberAccessibility.Internal,
        YldaResolutionConstants.MethodAttrFamily => ExportMemberAccessibility.Protected,
        YldaResolutionConstants.MethodAttrFamOrAssem => ExportMemberAccessibility.ProtectedInternal,
        YldaResolutionConstants.MethodAttrPublic => ExportMemberAccessibility.Public,
        _ => ExportMemberAccessibility.Private,
    };

    public static string MethodAccessModifier(ushort flags) => AccessibilityModifier(MethodAccessibility(flags));

    public static string AccessibilityModifier(ExportMemberAccessibility accessibility) => accessibility switch
    {
        ExportMemberAccessibility.Private => "private",
        ExportMemberAccessibility.PrivateProtected => "private protected",
        ExportMemberAccessibility.Internal => "internal",
        ExportMemberAccessibility.Protected => "protected",
        ExportMemberAccessibility.ProtectedInternal => "protected internal",
        ExportMemberAccessibility.Public => "public",
        _ => string.Empty,
    };

    public static int AccessModifierRank(string modifier) => modifier switch
    {
        "private" => 0,
        "private protected" => 1,
        "internal" => 2,
        "protected" => 3,
        "protected internal" => 4,
        "public" => 5,
        _ => -1,
    };

    public static bool IsExactPrivate(ExportMemberAccessibility accessibility)
        => accessibility == ExportMemberAccessibility.Private;

    public static IEnumerable<string> ExpandMemberNameKeys(string memberName, string typeName)
    {
        if (string.IsNullOrWhiteSpace(memberName))
            yield break;

        yield return memberName;

        if (typeName is "FlatBuffers.StringOffset" or "FlatBuffers.VectorOffset")
            yield return memberName + "Offset";

        if (memberName.EndsWith("Offset", StringComparison.Ordinal))
            yield return memberName[..^"Offset".Length];
    }

    public static string? ConventionalPropertyCandidate(string fieldName)
    {
        if (string.IsNullOrWhiteSpace(fieldName))
            return null;

        if (fieldName[0] == '_' && fieldName.Length > 1)
            return char.ToUpperInvariant(fieldName[1]) + fieldName[2..];

        if (fieldName[0] == 'm' && fieldName.Length > 1 && char.IsUpper(fieldName[1]))
            return fieldName[1..];

        if (char.IsLower(fieldName[0]) &&
            fieldName.Length > 1 &&
            fieldName.Skip(1).Any(char.IsUpper))
        {
            return char.ToUpperInvariant(fieldName[0]) + fieldName[1..];
        }

        return null;
    }

    public static string? BackingFieldPropertyName(string fieldName)
    {
        const string angleSuffix = ">k__BackingField";
        const string underscoreSuffix = "_k__BackingField";

        if (fieldName.StartsWith('<') && fieldName.EndsWith(angleSuffix, StringComparison.Ordinal))
            return fieldName[1..^angleSuffix.Length];

        if (fieldName.StartsWith('_') && fieldName.EndsWith(underscoreSuffix, StringComparison.Ordinal))
            return fieldName[1..^underscoreSuffix.Length];

        return null;
    }

    public static IReadOnlyList<ParameterDefinition> GetMethodParameters(MethodDefinition method, IReadOnlyList<ParameterDefinition> parameters)
    {
        if (method.ParameterStart == uint.MaxValue || method.ParameterCount == 0)
            return [];

        var items = new List<ParameterDefinition>(method.ParameterCount);
        for (var idx = 0; idx < method.ParameterCount; idx++)
            items.Add(parameters[(int)method.ParameterStart + idx]);
        return items;
    }

    public static string MethodContractKey(
        MethodDefinition method,
        IReadOnlyList<ParameterDefinition> parameters,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var parameterTypes = GetMethodParameters(method, parameters)
            .Select(parameter => FormatType(parameter.TypeIndex, typeNameMap))
            .ToArray();
        return string.Join("\u001F", [method.Name, FormatType(method.ReturnTypeIndex, typeNameMap), string.Join("\u001E", parameterTypes)]);
    }

    public static string MethodContractKeyForResolvedParameters(
        MethodDefinition method,
        IReadOnlyList<ParameterDefinition> methodParameters,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var parameterTypes = methodParameters
            .Select(parameter => FormatType(parameter.TypeIndex, typeNameMap))
            .ToArray();
        return string.Join("\u001F", [method.Name, FormatType(method.ReturnTypeIndex, typeNameMap), string.Join("\u001E", parameterTypes)]);
    }

    public static IEnumerable<string> ExpandedMethodContractKeys(
        MethodDefinition method,
        IReadOnlyList<ParameterDefinition> parameters,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var key = MethodContractKey(method, parameters, typeNameMap);
        yield return key;

        if (method.Name.Contains('.') && !method.Name.StartsWith('<'))
        {
            var parts = key.Split("\u001F");
            if (parts.Length == 3)
                yield return string.Join("\u001F", [method.Name[(method.Name.LastIndexOf('.') + 1)..], parts[1], parts[2]]);
        }
    }

    public static IEnumerable<string> ExpandedMethodContractKeysForResolvedParameters(
        MethodDefinition method,
        IReadOnlyList<ParameterDefinition> methodParameters,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var key = MethodContractKeyForResolvedParameters(method, methodParameters, typeNameMap);
        yield return key;

        if (method.Name.Contains('.') && !method.Name.StartsWith('<'))
        {
            var parts = key.Split("\u001F");
            if (parts.Length == 3)
                yield return string.Join("\u001F", [method.Name[(method.Name.LastIndexOf('.') + 1)..], parts[1], parts[2]]);
        }
    }

    public static (string BaseName, IReadOnlyList<string> Args)? ParseGenericType(string typeName)
    {
        var text = typeName.Trim();
        var lt = text.IndexOf('<');
        var gt = text.LastIndexOf('>');
        if (lt < 0 || gt < lt)
            return null;

        var baseName = text[..lt].Trim();
        var args = SplitTopLevelCommas(text[(lt + 1)..gt]);
        return (baseName, args);
    }

    public static IReadOnlyList<string> SplitTopLevelCommas(string text)
    {
        var parts = new List<string>();
        var current = new StringBuilder();
        var depth = 0;
        foreach (var ch in text)
        {
            switch (ch)
            {
                case '<':
                    depth++;
                    current.Append(ch);
                    break;
                case '>':
                    depth = Math.Max(0, depth - 1);
                    current.Append(ch);
                    break;
                case ',' when depth == 0:
                    var part = current.ToString().Trim();
                    if (!string.IsNullOrEmpty(part))
                        parts.Add(part);
                    current.Clear();
                    break;
                default:
                    current.Append(ch);
                    break;
            }
        }

        var tail = current.ToString().Trim();
        if (!string.IsNullOrEmpty(tail))
            parts.Add(tail);
        return parts;
    }

    public static string? ChooseTypeName(IEnumerable<string> candidates)
    {
        var normalized = candidates
            .Where(candidate => !string.IsNullOrWhiteSpace(candidate))
            .Select(NormalizeTypeCandidate)
            .Distinct(StringComparer.Ordinal)
            .OrderBy(name => name, StringComparer.Ordinal)
            .ToArray();
        if (normalized.Length == 0)
            return null;

        foreach (var pair in YldaResolutionConstants.SystemAliases)
        {
            if (normalized.Contains(pair.Key))
                return pair.Value;
        }

        var pool = normalized.Where(name => !name.EndsWith("Enum", StringComparison.Ordinal)).ToArray();
        if (pool.Length == 0)
            pool = normalized;

        var chosen = pool
            .OrderBy(name => name.StartsWith("System.", StringComparison.Ordinal) ? 0 : 1)
            .ThenBy(name => name.Count(ch => ch is '`' or '+'))
            .ThenBy(name => name, StringComparer.Ordinal)
            .FirstOrDefault();

        return chosen is null ? null : YldaResolutionConstants.SystemAliases.GetValueOrDefault(chosen, chosen);
    }

    public static string NormalizeTypeCandidate(string candidate)
    {
        if (string.IsNullOrWhiteSpace(candidate))
            return candidate;

        if (YldaResolutionConstants.AliasToSystemType.TryGetValue(candidate, out var fullName))
            return fullName;

        if (candidate.EndsWith("[]", StringComparison.Ordinal))
        {
            var elementName = candidate[..^2];
            if (YldaResolutionConstants.AliasToSystemType.TryGetValue(elementName, out var fullElementName))
                return fullElementName + "[]";
        }

        return candidate;
    }

    public static string SimplifyTypeName(string typeName)
    {
        var current = typeName;
        foreach (var pair in YldaResolutionConstants.SystemAliases.OrderByDescending(pair => pair.Key.Length))
            current = current.Replace(pair.Key, pair.Value, StringComparison.Ordinal);
        return current;
    }

    public static string SanitizeIdentifier(string name, string fallback)
    {
        if (string.IsNullOrWhiteSpace(name))
            return fallback;

        var builder = new StringBuilder(name.Length);
        foreach (var ch in name)
            builder.Append(char.IsLetterOrDigit(ch) || ch == '_' ? ch : '_');

        if (builder.Length == 0)
            builder.Append(fallback);
        if (char.IsDigit(builder[0]))
            builder.Insert(0, '_');
        return builder.ToString();
    }
}
