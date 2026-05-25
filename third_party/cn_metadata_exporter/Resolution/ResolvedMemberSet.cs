namespace CnMetadataExporter;

internal readonly record struct ResolvedMemberSet(
    TypeRelationships Relationships,
    IReadOnlyList<ResolvedFieldModel> Fields,
    IReadOnlyList<ResolvedPropertyModel> Properties,
    IReadOnlyList<ResolvedEventModel> Events,
    IReadOnlyList<ResolvedMethodModel> Methods);
