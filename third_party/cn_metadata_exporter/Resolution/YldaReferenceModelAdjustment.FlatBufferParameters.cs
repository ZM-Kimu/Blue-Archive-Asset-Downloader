namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private ResolvedParameterModel[] AdjustFlatBufferSecondaryParameters(
        ResolvedMethodModel method,
        ResolvedParameterModel[] adjustedParameters)
    {
            if (isFlatBuffersByteBuffer)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000002 when index == 0 => "System.Byte[]",
                        0x06000003 when index == 0 => "System.Byte[]",
                        0x06000003 when index == 1 => "System.Int32",
                        0x06000005 when index == 0 => "System.Int32",
                        0x06000006 when index == 0 => "System.Int32",
                        0x06000007 when index <= 1 => "System.Int32",
                        0x06000009 when index <= 1 => "System.Int32",
                        0x0600000A when index <= 1 => "System.Int32",
                        0x0600000A when index == 2 => "System.UInt64",
                        0x0600000B when index <= 1 => "System.Int32",
                        0x0600000C when index <= 1 => "System.Int32",
                        0x0600000D when index == 0 => "System.Int32",
                        0x0600000D when index == 1 => "System.SByte",
                        0x0600000E when index == 0 => "System.Int32",
                        0x0600000E when index == 1 => "System.Byte",
                        0x0600000F when index == 0 => "System.Int32",
                        0x0600000F when index == 1 => "System.Byte",
                        0x0600000F when index == 2 => "System.Int32",
                        0x06000010 when index == 0 => "System.Int32",
                        0x06000010 when index == 1 => "System.Int16",
                        0x06000011 when index == 0 => "System.Int32",
                        0x06000011 when index == 1 => "System.Int32",
                        0x06000012 when index == 0 => "System.Int32",
                        0x06000012 when index == 1 => "System.UInt32",
                        0x06000013 when index == 0 => "System.Int32",
                        0x06000013 when index == 1 => "System.Int64",
                        0x06000014 when index == 0 => "System.Int32",
                        0x06000014 when index == 1 => "System.Single",
                        0x06000015 when index == 0 => "System.Int32",
                        0x06000016 when index == 0 => "System.Int32",
                        0x06000017 when index <= 1 => "System.Int32",
                        0x06000018 when index == 0 => "System.Int32",
                        0x06000019 when index == 0 => "System.Int32",
                        0x0600001A when index == 0 => "System.Int32",
                        0x0600001B when index == 0 => "System.Int32",
                        0x0600001C when index == 0 => "System.Int32",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isAddTypeMenuAttribute)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000003 when index == 0 => "System.String",
                        0x06000003 when index == 1 => "System.Int32",
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
