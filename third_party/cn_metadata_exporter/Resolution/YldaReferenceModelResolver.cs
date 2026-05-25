namespace YldaDumpCsExporter;

internal sealed class YldaReferenceModelResolver
{
    private readonly YldaKnownTypeCatalog _knownTypes;

    public YldaReferenceModelResolver(YldaKnownTypeCatalog knownTypes)
    {
        _knownTypes = knownTypes;
    }

    public YldaResolvedMemberSet ApplyReferenceModelAdjustments(
        TypeDefinition type,
        string safeTypeName,
        string? declaringType,
        YldaResolvedMemberSet members)
    {
        return new YldaReferenceModelAdjustment(_knownTypes, type, safeTypeName, declaringType, members).Apply();
    }
}
