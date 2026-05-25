namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private ResolvedParameterModel[] AdjustTransportSecondaryParameters(
        ResolvedMethodModel method,
        ResolvedParameterModel[] adjustedParameters)
    {
            if (isSocketIoTransportInterface)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000353 when index == 0 => "BestHTTP.SocketIO.Packet",
                        0x06000354 when index == 0 => socketIoPacketListType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIoJsonEncoder || isSocketIoDefaultJsonEncoder)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000382 when index == 0 => "System.String",
                        0x06000383 when index == 0 => listObjectType,
                        0x06000385 when index == 0 => "System.String",
                        0x06000386 when index == 0 => listObjectType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreEncoder)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000511 when index == 0 => "T",
                        0x06000512 when index == 0 => bufferSegmentType,
                        0x06000513 when index == 0 => "System.Type",
                        0x06000513 when index == 1 => "System.Object",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreProtocol)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060005AA when index == 0 => _hubConnectionTypeName,
                        0x060005AB when index == 0 => bufferSegmentType,
                        0x060005AB when index == 1 => signalRMessageListType,
                        0x060005AC when index == 0 => "BestHTTP.SignalRCore.Messages.Message",
                        0x060005AD when index == 0 => typeArrayType,
                        0x060005AD when index == 1 => objectArrayType,
                        0x060005AE when index == 0 => "System.Type",
                        0x060005AE when index == 1 => "System.Object",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreUploadItemController)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060005BD when index == 0 => "System.String",
                        0x060005BD when index == 1 => "T",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreStreamItemContainer)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000515 when index == 0 => genericListType,
                        0x06000517 when index == 0 => genericItemType,
                        0x06000518 when index == 0 => "System.Int64",
                        0x06000519 when index == 0 => genericItemType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreCallbackDescriptor)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x0600051A when index == 0 => typeArrayType,
                        0x0600051A when index == 1 => actionObjectArrayType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIO3EventsCallbackDescriptor)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060004E2 when index == 0 => typeArrayType,
                        0x060004E2 when index == 1 => actionObjectArrayType,
                        0x060004E2 when index == 2 => "System.Boolean",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIO3EventsSubscription)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060004E3 when index == 0 => typeArrayType,
                        0x060004E3 when index == 1 => actionObjectArrayType,
                        0x060004E3 when index == 2 => "System.Boolean",
                        0x060004E4 when index == 0 => actionObjectArrayType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIO3EventsTypedEventTable)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060004E8 when index == 0 => "BestHTTP.SocketIO3.Socket",
                        0x060004EA when index == 0 => "System.String",
                        0x060004EA when index == 1 => typeArrayType,
                        0x060004EA when index == 2 => actionObjectArrayType,
                        0x060004EA when index == 3 => "System.Boolean",
                        0x060004EB when index == 0 => "System.String",
                        0x060004EB when index == 1 => objectArrayType,
                        0x060004ED when index == 0 => "System.String",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreTransportInterface)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x0600050C or 0x0600050D when index == 0 => actionTransportStatesPairType,
                        0x06000510 when index == 0 => bufferSegmentType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isFutureCallback)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x0600425A when index == 0 => "System.Object",
                        0x0600425A when index == 1 => "System.IntPtr",
                        0x0600425B when index == 0 => _futureInterfaceTypeName,
                        0x0600425C when index == 0 => _futureInterfaceTypeName,
                        0x0600425C when index == 1 => "System.AsyncCallback",
                        0x0600425C when index == 2 => "System.Object",
                        0x0600425D when index == 0 => "System.IAsyncResult",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isFutureValueCallback)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x0600425E when index == 0 => "System.Object",
                        0x0600425E when index == 1 => "System.IntPtr",
                        0x0600425F when index == 0 => "T",
                        0x06004260 when index == 0 => "T",
                        0x06004260 when index == 1 => "System.AsyncCallback",
                        0x06004260 when index == 2 => "System.Object",
                        0x06004261 when index == 0 => "System.IAsyncResult",
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
