namespace CnMetadataExporter;

internal sealed class MxFieldFamilyResolver
{
    private readonly KnownTypeCatalog _knownTypes;

    public MxFieldFamilyResolver(KnownTypeCatalog knownTypes)
    {
        _knownTypes = knownTypes;
    }

    public ResolvedMemberSet ApplyMxFieldFamilyAdjustments(
        TypeDefinition type,
        ResolvedMemberSet members)
    {
        return new MxFieldFamilyAdjustment(_knownTypes, type, members).Apply();
    }
}
