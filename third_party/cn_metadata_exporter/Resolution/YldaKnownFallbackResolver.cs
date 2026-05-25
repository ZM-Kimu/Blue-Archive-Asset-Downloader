namespace YldaDumpCsExporter;

internal sealed class YldaKnownFallbackResolver
{
    private readonly YldaMxFieldFamilyResolver _mxFieldFamilyResolver;
    private readonly YldaFutureLikeResolver _futureLikeResolver;
    private readonly YldaFieldBridgeResolver _fieldBridgeResolver;
    private readonly YldaReferenceModelResolver _referenceModelResolver;

    public YldaKnownFallbackResolver(YldaKnownTypeCatalog knownTypes)
    {
        _mxFieldFamilyResolver = new YldaMxFieldFamilyResolver(knownTypes);
        _futureLikeResolver = new YldaFutureLikeResolver(knownTypes);
        _fieldBridgeResolver = new YldaFieldBridgeResolver(knownTypes);
        _referenceModelResolver = new YldaReferenceModelResolver(knownTypes);
    }

    public YldaResolvedMemberSet ApplyMxFieldFamilyAdjustments(
        TypeDefinition type,
        YldaResolvedMemberSet members)
        => _mxFieldFamilyResolver.ApplyMxFieldFamilyAdjustments(type, members);

    public YldaResolvedMemberSet ApplyFutureLikeAdjustments(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyList<string> genericParameterNames,
        YldaResolvedMemberSet members)
        => _futureLikeResolver.ApplyFutureLikeAdjustments(type, methodRows, genericParameterNames, members);

    public YldaResolvedMemberSet ApplyFieldBridgeAdjustments(
        TypeDefinition type,
        string? declaringType,
        YldaResolvedMemberSet members)
        => _fieldBridgeResolver.ApplyFieldBridgeAdjustments(type, declaringType, members);

    public YldaResolvedMemberSet ApplyReferenceModelAdjustments(
        TypeDefinition type,
        string safeTypeName,
        string? declaringType,
        YldaResolvedMemberSet members)
        => _referenceModelResolver.ApplyReferenceModelAdjustments(type, safeTypeName, declaringType, members);
}
