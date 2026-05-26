using static CnMetadataExporter.TypeNameHelpers;

namespace CnMetadataExporter;

internal sealed class MemberResolver
{
    private readonly MetadataModel _model;
    private readonly TypeResolver _typeResolver;
    private readonly RelationshipResolver _relationshipResolver;
    private readonly TypeDescriptorIndex _descriptors;
    private readonly PrimitiveMemberSignatureResolver _signatureResolver;
    private readonly PropertyAccessorResolver _propertyResolver;
    private readonly FlatBufferBuilderResolver _flatBufferBuilderResolver;
    private readonly MemoryPackFormatterResolver _memoryPackFormatterResolver;
    private readonly KnownFallbackResolver _knownFallbackResolver;

    public MemberResolver(
        MetadataModel model,
        TypeResolver typeResolver,
        RelationshipResolver relationshipResolver,
        TypeDescriptorIndex descriptors)
    {
        _model = model;
        _typeResolver = typeResolver;
        _relationshipResolver = relationshipResolver;
        _descriptors = descriptors;

        var knownTypes = new KnownTypeCatalog(model, typeResolver, relationshipResolver);
        _signatureResolver = new PrimitiveMemberSignatureResolver(model, typeResolver, relationshipResolver, descriptors);
        _propertyResolver = new PropertyAccessorResolver(model, typeResolver, relationshipResolver, descriptors);
        _flatBufferBuilderResolver = new FlatBufferBuilderResolver(knownTypes);
        _memoryPackFormatterResolver = new MemoryPackFormatterResolver(knownTypes);
        _knownFallbackResolver = new KnownFallbackResolver(knownTypes);
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

        var members = new ResolvedMemberSet(relationships, fields, properties, events, methods);
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
