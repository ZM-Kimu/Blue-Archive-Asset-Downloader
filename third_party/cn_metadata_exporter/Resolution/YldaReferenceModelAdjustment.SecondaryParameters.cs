namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private ResolvedParameterModel[] AdjustSecondaryParameters(
        ResolvedMethodModel method,
        IReadOnlyList<ResolvedParameterModel> initialParameters)
    {
        var adjustedParameters = initialParameters.ToArray();
        adjustedParameters = AdjustRuntimeInspectorSecondaryParameters(method, adjustedParameters);
        adjustedParameters = AdjustProtocolSecondaryParameters(method, adjustedParameters);
        adjustedParameters = AdjustTransportSecondaryParameters(method, adjustedParameters);
        adjustedParameters = AdjustFlatBufferSecondaryParameters(method, adjustedParameters);
        adjustedParameters = AdjustFurnitureFilterSecondaryParameters(method, adjustedParameters);
        return adjustedParameters;
    }
}
