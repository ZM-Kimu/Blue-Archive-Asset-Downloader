namespace YldaDumpCsExporter;

internal sealed class YldaRelationshipIndexBuilder
{
    private readonly MetadataModel _model;
    private readonly YldaRelationshipResolver _relationshipResolver;
    private readonly TypeIndexArtifact _typeIndex;
    private readonly TypeDescriptorIndex _descriptors;
    private readonly ExportProgress? _progress;

    public YldaRelationshipIndexBuilder(
        MetadataModel model,
        YldaRelationshipResolver relationshipResolver,
        TypeIndexArtifact typeIndex,
        TypeDescriptorIndex descriptors,
        ExportProgress? progress = null)
    {
        _model = model;
        _relationshipResolver = relationshipResolver;
        _typeIndex = typeIndex;
        _descriptors = descriptors;
        _progress = progress;
    }

    public RelationshipIndexArtifact Build()
    {
        var relationshipBuckets = new RelationshipIndexEntry[_model.Types.Count];
        var processed = 0;

        Parallel.For(0, _model.Types.Count, i =>
        {
            var type = _model.Types[i];
            var methods = _descriptors.GetMethods(type);
            var typeNameMap = CreateLookup(type.Index);
            var declaringType = _relationshipResolver.ResolveDeclaringType(type, typeNameMap);
            var relationships = _relationshipResolver.ResolveTypeRelationships(type, methods, typeNameMap);
            relationshipBuckets[type.Index] = new RelationshipIndexEntry(
                type.Index,
                declaringType,
                relationships.BaseType,
                relationships.Interfaces.ToArray(),
                relationships.Comments.ToArray());

            _progress?.Loop("relationship index build", Interlocked.Increment(ref processed), _model.Types.Count);
        });

        var relationshipsByType = new Dictionary<int, RelationshipIndexEntry>(_model.Types.Count);
        for (var i = 0; i < relationshipBuckets.Length; i++)
        {
            var entry = relationshipBuckets[i];
            if (entry is not null)
                relationshipsByType[i] = entry;
        }

        return new RelationshipIndexArtifact(relationshipsByType);
    }

    private IReadOnlyDictionary<uint, string> CreateLookup(int typeIndex)
    {
        if (!_typeIndex.LocalTypeOverridesByType.TryGetValue(typeIndex, out var localOverrides) || localOverrides.Count == 0)
            return _typeIndex.GlobalTypeNames;

        return new TypeNameLookup(_typeIndex.GlobalTypeNames, localOverrides);
    }
}
