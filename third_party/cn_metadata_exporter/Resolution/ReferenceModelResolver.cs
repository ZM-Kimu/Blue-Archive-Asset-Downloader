namespace CnMetadataExporter;

internal sealed class ReferenceModelResolver
{
    private readonly KnownTypeCatalog _knownTypes;

    public ReferenceModelResolver(KnownTypeCatalog knownTypes)
    {
        _knownTypes = knownTypes;
    }

    public ResolvedMemberSet ApplyReferenceModelAdjustments(
        TypeDefinition type,
        string safeTypeName,
        string? declaringType,
        ResolvedMemberSet members)
    {
        return new ReferenceModelAdjustment(_knownTypes, type, safeTypeName, declaringType, members).Apply();
    }
}
