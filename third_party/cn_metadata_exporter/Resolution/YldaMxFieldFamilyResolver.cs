namespace YldaDumpCsExporter;

internal sealed class YldaMxFieldFamilyResolver
{
    private readonly YldaKnownTypeCatalog _knownTypes;

    public YldaMxFieldFamilyResolver(YldaKnownTypeCatalog knownTypes)
    {
        _knownTypes = knownTypes;
    }

    public YldaResolvedMemberSet ApplyMxFieldFamilyAdjustments(
        TypeDefinition type,
        YldaResolvedMemberSet members)
    {
        return new YldaMxFieldFamilyAdjustment(_knownTypes, type, members).Apply();
    }
}
