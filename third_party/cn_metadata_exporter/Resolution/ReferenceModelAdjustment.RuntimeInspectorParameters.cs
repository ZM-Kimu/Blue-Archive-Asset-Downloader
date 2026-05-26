namespace CnMetadataExporter;

internal sealed partial class ReferenceModelAdjustment
{
    private ResolvedParameterModel[] AdjustRuntimeInspectorSecondaryParameters(
        ResolvedMethodModel method,
        ResolvedParameterModel[] adjustedParameters)
    {
            if (isRuntimeInspectorUtils)
            {
                adjustedParameters = adjustedParameters.Select(parameter =>
                {
                    if (method.DisplayName is "GetAssignableObjectsFromDraggedReferenceItem" && parameter.Identifier == "assignableType")
                    {
                        return parameter with { TypeName = "System.Type" };
                    }

                    return parameter;
                }).ToArray();
            }

        return adjustedParameters;
    }
}
