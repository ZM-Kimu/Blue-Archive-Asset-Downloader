namespace YldaDumpCsExporter;

internal readonly record struct YldaResolvedMemberSet(
    TypeRelationships Relationships,
    IReadOnlyList<ResolvedFieldModel> Fields,
    IReadOnlyList<ResolvedPropertyModel> Properties,
    IReadOnlyList<ResolvedEventModel> Events,
    IReadOnlyList<ResolvedMethodModel> Methods);
