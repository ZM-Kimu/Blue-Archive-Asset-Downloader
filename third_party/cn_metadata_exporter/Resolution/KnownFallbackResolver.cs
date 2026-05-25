namespace CnMetadataExporter;

internal sealed class KnownFallbackResolver
{
    private readonly MxFieldFamilyResolver _mxFieldFamilyResolver;
    private readonly FutureLikeResolver _futureLikeResolver;
    private readonly FieldBridgeResolver _fieldBridgeResolver;
    private readonly ReferenceModelResolver _referenceModelResolver;

    public KnownFallbackResolver(KnownTypeCatalog knownTypes)
    {
        _mxFieldFamilyResolver = new MxFieldFamilyResolver(knownTypes);
        _futureLikeResolver = new FutureLikeResolver(knownTypes);
        _fieldBridgeResolver = new FieldBridgeResolver(knownTypes);
        _referenceModelResolver = new ReferenceModelResolver(knownTypes);
    }

    public ResolvedMemberSet ApplyMxFieldFamilyAdjustments(
        TypeDefinition type,
        ResolvedMemberSet members)
        => _mxFieldFamilyResolver.ApplyMxFieldFamilyAdjustments(type, members);

    public ResolvedMemberSet ApplyFutureLikeAdjustments(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyList<string> genericParameterNames,
        ResolvedMemberSet members)
        => _futureLikeResolver.ApplyFutureLikeAdjustments(type, methodRows, genericParameterNames, members);

    public ResolvedMemberSet ApplyFieldBridgeAdjustments(
        TypeDefinition type,
        string? declaringType,
        ResolvedMemberSet members)
        => _fieldBridgeResolver.ApplyFieldBridgeAdjustments(type, declaringType, members);

    public ResolvedMemberSet ApplyReferenceModelAdjustments(
        TypeDefinition type,
        string safeTypeName,
        string? declaringType,
        ResolvedMemberSet members)
        => _referenceModelResolver.ApplyReferenceModelAdjustments(type, safeTypeName, declaringType, members);
}
