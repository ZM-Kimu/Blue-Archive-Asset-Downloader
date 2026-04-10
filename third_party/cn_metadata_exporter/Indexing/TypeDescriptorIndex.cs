namespace YldaDumpCsExporter;

internal sealed record TypeDescriptorIndex(
    Dictionary<int, MethodDefinition[]> MethodsByType,
    Dictionary<int, FieldDefinition[]> FieldsByType,
    Dictionary<int, PropertyDefinition[]> PropertiesByType,
    Dictionary<int, EventDefinition[]> EventsByType,
    Dictionary<int, ParameterDefinition[]> MethodParametersByMethodIndex,
    Dictionary<int, Dictionary<string, uint>> PropertyTypeIndicesByType,
    Dictionary<int, string> ImageNameByType,
    Dictionary<int, uint[]> ReferencedTypeIndicesByType,
    Dictionary<int, TypeDescriptorHints> HintsByType)
{
    public MethodDefinition[] GetMethods(TypeDefinition type)
        => MethodsByType.GetValueOrDefault(type.Index) ?? [];

    public FieldDefinition[] GetFields(TypeDefinition type)
        => FieldsByType.GetValueOrDefault(type.Index) ?? [];

    public PropertyDefinition[] GetProperties(TypeDefinition type)
        => PropertiesByType.GetValueOrDefault(type.Index) ?? [];

    public EventDefinition[] GetEvents(TypeDefinition type)
        => EventsByType.GetValueOrDefault(type.Index) ?? [];

    public ParameterDefinition[] GetParameters(MethodDefinition method)
        => MethodParametersByMethodIndex.GetValueOrDefault(method.Index) ?? [];

    public IReadOnlyDictionary<string, uint> GetPropertyTypeIndices(TypeDefinition type)
        => PropertyTypeIndicesByType.GetValueOrDefault(type.Index) ?? EmptyPropertyTypeIndices;

    public string GetImageName(TypeDefinition type)
        => ImageNameByType.GetValueOrDefault(type.Index) ?? "unknown";

    public IReadOnlyList<uint> GetReferencedTypeIndices(TypeDefinition type)
        => ReferencedTypeIndicesByType.GetValueOrDefault(type.Index) ?? EmptyReferencedTypeIndices;

    public TypeDescriptorHints GetHints(TypeDefinition type)
        => HintsByType.GetValueOrDefault(type.Index);

    private static readonly IReadOnlyDictionary<string, uint> EmptyPropertyTypeIndices =
        new Dictionary<string, uint>(StringComparer.OrdinalIgnoreCase);

    private static readonly IReadOnlyList<uint> EmptyReferencedTypeIndices = [];
}

internal readonly record struct TypeDescriptorHints(
    bool RequiresLocalTypeInference,
    bool HasExplicitInterfaces,
    bool HasFlatBufferAssignOrRoot,
    bool HasByteBufferAccessor,
    bool HasInitKeyMethod,
    bool HasCollectionLikeMembers,
    bool IsTableLike,
    bool IsKnownLocalInferenceType);
