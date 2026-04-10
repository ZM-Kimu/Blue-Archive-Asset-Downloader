using LibCpp2IL;

namespace YldaDumpCsExporter;

internal sealed class ResolvedExportArtifactBuilder
{
    private readonly MetadataModel _model;
    private readonly ExportProfiler? _profiler;
    private readonly ExportProgress? _progress;

    public ResolvedExportArtifactBuilder(
        MetadataModel model,
        ExportProfiler? profiler = null,
        ExportProgress? progress = null)
    {
        _model = model;
        _profiler = profiler;
        _progress = progress;
    }

    public ResolvedExportArtifact Build()
    {
        _progress?.Stage("descriptor build", 1, 7);
        var descriptors = Measure("descriptor build", () => new TypeDescriptorIndexBuilder(_model).Build());

        _progress?.Stage("type-system indexes", 2, 7);
        var typeResolver = Measure("build type-system indexes", () => new YldaTypeResolver(_model, descriptors));

        _progress?.Stage("type index build", 3, 7);
        var typeIndex = Measure("type index build", () => new YldaTypeIndexBuilder(_model, typeResolver, descriptors, _progress).Build());

        _progress?.Stage("relationship resolver build", 4, 7);
        var relationshipResolver = Measure("relationship build", () => new YldaRelationshipResolver(_model, typeResolver, descriptors));

        _progress?.Stage("relationship index build", 5, 7);
        var relationshipIndex = Measure("relationship index build", () => new YldaRelationshipIndexBuilder(_model, relationshipResolver, typeIndex, descriptors, _progress).Build());

        _progress?.Stage("member resolver build", 6, 7);
        var memberResolver = Measure("member resolver build", () => new YldaMemberResolver(_model, typeResolver, relationshipResolver, descriptors));

        _progress?.Stage("member signature build", 7, 7);
        var memberIndex = Measure("member signature build", () => new YldaMemberIndexBuilder(_model, memberResolver, typeIndex, relationshipIndex, _progress).Build());
        _progress?.Complete();

        return new ResolvedExportArtifact(
            typeof(LibCpp2IlMain).Assembly.GetName().Name ?? "LibCpp2IL",
            _model.Sections
                .Select(section => new CachedSectionDescriptor(
                    section.HeaderOffset,
                    section.Name,
                    section.Section.Offset,
                    section.Section.Size,
                    section.RecordSize,
                    section.IsKnown))
                .ToArray(),
            typeIndex,
            relationshipIndex,
            memberIndex);
    }

    private T Measure<T>(string stage, Func<T> action)
    {
        if (_profiler is null)
            return action();

        return _profiler.Measure(stage, action);
    }
}
