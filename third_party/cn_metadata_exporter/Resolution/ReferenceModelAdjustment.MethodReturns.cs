using static CnMetadataExporter.TypeNameHelpers;

namespace CnMetadataExporter;

internal sealed partial class ReferenceModelAdjustment
{
    private string? ResolveDesiredMethodReturnType(
        ResolvedMethodModel method,
        ResolvedParameterModel[] adjustedParameters)
    {
            string? desiredReturnType = null;

            switch (type.FullName)
            {
                case "AccountBillingInfo":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_MonthlyProductRewards" => monthlyProductRewardsType,
                        "get_RepurchasableProductPurchaseCountDBList" => purchaseCountDbListType,
                        "get_RepurchasableProductList" => repurchasableProductListType,
                        "get_NewProductList" => purchaseCountDbListType,
                        "get_PurchaseCountList" => purchaseCountDbListType,
                        "get_BlockedProductList" => blockedProductDbListType,
                        "set_MonthlyProductRewards" or
                        "set_RepurchasableProductPurchaseCountDBList" or
                        "set_RepurchasableProductList" or
                        "set_NewProductList" or
                        "set_PurchaseCountList" or
                        "set_BlockedProductList" => "System.Void",
                        _ => null,
                    };
                    break;
                case "ByteReader":
                    desiredReturnType = method.DisplayName switch
                    {
                        "ReadDictionary" => stringDictionaryType,
                        "ReadCSV" => betterListStringType,
                        _ => null,
                    };
                    break;
                case "BMFont":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_glyphs" => bmGlyphListType,
                        _ => null,
                    };
                    break;
                case var _ when isRuntimeInspectorUtils:
                    desiredReturnType = method.DisplayName switch
                    {
                        "GetTexture" => textureType,
                        "Tint" => colorType,
                        "CreateDraggedReferenceItem" => draggedReferenceItemType,
                        "GetAllVariables" => memberInfoArrayType,
                        "GetExposedMethods" => exposedMethodArrayType,
                        "GetAssignableObjectFromDraggedReferenceItem" or "GetAssignableObjectFromDraggedReferenceItem<T>" when adjustedParameters.Length == 1 => "T",
                        "GetAssignableObjectFromDraggedReferenceItem" when adjustedParameters.Length == 2 => "System.Object",
                        "GetAssignableObjectsFromDraggedReferenceItem" or "GetAssignableObjectsFromDraggedReferenceItem<T>" when adjustedParameters.Length == 1 => "T[]",
                        "GetAssignableObjectsFromDraggedReferenceItem" when adjustedParameters.Length == 2 => "System.Object[]",
                        "GetAttribute" or "GetAttribute<T>" => "T",
                        "GetAttributes" or "GetAttributes<T>" => "T[]",
                        _ => null,
                    };
                    break;
                case var _ when isHubConnectionExtensions:
                    desiredReturnType = "BestHTTP.SignalRCore.UpStreamItemController<TResult>";
                    break;
                case var _ when isUploadItemControllerExtensions:
                    desiredReturnType = "System.Void";
                    break;
                case var _ when isBitPackFormatter:
                    desiredReturnType = method.DisplayName switch
                    {
                        "Serialize" or "Deserialize" => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSystemRuntimeUnsafe:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "T",
                        0x06000002 => "System.Void",
                        0x06000003 => "System.Void*",
                        0x06000004 => "System.Int32",
                        0x06000005 => "System.Void",
                        0x06000006 => "T",
                        0x06000007 => "T",
                        0x06000008 => "T",
                        0x06000009 => "TTo",
                        0x0600000A => "T",
                        0x0600000B => "T",
                        0x0600000C => "T",
                        0x0600000D => "System.IntPtr",
                        0x0600000E => "System.Boolean",
                        0x0600000F => "System.Boolean",
                        0x06000010 => "System.Boolean",
                        _ => null,
                    };
                    break;
                case var _ when isCommunityToolkitArrayExtensions:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000008 => "T",
                        0x06000009 => "T",
                        _ => null,
                    };
                    break;
                case var _ when isTimelineExtensions:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000388 => _unityVector2TypeName,
                        0x06000389 => _unityVector2TypeName,
                        0x0600038A => "System.Single",
                        0x0600038B => _unityVector2TypeName,
                        0x0600038C => "System.Single",
                        0x0600038D => "Spine.TranslateTimeline",
                        0x0600038E => "T",
                        0x0600038F => "Spine.TransformConstraintTimeline",
                        _ => null,
                    };
                    break;
                case var _ when isWebRequestUtils:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "System.String",
                        0x06000002 => "System.String",
                        0x06000003 => "System.String",
                        0x06000004 => "System.String",
                        0x06000005 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isJsonUtility:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "System.String",
                        0x06000002 => "System.Object",
                        0x06000003 => "System.String",
                        0x06000004 => "System.String",
                        0x06000005 => "T",
                        0x06000006 => "System.Object",
                        _ => null,
                    };
                    break;
                case var _ when isSocketIoJsonEncoder || isSocketIoDefaultJsonEncoder:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000382 => listObjectType,
                        0x06000383 => "System.String",
                        0x06000385 => listObjectType,
                        0x06000386 => "System.String",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreEncoder:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000511 => bufferSegmentType,
                        0x06000512 => "T",
                        0x06000513 => "System.Object",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreProtocol:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060005A6 => "System.String",
                        0x060005A7 => "BestHTTP.SignalRCore.TransferModes",
                        0x060005A8 => "BestHTTP.SignalRCore.IEncoder",
                        0x060005A9 => _hubConnectionTypeName,
                        0x060005AA => "System.Void",
                        0x060005AB => "System.Void",
                        0x060005AC => bufferSegmentType,
                        0x060005AD => objectArrayType,
                        0x060005AE => "System.Object",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreTransportInterface:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000508 => "BestHTTP.SignalRCore.TransferModes",
                        0x06000509 => "BestHTTP.SignalRCore.TransportTypes",
                        0x0600050A => "BestHTTP.SignalRCore.TransportStates",
                        0x0600050B => "System.String",
                        0x0600050C => "System.Void",
                        0x0600050D => "System.Void",
                        0x0600050E => "System.Void",
                        0x0600050F => "System.Void",
                        0x06000510 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreUploadItemController:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060005BB => stringArrayType,
                        0x060005BC => _hubConnectionTypeName,
                        0x060005BD => "System.Void",
                        0x060005BE => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isBestHttpCoreHostConnection:
                    if (method.DisplayName == "get_LastProtocolSupportUpdate")
                    {
                        desiredReturnType = "System.DateTime";
                    }
                    else if (method.DisplayName == "set_LastProtocolSupportUpdate")
                    {
                        desiredReturnType = "System.Void";
                    }
                    break;
                case var _ when isSignalRCoreStreamItemContainer:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000514 => genericListType,
                        0x06000515 => "System.Void",
                        0x06000516 => genericItemType,
                        0x06000517 => "System.Void",
                        0x06000518 => "System.Void",
                        0x06000519 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSocketIO3EventsCallbackDescriptor:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060004E2 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSocketIO3EventsSubscription:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060004E3 => "System.Void",
                        0x060004E4 => "System.Void",
                        0x060004E5 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSocketIO3EventsTypedEventTable:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060004E6 => "BestHTTP.SocketIO3.Socket",
                        0x060004E7 => "System.Void",
                        0x060004E8 => "System.Void",
                        0x060004E9 => "BestHTTP.SocketIO3.Events.Subscription",
                        0x060004EA => "System.Void",
                        0x060004EB => "System.Void",
                        0x060004EC => "System.Void",
                        0x060004ED => "System.Void",
                        0x060004EE => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isFlatBuffersByteBuffer:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "System.Int32",
                        0x06000002 => "System.Void",
                        0x06000003 => "System.Void",
                        0x06000004 => "System.Int32",
                        0x06000005 => "System.Void",
                        0x06000006 => "System.Void",
                        0x06000007 => "System.Byte[]",
                        0x06000008 => "System.Byte[]",
                        0x06000009 => "System.ArraySegment<System.Byte>",
                        0x0600000A => "System.Void",
                        0x0600000B => "System.UInt64",
                        0x0600000C => "System.Void",
                        0x0600000D => "System.Void",
                        0x0600000E => "System.Void",
                        0x0600000F => "System.Void",
                        0x06000010 => "System.Void",
                        0x06000011 => "System.Void",
                        0x06000012 => "System.Void",
                        0x06000013 => "System.Void",
                        0x06000014 => "System.Void",
                        0x06000015 => "System.SByte",
                        0x06000016 => "System.Byte",
                        0x06000017 => "System.String",
                        0x06000018 => "System.Int16",
                        0x06000019 => "System.Int32",
                        0x0600001A => "System.UInt32",
                        0x0600001B => "System.Int64",
                        0x0600001C => "System.Single",
                        _ => null,
                    };
                    break;
                case var _ when isAddTypeMenuAttribute:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "System.String",
                        0x06000002 => "System.Int32",
                        0x06000003 => "System.Void",
                        0x06000004 => "System.String[]",
                        0x06000005 => "System.String",
                        0x06000006 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreCallbackDescriptor:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x0600051A => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isFutureCallback:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x0600425A => "System.Void",
                        0x0600425B => "System.Void",
                        0x0600425C => "System.IAsyncResult",
                        0x0600425D => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isFutureValueCallback:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x0600425E => "System.Void",
                        0x0600425F => "System.Void",
                        0x06004260 => "System.IAsyncResult",
                        0x06004261 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSystemActionDelegate:
                    if (method.DisplayName == "Invoke")
                        desiredReturnType = "System.Void";
                    break;
                case var _ when isSystemFuncDelegate:
                    if (method.DisplayName == "Invoke" &&
                        parsedSafeGeneric is { Args: var genericArgs } &&
                        genericArgs.Count > 0)
                    {
                        desiredReturnType = genericArgs[^1];
                    }
                    break;
                case var _ when isWwwForm:
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_headers" => BuildDictionaryType("System.String", "System.String"),
                        "get_data" => byteArrayType,
                        _ => null,
                    };
                    break;
                case "NGUIText":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_isDynamic" => "System.Boolean",
                        "GetGlyph" => glyphInfoType,
                        "ParseColor" or "ParseColor24" or "ParseColor32" => colorType,
                        "CalculatePrintedSize" => _unityVector2TypeName,
                        _ => null,
                    };
                    break;
                case "UIDrawCall":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_list" or "get_activeList" or "get_inactiveList" => uiDrawCallListType,
                        "get_cachedTransform" => transformType,
                        "get_baseMaterial" or "get_dynamicMaterial" or "RebuildMaterial" => materialType,
                        _ => null,
                    };
                    break;
                default:
                    if (isBetterList)
                    {
                        desiredReturnType = method.DisplayName switch
                        {
                            "GetEnumerator" => genericEnumeratorType,
                            "get_Item" => genericItemType,
                            "Pop" => genericItemType,
                            "ToArray" => genericItemArrayType,
                            "Add" or "Insert" or "set_Item" => "System.Void",
                            "Contains" or "Remove" => "System.Boolean",
                            "IndexOf" => "System.Int32",
                            _ => null,
                        };
                    }
                    else if (isEventDelegate)
                    {
                        desiredReturnType = method.DisplayName switch
                        {
                            "get_target" => "UnityEngine.MonoBehaviour",
                            "get_methodName" => "System.String",
                            "set_target" or "set_methodName" => "System.Void",
                            "get_parameters" => eventDelegateParameterArrayType,
                            _ => null,
                        };
                    }
                    else if (isPropertyReference)
                    {
                        desiredReturnType = method.DisplayName switch
                        {
                            "get_target" => "UnityEngine.Component",
                            "get_name" => "System.String",
                            "set_target" or "set_name" => "System.Void",
                            _ => null,
                        };
                    }
                    break;
                case "FurnitureInventoryObject":
                    if (method.DisplayName == "GetLevelExp")
                    {
                        desiredReturnType = "System.Int64";
                    }
                    else if (method.DisplayName == "GetPlacedFurnitures" || method.DisplayName == "GetAllPlacedFurnitures")
                    {
                        desiredReturnType = furnitureObjectEnumerableType;
                    }
                    else if (method.DisplayName == "FindFurniture")
                    {
                        desiredReturnType = "FurnitureObject";
                    }
                    break;
                case "FurnitureObject":
                    if (method.DisplayName is "get_CafeDBId" or "get_LevelUpFeedCostAmount" or "get_LevelUpFeedExp" or "get_SetGroupId" or "get_InvalidId")
                    {
                        desiredReturnType = "System.Int64";
                    }
                    else if (method.DisplayName is "get_Tags")
                    {
                        desiredReturnType = furnitureTagsDictionaryType;
                    }
                    else if (method.DisplayName is "get_AvailableCharacterStates")
                    {
                        desiredReturnType = furnitureTimelineStateListType;
                    }
                    else if (method.DisplayName is "get_FurnitureExcel")
                    {
                        desiredReturnType = furnitureExcelType;
                    }
                    else if (method.DisplayName is "set_CafeDBId" or "set_Tags" or "set_FurnitureExcel" or "set_Position")
                    {
                        desiredReturnType = "System.Void";
                    }
                    break;
            }

            if (isEventDelegateParameter && method.DisplayName == ".ctor")
            {
                desiredReturnType = "System.Void";
            }

        return desiredReturnType;
    }
}
