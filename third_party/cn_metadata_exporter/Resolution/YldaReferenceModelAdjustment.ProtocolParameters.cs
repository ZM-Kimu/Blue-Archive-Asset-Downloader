namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private ResolvedParameterModel[] AdjustProtocolSecondaryParameters(
        ResolvedMethodModel method,
        ResolvedParameterModel[] adjustedParameters)
    {
            if (isHubConnectionExtensions)
            {
                adjustedParameters = adjustedParameters.Select(parameter =>
                    parameter.Identifier == "args"
                        ? parameter with { TypeName = objectArrayType! }
                        : parameter).ToArray();
            }
            else if (isUploadItemControllerExtensions)
            {
                adjustedParameters = adjustedParameters.Select(parameter =>
                {
                    var desiredType = parameter.Identifier switch
                    {
                        "controller" => "BestHTTP.SignalRCore.UpStreamItemController<TResult>",
                        "item" or "param1" => "P1",
                        "param2" => "P2",
                        "param3" => "P3",
                        "param4" => "P4",
                        "param5" => "P5",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = desiredType };
                }).ToArray();
            }
            else if (isBitPackFormatter)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.DisplayName switch
                    {
                        "Serialize" when index == 0 => _memoryPackWriterTypeName,
                        "Serialize" when parameter.Identifier == "value" => boolArrayType,
                        "Deserialize" when index == 0 => _memoryPackReaderTypeName,
                        "Deserialize" when parameter.Identifier == "value" => boolArrayType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSystemRuntimeUnsafe)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000001 when index == 0 => "System.Byte",
                        0x06000002 when index == 0 => "System.Byte",
                        0x06000002 when index == 1 => "T",
                        0x06000003 when index == 0 => "T",
                        0x06000005 when index == 0 => "System.Byte",
                        0x06000005 when index == 1 => "System.Byte",
                        0x06000005 when index == 2 => "System.UInt32",
                        0x06000006 when index == 0 => "System.Object",
                        0x06000007 when index == 0 => "System.Void*",
                        0x06000008 when index == 0 => "T",
                        0x06000009 when index == 0 => "TFrom",
                        0x0600000A when index == 0 => "T",
                        0x0600000A when index == 1 => "System.Int32",
                        0x0600000B when index == 0 => "T",
                        0x0600000B when index == 1 => "System.IntPtr",
                        0x0600000C when index == 0 => "T",
                        0x0600000C when index == 1 => "System.IntPtr",
                        0x0600000D when index == 0 => "T",
                        0x0600000D when index == 1 => "T",
                        0x0600000E when index <= 1 => "T",
                        0x0600000F when index <= 1 => "T",
                        0x06000010 when index == 0 => "T",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isCommunityToolkitArrayExtensions)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000008 when index == 0 => "T[]",
                        0x06000009 when index == 0 => "T[]",
                        0x06000009 when index == 1 => "System.Int32",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isTimelineExtensions)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000388 when index == 0 => "Spine.TranslateTimeline",
                        0x06000388 when index == 1 => "System.Single",
                        0x06000388 when index == 2 => "Spine.SkeletonData",
                        0x06000389 when index == 0 => "Spine.TranslateXTimeline",
                        0x06000389 when index == 1 => "Spine.TranslateYTimeline",
                        0x06000389 when index == 2 => "System.Single",
                        0x06000389 when index == 3 => "Spine.SkeletonData",
                        0x0600038A when index == 0 => "Spine.RotateTimeline",
                        0x0600038A when index == 1 => "System.Single",
                        0x0600038A when index == 2 => "Spine.SkeletonData",
                        0x0600038B when index == 0 => "Spine.TransformConstraintTimeline",
                        0x0600038B when index == 1 => "System.Single",
                        0x0600038C when index == 0 => "Spine.TransformConstraintTimeline",
                        0x0600038C when index == 1 => "System.Single",
                        0x0600038D when index == 0 => "Spine.Animation",
                        0x0600038D when index == 1 => "System.Int32",
                        0x0600038E when index == 0 => "Spine.Animation",
                        0x0600038E when index == 1 => "System.Int32",
                        0x0600038F when index == 0 => "Spine.Animation",
                        0x0600038F when index == 1 => "System.Int32",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isWebRequestUtils)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000001 when index <= 1 => "System.String",
                        0x06000002 when index <= 1 => "System.String",
                        0x06000003 when index == 0 => "System.Uri",
                        0x06000003 when index == 1 => "System.String",
                        0x06000003 when index == 2 => "System.Boolean",
                        0x06000004 when index == 0 => "System.String",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isJsonUtility)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000001 when index == 0 => "System.Object",
                        0x06000001 when index == 1 => "System.Boolean",
                        0x06000002 when index == 0 => "System.String",
                        0x06000002 when index == 1 => "System.Object",
                        0x06000002 when index == 2 => "System.Type",
                        0x06000003 when index == 0 => "System.Object",
                        0x06000004 when index == 0 => "System.Object",
                        0x06000004 when index == 1 => "System.Boolean",
                        0x06000005 when index == 0 => "System.String",
                        0x06000006 when index == 0 => "System.String",
                        0x06000006 when index == 1 => "System.Type",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }

        return adjustedParameters;
    }
}
