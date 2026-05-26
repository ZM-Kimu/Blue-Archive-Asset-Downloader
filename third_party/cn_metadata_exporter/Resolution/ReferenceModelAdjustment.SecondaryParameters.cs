namespace CnMetadataExporter;

internal sealed partial class ReferenceModelAdjustment
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
