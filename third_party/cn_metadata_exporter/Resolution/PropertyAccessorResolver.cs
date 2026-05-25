namespace CnMetadataExporter;

internal sealed class PropertyAccessorResolver
{
    private readonly MetadataModel _model;
    private readonly TypeResolver _typeResolver;
    private readonly RelationshipResolver _relationshipResolver;
    private readonly TypeDescriptorIndex _descriptors;

    public PropertyAccessorResolver(
        MetadataModel model,
        TypeResolver typeResolver,
        RelationshipResolver relationshipResolver,
        TypeDescriptorIndex descriptors)
    {
        _model = model;
        _typeResolver = typeResolver;
        _relationshipResolver = relationshipResolver;
        _descriptors = descriptors;
    }

    public IReadOnlyList<ResolvedPropertyModel> ResolveProperties(
        TypeDefinition type,
        IReadOnlyList<PropertyDefinition> rows,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var resolved = new List<ResolvedPropertyModel>(rows.Count);
        foreach (var property in rows)
        {
            var accessors = new List<string>();
            var propertyType = ResolvePropertyType(type, property, methodRows, typeNameMap);
            bool? confirmedOverride = null;

            if (property.GetterDelta != uint.MaxValue)
            {
                var getter = _model.Methods[type.FirstMethodIndex + (int)property.GetterDelta];
                accessors.Add("get;");
                confirmedOverride = MergeOverrideEvidence(confirmedOverride, _relationshipResolver.ResolveOverride(type, getter, typeNameMap));
            }

            if (property.SetterDelta != uint.MaxValue)
            {
                var setter = _model.Methods[type.FirstMethodIndex + (int)property.SetterDelta];
                accessors.Add("set;");
                confirmedOverride = MergeOverrideEvidence(confirmedOverride, _relationshipResolver.ResolveOverride(type, setter, typeNameMap));
            }

            resolved.Add(new ResolvedPropertyModel(
                property,
                property.Name,
                propertyType,
                _relationshipResolver.ResolvePropertyModifiers(type, property, confirmedOverride),
                _relationshipResolver.ResolvePropertyAccessibility(type, property),
                accessors));
        }

        return resolved;
    }

    public IReadOnlyDictionary<string, string> BuildPropertyTypeByName(
        TypeDefinition type,
        IReadOnlyList<PropertyDefinition> properties,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var propertyTypeByName = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var methodRows = _descriptors.GetMethods(type);
        var propertyTypeIndexByName = _descriptors.GetPropertyTypeIndices(type);
        foreach (var property in properties)
        {
            var propertyType = ResolvePropertyType(type, property, methodRows, typeNameMap, propertyTypeIndexByName);

            if (!string.IsNullOrWhiteSpace(propertyType))
                propertyTypeByName[property.Name] = propertyType;
        }

        return propertyTypeByName;
    }

    private string ResolvePropertyType(
        TypeDefinition type,
        PropertyDefinition property,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap,
        IReadOnlyDictionary<string, uint>? propertyTypeIndexByName = null)
    {
        propertyTypeIndexByName ??= _descriptors.GetPropertyTypeIndices(type);
        if (propertyTypeIndexByName.TryGetValue(property.Name, out var propertyTypeIndex))
            return _typeResolver.ResolveContextualTypeName(type, property.Name, propertyTypeIndex, methodRows, typeNameMap);

        return "Type_Unknown";
    }


    private static bool? MergeOverrideEvidence(bool? current, bool? next)
    {
        if (next == true)
            return true;
        return current ?? next;
    }
}
