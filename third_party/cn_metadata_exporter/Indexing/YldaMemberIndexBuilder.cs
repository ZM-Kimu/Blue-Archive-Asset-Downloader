namespace YldaDumpCsExporter;

internal sealed class YldaMemberIndexBuilder
{
    private readonly MetadataModel _model;
    private readonly YldaMemberResolver _memberResolver;
    private readonly TypeIndexArtifact _typeIndex;
    private readonly RelationshipIndexArtifact _relationshipIndex;
    private readonly ExportProgress? _progress;

    public YldaMemberIndexBuilder(
        MetadataModel model,
        YldaMemberResolver memberResolver,
        TypeIndexArtifact typeIndex,
        RelationshipIndexArtifact relationshipIndex,
        ExportProgress? progress = null)
    {
        _model = model;
        _memberResolver = memberResolver;
        _typeIndex = typeIndex;
        _relationshipIndex = relationshipIndex;
        _progress = progress;
    }

    public MemberIndexArtifact Build()
    {
        var resolvedTypes = new ResolvedExportTypeModel[_model.Types.Count];
        var processed = 0;

        Parallel.For(0, _model.Types.Count, i =>
        {
            var type = _model.Types[i];
            var typeNameMap = CreateLookup(type.Index);
            var relationshipEntry = _relationshipIndex.RelationshipsByType[type.Index];
            resolvedTypes[i] = ToExportModel(_memberResolver.ResolveType(type, typeNameMap, relationshipEntry));
            _progress?.Loop("member signature build", Interlocked.Increment(ref processed), _model.Types.Count);
        });

        return new MemberIndexArtifact(resolvedTypes);
    }

    private IReadOnlyDictionary<uint, string> CreateLookup(int typeIndex)
    {
        if (!_typeIndex.LocalTypeOverridesByType.TryGetValue(typeIndex, out var localOverrides) || localOverrides.Count == 0)
            return _typeIndex.GlobalTypeNames;

        return new TypeNameLookup(_typeIndex.GlobalTypeNames, localOverrides);
    }

    private static ResolvedExportTypeModel ToExportModel(ResolvedTypeModel type)
    {
        return new ResolvedExportTypeModel(
            type.Type.Index,
            type.Type.Token,
            type.Type.FullName,
            type.ImageName,
            type.NamespaceName,
            type.SafeTypeName,
            type.OriginalTypeName,
            type.GenericParameterNames.ToArray(),
            type.Modifiers.ToArray(),
            type.DeclaringType,
            type.Relationships.BaseType,
            type.Relationships.Interfaces.ToArray(),
            type.Relationships.Comments.ToArray(),
            type.Fields.Select(field => new ResolvedExportFieldModel(
                field.Definition.Token,
                field.Identifier,
                field.TypeName,
                field.Modifiers.ToArray(),
                field.Accessibility)).ToArray(),
            type.Properties.Select(property => new ResolvedExportPropertyModel(
                property.Definition.Token,
                property.DisplayName,
                property.TypeName,
                property.Modifiers.ToArray(),
                property.Accessibility,
                property.Accessors.ToArray())).ToArray(),
            type.Events.Select(evt => new ResolvedExportEventModel(
                evt.Definition.Token,
                evt.DisplayName,
                evt.TypeName,
                evt.Modifiers.ToArray(),
                evt.Accessibility)).ToArray(),
            type.Methods.Select(method => new ResolvedExportMethodModel(
                method.Definition.Token,
                method.DisplayName,
                method.ReturnTypeName,
                method.Modifiers.ToArray(),
                method.Accessibility,
                method.Definition.Slot,
                method.Parameters.Select(parameter => new ResolvedExportParameterModel(
                    parameter.Identifier,
                    parameter.TypeName,
                    parameter.ModifierPrefix)).ToArray())).ToArray());
    }
}
