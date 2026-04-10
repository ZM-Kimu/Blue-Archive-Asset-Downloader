namespace YldaDumpCsExporter;

internal sealed partial class YldaDumpExporter
{
    private void WriteResolvedType(StreamWriter writer, ResolvedExportTypeModel type)
    {
        var fields = FilterFields(type.Fields);
        var properties = FilterProperties(type.Properties);
        var events = FilterEvents(type.Events);
        var methods = FilterMethods(type.Methods);

        if (!string.IsNullOrWhiteSpace(type.OriginalTypeName))
            writer.WriteLine($"// OriginalTypeName: {type.OriginalTypeName}");
        if (!string.IsNullOrWhiteSpace(type.DeclaringType))
            writer.WriteLine($"// DeclaringType: {type.DeclaringType}");

        foreach (var comment in type.Comments)
            writer.WriteLine($"// {comment}");

        writer.WriteLine($"{BuildTypeDeclaration(type)} // TypeDefIndex: {type.TypeIndex}, Token: 0x{type.TypeToken:X8}");
        writer.WriteLine("{");

        WriteFields(writer, fields);
        WriteProperties(writer, properties);
        WriteEvents(writer, events);
        WriteMethods(writer, methods);

        writer.WriteLine("}");
        writer.WriteLine();
    }

    private static string BuildTypeDeclaration(ResolvedExportTypeModel type)
    {
        var parts = new List<string>(type.Modifiers) { type.SafeTypeName };
        var names = new List<string>();
        var isEnum = type.Modifiers.Contains("enum", StringComparer.Ordinal);
        var isStruct = type.Modifiers.Contains("struct", StringComparer.Ordinal);
        if (!string.IsNullOrWhiteSpace(type.BaseType) &&
            !(isEnum && string.Equals(type.BaseType, "System.Enum", StringComparison.Ordinal)) &&
            !(isStruct && string.Equals(type.BaseType, "System.ValueType", StringComparison.Ordinal)))
        {
            names.Add(type.BaseType!);
        }
        foreach (var interfaceName in type.Interfaces)
        {
            if (!names.Contains(interfaceName, StringComparer.Ordinal))
                names.Add(interfaceName);
        }

        if (names.Count > 0)
            parts.Add(": " + string.Join(", ", names));

        return string.Join(" ", parts);
    }

    private static void WriteFields(StreamWriter writer, IReadOnlyList<ResolvedExportFieldModel> fields)
    {
        if (fields.Count == 0)
            return;

        writer.WriteLine("    // Fields");
        foreach (var field in fields)
            writer.WriteLine($"    {FormatDeclaration(field.Modifiers, field.TypeName, field.Identifier)}; // Token: 0x{field.Token:X8}");
    }

    private static void WriteProperties(StreamWriter writer, IReadOnlyList<ResolvedExportPropertyModel> properties)
    {
        if (properties.Count == 0)
            return;

        writer.WriteLine("    // Properties");
        foreach (var property in properties)
        {
            writer.WriteLine(
                $"    {FormatDeclaration(property.Modifiers, property.TypeName, property.DisplayName)} {{ {string.Join(" ", property.Accessors)} }} // Token: 0x{property.Token:X8}");
        }
    }

    private static void WriteEvents(StreamWriter writer, IReadOnlyList<ResolvedExportEventModel> events)
    {
        if (events.Count == 0)
            return;

        writer.WriteLine("    // Events");
        foreach (var evt in events)
            writer.WriteLine($"    {FormatEventDeclaration(evt.Modifiers, evt.TypeName, evt.DisplayName)}; // Token: 0x{evt.Token:X8}");
    }

    private void WriteMethods(StreamWriter writer, IReadOnlyList<ResolvedExportMethodModel> methods)
    {
        if (methods.Count == 0)
            return;

        writer.WriteLine("    // Methods");
        foreach (var method in methods)
        {
            var parameters = method.Parameters.Select(parameter =>
                string.IsNullOrWhiteSpace(parameter.ModifierPrefix)
                    ? $"{parameter.TypeName} {parameter.Identifier}"
                    : $"{parameter.ModifierPrefix} {parameter.TypeName} {parameter.Identifier}");
            writer.WriteLine(BuildMethodMetadataComment(method));
            writer.WriteLine(
                $"    {FormatDeclaration(method.Modifiers, method.ReturnTypeName, method.DisplayName)}({string.Join(", ", parameters)}) {{ }}");
        }
    }

    private string BuildMethodMetadataComment(ResolvedExportMethodModel method)
    {
        if (_methodAddressPlaceholders)
        {
            var slotText = method.Slot == ushort.MaxValue ? "-1" : method.Slot.ToString();
            return $"    // RVA: 0x0 Offset: 0x0 VA: 0x0 Slot: {slotText} Token: 0x{method.Token:X8}";
        }

        return method.Slot == ushort.MaxValue
            ? $"    // Token: 0x{method.Token:X8}"
            : $"    // Slot: {method.Slot} Token: 0x{method.Token:X8}";
    }

    private static string FormatDeclaration(IReadOnlyList<string> modifiers, string typeName, string identifier)
    {
        var prefix = modifiers.Count == 0 ? string.Empty : string.Join(" ", modifiers) + " ";
        return $"{prefix}{typeName} {identifier}";
    }

    private static string FormatEventDeclaration(IReadOnlyList<string> modifiers, string typeName, string identifier)
    {
        var parts = new List<string>(modifiers.Count + 2);
        parts.AddRange(modifiers);
        parts.Add("event");
        parts.Add(typeName);
        parts.Add(identifier);
        return string.Join(" ", parts);
    }

    private List<ResolvedExportFieldModel> FilterFields(IReadOnlyList<ResolvedExportFieldModel> fields)
        => fields.Where(field => ShouldIncludePrivate(field.Accessibility, PrivateMemberKinds.Fields)).ToList();

    private List<ResolvedExportPropertyModel> FilterProperties(IReadOnlyList<ResolvedExportPropertyModel> properties)
        => properties.Where(property => ShouldIncludePrivate(property.Accessibility, PrivateMemberKinds.Properties)).ToList();

    private List<ResolvedExportEventModel> FilterEvents(IReadOnlyList<ResolvedExportEventModel> events)
        => events.Where(evt => ShouldIncludePrivate(evt.Accessibility, PrivateMemberKinds.Events)).ToList();

    private List<ResolvedExportMethodModel> FilterMethods(IReadOnlyList<ResolvedExportMethodModel> methods)
        => methods.Where(method => ShouldIncludePrivate(method.Accessibility, PrivateMemberKinds.Methods)).ToList();

    private bool ShouldIncludePrivate(ExportMemberAccessibility accessibility, PrivateMemberKinds category)
        => !YldaResolutionUtilities.IsExactPrivate(accessibility) || _privateMembers.HasFlag(category);
}
