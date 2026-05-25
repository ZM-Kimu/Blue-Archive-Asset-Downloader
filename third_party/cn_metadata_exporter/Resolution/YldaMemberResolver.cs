using static YldaDumpCsExporter.YldaTypeNameHelpers;

namespace YldaDumpCsExporter;

internal sealed class YldaMemberResolver
{
    private readonly MetadataModel _model;
    private readonly YldaTypeResolver _typeResolver;
    private readonly YldaRelationshipResolver _relationshipResolver;
    private readonly TypeDescriptorIndex _descriptors;
    private readonly YldaPrimitiveMemberSignatureResolver _signatureResolver;
    private readonly YldaPropertyAccessorResolver _propertyResolver;
    private readonly YldaFlatBufferBuilderResolver _flatBufferBuilderResolver;
    private readonly YldaMemoryPackFormatterResolver _memoryPackFormatterResolver;
    private readonly YldaKnownFallbackResolver _knownFallbackResolver;

    public YldaMemberResolver(
        MetadataModel model,
        YldaTypeResolver typeResolver,
        YldaRelationshipResolver relationshipResolver,
        TypeDescriptorIndex descriptors)
    {
        _model = model;
        _typeResolver = typeResolver;
        _relationshipResolver = relationshipResolver;
        _descriptors = descriptors;

        var knownTypes = new YldaKnownTypeCatalog(model, typeResolver, relationshipResolver);
        _signatureResolver = new YldaPrimitiveMemberSignatureResolver(model, typeResolver, relationshipResolver, descriptors);
        _propertyResolver = new YldaPropertyAccessorResolver(model, typeResolver, relationshipResolver, descriptors);
        _flatBufferBuilderResolver = new YldaFlatBufferBuilderResolver(knownTypes);
        _memoryPackFormatterResolver = new YldaMemoryPackFormatterResolver(knownTypes);
        _knownFallbackResolver = new YldaKnownFallbackResolver(knownTypes);
    }

    public ResolvedTypeModel ResolveType(TypeDefinition type)
    {
        var methodRows = GetTypeMethods(type);
        var fieldRows = GetTypeFields(type);
        var typeNameMap = _typeResolver.CreateTypeNameMap(type, methodRows, fieldRows);
        var relationships = _relationshipResolver.ResolveTypeRelationships(type, methodRows, typeNameMap);
        var declaringType = _relationshipResolver.ResolveDeclaringType(type, typeNameMap);
        return ResolveType(type, typeNameMap, new RelationshipIndexEntry(
            type.Index,
            declaringType,
            relationships.BaseType,
            relationships.Interfaces.ToArray(),
            relationships.Comments.ToArray()));
    }

    public ResolvedTypeModel ResolveType(
        TypeDefinition type,
        IReadOnlyDictionary<uint, string> typeNameMap,
        RelationshipIndexEntry relationshipEntry)
    {
        var methodRows = GetTypeMethods(type);
        var fieldRows = GetTypeFields(type);
        var propertyRows = GetTypeProperties(type);
        var eventRows = GetTypeEvents(type);
        var declaringType = relationshipEntry.DeclaringType;
        var genericParameterNames = _signatureResolver.ResolveTypeGenericParameterNames(type);
        var relationships = new TypeRelationships(
            ApplyGenericContext(relationshipEntry.BaseType, genericParameterNames),
            relationshipEntry.Interfaces.Select(interfaceName => ApplyGenericContext(interfaceName, genericParameterNames) ?? interfaceName).ToArray(),
            relationshipEntry.Comments);
        var propertyTypeByName = _propertyResolver.BuildPropertyTypeByName(type, propertyRows, typeNameMap);

        var safeTypeName = FormatTypeDisplayName(type, genericParameterNames);
        var originalTypeName = string.Equals(safeTypeName, type.Name, StringComparison.Ordinal) ? null : type.Name;

        IReadOnlyList<ResolvedFieldModel> fields = _signatureResolver.ResolveFields(type, fieldRows, methodRows, propertyTypeByName, typeNameMap, declaringType)
            .Select(field => field with { TypeName = ApplyGenericContext(field.TypeName, genericParameterNames) ?? field.TypeName })
            .ToArray();
        IReadOnlyList<ResolvedPropertyModel> properties = _propertyResolver.ResolveProperties(type, propertyRows, methodRows, typeNameMap)
            .Select(property => property with { TypeName = ApplyGenericContext(property.TypeName, genericParameterNames) ?? property.TypeName })
            .ToArray();
        IReadOnlyList<ResolvedEventModel> events = _signatureResolver.ResolveEvents(type, eventRows, methodRows, typeNameMap)
            .Select(evt => evt with { TypeName = ApplyGenericContext(evt.TypeName, genericParameterNames) ?? evt.TypeName })
            .ToArray();
        IReadOnlyList<ResolvedMethodModel> methods = _signatureResolver.ResolveMethods(type, methodRows, typeNameMap)
            .Select(method => method with
            {
                ReturnTypeName = ApplyGenericContext(method.ReturnTypeName, genericParameterNames) ?? method.ReturnTypeName,
                Parameters = method.Parameters.Select(parameter => parameter with
                {
                    TypeName = ApplyGenericContext(parameter.TypeName, genericParameterNames) ?? parameter.TypeName,
                }).ToArray(),
            })
            .ToArray();

        var members = new YldaResolvedMemberSet(relationships, fields, properties, events, methods);
        members = _knownFallbackResolver.ApplyFutureLikeAdjustments(
            type,
            methodRows,
            genericParameterNames,
            members);

        members = _knownFallbackResolver.ApplyMxFieldFamilyAdjustments(
            type,
            members);

        members = _flatBufferBuilderResolver.ApplyFlatBufferTableAdjustments(
            type,
            members);

        members = _memoryPackFormatterResolver.ApplyMemoryPackAdjustments(
            type,
            safeTypeName,
            declaringType,
            members);

        members = _knownFallbackResolver.ApplyFieldBridgeAdjustments(
            type,
            declaringType,
            members);

        members = _knownFallbackResolver.ApplyReferenceModelAdjustments(
            type,
            safeTypeName,
            declaringType,
            members);

        return new ResolvedTypeModel(
            type,
            ImageForType(type.Index),
            string.IsNullOrEmpty(type.Namespace) ? "<global>" : type.Namespace,
            safeTypeName,
            originalTypeName,
            genericParameterNames,
            _relationshipResolver.ResolveTypeModifiers(type),
            declaringType,
            members.Relationships,
            members.Fields,
            members.Properties,
            members.Events,
            members.Methods);
    }

    private string ImageForType(int typeIndex)
        => typeIndex >= 0 && typeIndex < _model.Types.Count
            ? _descriptors.GetImageName(_model.Types[typeIndex])
            : "unknown";

    private MethodDefinition[] GetTypeMethods(TypeDefinition type) => _descriptors.GetMethods(type);
    private FieldDefinition[] GetTypeFields(TypeDefinition type) => _descriptors.GetFields(type);
    private PropertyDefinition[] GetTypeProperties(TypeDefinition type) => _descriptors.GetProperties(type);
    private EventDefinition[] GetTypeEvents(TypeDefinition type) => _descriptors.GetEvents(type);
}
