namespace YldaDumpCsExporter;

internal sealed class YldaTypeIndexBuilder
{
    private readonly MetadataModel _model;
    private readonly YldaTypeResolver _typeResolver;
    private readonly TypeDescriptorIndex _descriptors;
    private readonly ExportProgress? _progress;

    public YldaTypeIndexBuilder(
        MetadataModel model,
        YldaTypeResolver typeResolver,
        TypeDescriptorIndex descriptors,
        ExportProgress? progress = null)
    {
        _model = model;
        _typeResolver = typeResolver;
        _descriptors = descriptors;
        _progress = progress;
    }

    public TypeIndexArtifact Build()
    {
        var globalTypeNames = new Dictionary<uint, string>(_typeResolver.GlobalTypeNames);
        var localOverrideBuckets = new Dictionary<uint, string>?[_model.Types.Count];
        var processed = 0;

        Parallel.For(0, _model.Types.Count, i =>
        {
            var type = _model.Types[i];
            var hints = _descriptors.GetHints(type);
            if (!ShouldBuildLocalOverrides(type, hints, globalTypeNames))
            {
                _progress?.Loop("type index build", Interlocked.Increment(ref processed), _model.Types.Count);
                return;
            }

            var localOverrides = _typeResolver.BuildLocalTypeOverrides(type, _descriptors.GetMethods(type), _descriptors.GetFields(type));
            if (localOverrides.Count > 0)
                localOverrideBuckets[type.Index] = localOverrides;

            _progress?.Loop("type index build", Interlocked.Increment(ref processed), _model.Types.Count);
        });

        var localOverridesByType = new Dictionary<int, Dictionary<uint, string>>();
        for (var i = 0; i < localOverrideBuckets.Length; i++)
        {
            var bucket = localOverrideBuckets[i];
            if (bucket is not null && bucket.Count > 0)
                localOverridesByType[i] = bucket;
        }

        return new TypeIndexArtifact(globalTypeNames, localOverridesByType);
    }

    private bool ShouldBuildLocalOverrides(
        TypeDefinition type,
        TypeDescriptorHints hints,
        IReadOnlyDictionary<uint, string> globalTypeNames)
    {
        if (!hints.RequiresLocalTypeInference)
            return false;

        if (hints.HasExplicitInterfaces ||
            hints.HasFlatBufferAssignOrRoot ||
            hints.HasByteBufferAccessor ||
            hints.HasInitKeyMethod ||
            hints.IsTableLike ||
            hints.IsKnownLocalInferenceType)
        {
            return true;
        }

        if (!hints.HasCollectionLikeMembers)
            return false;

        foreach (var typeIndex in _descriptors.GetReferencedTypeIndices(type))
        {
            if (!globalTypeNames.TryGetValue(typeIndex, out var resolvedTypeName))
                return true;

            if (resolvedTypeName.StartsWith("Type_0x", StringComparison.Ordinal) ||
                YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(resolvedTypeName))
            {
                return true;
            }
        }

        return false;
    }
}
