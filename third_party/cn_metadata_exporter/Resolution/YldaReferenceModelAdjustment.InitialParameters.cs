using static YldaDumpCsExporter.YldaTypeNameHelpers;

namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private ResolvedParameterModel[] AdjustInitialParameters(ResolvedMethodModel method)
    {
        return method.Parameters.Select(parameter =>
        {
                string? desiredType = null;
                var modifierPrefix = parameter.ModifierPrefix;

                switch (type.FullName)
                {
                    case "AccountBillingInfo":
                        if (method.DisplayName is "set_MonthlyProductRewards" && parameter.Identifier == "value")
                        {
                            desiredType = monthlyProductRewardsType;
                        }
                        else if (method.DisplayName is "set_RepurchasableProductPurchaseCountDBList" && parameter.Identifier == "value")
                        {
                            desiredType = purchaseCountDbListType;
                        }
                        else if (method.DisplayName is "set_RepurchasableProductList" && parameter.Identifier == "value")
                        {
                            desiredType = repurchasableProductListType;
                        }
                        else if (method.DisplayName is "set_NewProductList" or "set_PurchaseCountList" && parameter.Identifier == "value")
                        {
                            desiredType = purchaseCountDbListType;
                        }
                        else if (method.DisplayName is "set_BlockedProductList" && parameter.Identifier == "value")
                        {
                            desiredType = blockedProductDbListType;
                        }
                        break;
                    case "EventDelegate":
                        if ((method.DisplayName is "get_target" or "set_target") && parameter.Identifier == "value")
                        {
                            desiredType = "UnityEngine.MonoBehaviour";
                        }
                        else if ((method.DisplayName is "get_methodName" or "set_methodName") && parameter.Identifier == "value")
                        {
                            desiredType = "System.String";
                        }
                        if ((method.DisplayName is "Execute" or "IsValid" or "Set" or "Add" or "Remove") &&
                            parameter.Identifier == "list")
                        {
                            desiredType = eventDelegateListType;
                        }
                        break;
                    case "BMSymbol":
                        if (method.DisplayName == "Validate" && parameter.Identifier == "atlas")
                        {
                            desiredType = "INGUIAtlas";
                        }
                        break;
                    case var _ when isRuntimeInspectorUtils:
                        if (method.DisplayName == "GetTexture" && parameter.Identifier == "obj")
                        {
                            desiredType = "UnityEngine.Object";
                        }
                        else if (method.DisplayName == "Tint" && parameter.Identifier == "color")
                        {
                            desiredType = colorType;
                        }
                        else if ((method.DisplayName == "ShowTooltip" || method.DisplayName == "CreateDraggedReferenceItem") &&
                                 parameter.Identifier == "skin")
                        {
                            desiredType = uiSkinType;
                        }
                        else if (method.DisplayName == "CreateDraggedReferenceItem" && parameter.Identifier == "reference")
                        {
                            desiredType = "UnityEngine.Object";
                        }
                        else if (method.DisplayName == "CreateDraggedReferenceItem" && parameter.Identifier == "references")
                        {
                            desiredType = unityObjectArrayType;
                        }
                        else if ((method.DisplayName == "GetAllVariables" || method.DisplayName == "HasAttribute" || method.DisplayName == "HasAttribute<T>" || method.DisplayName == "GetAttribute" || method.DisplayName == "GetAttribute<T>" || method.DisplayName == "GetAttributes" || method.DisplayName == "GetAttributes<T>") &&
                                 parameter.Identifier == "variable")
                        {
                            desiredType = "System.Reflection.MemberInfo";
                        }
                        else if ((method.DisplayName == "IsEmptyForDev" || method.DisplayName == "IsEmptyForDev<T>") && parameter.Identifier == "objects")
                        {
                            desiredType = "System.Collections.Generic.IList<T>";
                        }
                        break;
                    case var _ when isHubConnectionExtensions:
                        if (parameter.Identifier == "args")
                        {
                            desiredType = objectArrayType;
                        }
                        break;
                    case var _ when isUploadItemControllerExtensions:
                        desiredType = parameter.Identifier switch
                        {
                            "controller" => "BestHTTP.SignalRCore.UpStreamItemController<TResult>",
                            "item" or "param1" => "P1",
                            "param2" => "P2",
                            "param3" => "P3",
                            "param4" => "P4",
                            "param5" => "P5",
                            _ => desiredType,
                        };
                        break;
                    case var _ when (isSystemActionDelegate || isSystemFuncDelegate):
                        if (method.DisplayName == "Invoke" &&
                            parsedSafeGeneric is { Args: var genericArgs } &&
                            int.TryParse(parameter.Identifier.TrimStart('a', 'r', 'g'), out var argOrdinal) &&
                            argOrdinal >= 1)
                        {
                            var desiredIndex = argOrdinal - 1;
                            var availableCount = isSystemFuncDelegate ? genericArgs.Count - 1 : genericArgs.Count;
                            if (desiredIndex >= 0 && desiredIndex < availableCount)
                                desiredType = genericArgs[desiredIndex];
                        }
                        break;
                    case "NGUIText":
                        if (method.DisplayName is "EncodeColor" or "EncodeColor24" or "EncodeColor32")
                        {
                            if (parameter.Identifier == "c")
                                desiredType = colorType;
                        }
                        else if (method.DisplayName == "ParseSymbol" && parameter.Identifier == "colors")
                        {
                            desiredType = betterListColorType;
                        }
                        else if (method.DisplayName == "Align" && parameter.Identifier == "verts")
                        {
                            desiredType = vector3ListType;
                        }
                        else if ((method.DisplayName == "GetExactCharacterIndex" || method.DisplayName == "GetApproximateCharacterIndex") &&
                                 parameter.Identifier == "verts")
                        {
                            desiredType = vector3ListType;
                        }
                        else if ((method.DisplayName == "GetExactCharacterIndex" || method.DisplayName == "GetApproximateCharacterIndex") &&
                                 parameter.Identifier == "indices")
                        {
                            desiredType = intListType;
                        }
                        else if ((method.DisplayName == "GetExactCharacterIndex" || method.DisplayName == "GetApproximateCharacterIndex") &&
                                 parameter.Identifier == "pos")
                        {
                            desiredType = _unityVector2TypeName;
                        }
                        else if ((method.DisplayName == "EndLine" || method.DisplayName == "ReplaceSpaceWithNewline") &&
                                 parameter.Identifier == "s")
                        {
                            desiredType = stringBuilderType;
                        }
                        else if (method.DisplayName == "SplitTextChunk" && parameter.Identifier == "extracted")
                        {
                            desiredType = "System.String";
                            modifierPrefix = "out";
                        }
                        else if (method.DisplayName == "WrapText" && parameter.Identifier == "finalText")
                        {
                            desiredType = "System.String";
                            modifierPrefix = "out";
                        }
                        else if (method.DisplayName == "Print")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "verts" => vector3ListType,
                                "uvs" => vector2ListType,
                                "cols" => colorListType,
                                _ => desiredType,
                            };
                        }
                        else if ((method.DisplayName == "PrintApproximateCharacterPositions" || method.DisplayName == "PrintExactCharacterPositions") &&
                                 parameter.Identifier == "verts")
                        {
                            desiredType = vector3ListType;
                        }
                        else if ((method.DisplayName == "PrintApproximateCharacterPositions" || method.DisplayName == "PrintExactCharacterPositions") &&
                                 parameter.Identifier == "indices")
                        {
                            desiredType = intListType;
                        }
                        else if (method.DisplayName == "PrintCaretAndSelection")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "caret" or "highlight" => vector3ListType,
                                _ => desiredType,
                            };
                        }
                        break;
                    case "UIDrawCall":
                        if (method.DisplayName is "set_baseMaterial" && parameter.Identifier == "value")
                        {
                            desiredType = materialType;
                        }
                        else if (method.DisplayName is "set_mainTexture" && parameter.Identifier == "value")
                        {
                            desiredType = textureType;
                        }
                        else if (method.DisplayName is "set_shader" && parameter.Identifier == "value")
                        {
                            desiredType = "UnityEngine.Shader";
                        }
                        break;
                    case var _ when isBestHttpCoreConnectionEventInfo:
                        if (method.DisplayName == ".ctor")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "sourceConn" => "BestHTTP.Connections.ConnectionBase",
                                "event" => "BestHTTP.Core.ConnectionEvents",
                                "newState" => "BestHTTP.Connections.HTTPConnectionStates",
                                "protocolSupport" => "BestHTTP.Core.HostProtocolSupport",
                                "request" => "BestHTTP.HTTPRequest",
                                _ => desiredType,
                            };
                        }
                        break;
                    case var _ when isBestHttpCoreHostConnection:
                        if (method.DisplayName == "set_LastProtocolSupportUpdate" && parameter.Identifier == "value")
                        {
                            desiredType = "System.DateTime";
                        }
                        break;
                    case var _ when isBestHttpCoreHostConnectionKey:
                        if (method.DisplayName == ".ctor")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "host" or "connection" => "System.String",
                                _ => desiredType,
                            };
                        }
                        break;
                    case var _ when isBestHttpCoreRequestEventInfo:
                        if (method.DisplayName == ".ctor")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "request" => "BestHTTP.HTTPRequest",
                                "event" => "BestHTTP.Core.RequestEvents",
                                "newState" => "BestHTTP.HTTPRequestStates",
                                "progress" or "progressLength" => "System.Int64",
                                "data" => "System.Byte[]",
                                "dataLength" => "System.Int32",
                                _ => desiredType,
                            };
                        }
                        break;
                    case var _ when isBestHttpCoreRequestEventHelper:
                        if (method.DisplayName == "AbortRequestWhenTimedOut" && parameter.Identifier == "now")
                        {
                            desiredType = "System.DateTime";
                        }
                        else if (method.DisplayName == "AbortRequestWhenTimedOut" && parameter.Identifier == "context")
                        {
                            desiredType = "System.Object";
                        }
                        break;
                    default:
                        if (isBetterList)
                        {
                            if ((method.DisplayName is "get_Item" or "set_Item" or "Insert") &&
                                (parameter.Identifier == "i" || parameter.Identifier == "index"))
                            {
                                desiredType = "System.Int32";
                            }
                            else if (method.DisplayName is "set_Item" or "Add" or "Insert" or "Contains" or "IndexOf" or "Remove")
                            {
                                if (parameter.Identifier is "value" or "item")
                                    desiredType = genericItemType;
                            }
                            else if (method.DisplayName == "Sort" && parameter.Identifier == "comparer")
                            {
                                desiredType = compareFuncType;
                            }
                        }
                        else if (isPropertyReference)
                        {
                            if (((method.DisplayName == "set_target") && parameter.Identifier == "value") ||
                                ((method.DisplayName is ".ctor" or "Set") && parameter.Identifier == "target") ||
                                (method.DisplayName == "ToString" && parameter.Identifier == "comp"))
                            {
                                desiredType = "UnityEngine.Component";
                            }
                            else if (((method.DisplayName == "set_name") && parameter.Identifier == "value") ||
                                     (method.DisplayName == ".ctor" && parameter.Identifier == "fieldName") ||
                                     (method.DisplayName == "Set" && parameter.Identifier == "methodName") ||
                                     (method.DisplayName == "ToString" && parameter.Identifier == "property"))
                            {
                                desiredType = "System.String";
                            }
                            else if (method.DisplayName.StartsWith("Convert", StringComparison.Ordinal))
                            {
                                if (parameter.Identifier is "to" or "from")
                                    desiredType = "System.Type";
                                else if (parameter.Identifier == "value")
                                    desiredType = "System.Object";
                            }
                            else if (method.DisplayName == "Equals" && parameter.Identifier == "obj")
                            {
                                desiredType = "System.Object";
                            }
                        }
                        break;
                    case "CachedGeometries":
                        if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                            parameter.Identifier == "cache")
                        {
                            desiredType = genericStackListArrayType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "bigCache")
                        {
                            desiredType = genericLinkedListType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "source")
                        {
                            desiredType = genericListType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "verts")
                        {
                            desiredType = BuildListType(_unityVector3TypeName);
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 (parameter.Identifier == "uvs" || parameter.Identifier == "clipUVs"))
                        {
                            desiredType = vector2ListType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "cols")
                        {
                            desiredType = colorListType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "mRtpVerts")
                        {
                            desiredType = BuildListType(_unityVector3TypeName);
                        }
                        break;
                    case "ByteReader":
                        if (method.DisplayName == "ReadLine" && parameter.Identifier == "buffer")
                        {
                            desiredType = "System.Byte[]";
                        }
                        break;
                    case "MX.Logic.Data.TacticRoleConstraint":
                        if (method.DisplayName == "IsMatch" && parameter.Identifier == "tacticRole")
                            desiredType = "FlatData.TacticRole";
                        break;
                    case "MX.Data.GroundObstacleData":
                        if ((method.DisplayName == "Equals" && parameter.Identifier == "other") ||
                            ((method.DisplayName == "op_Equality" || method.DisplayName == "op_Inequality") && (parameter.Identifier == "left" || parameter.Identifier == "right")))
                        {
                            desiredType = _groundObstacleDataTypeName;
                        }
                        break;
                    case "MX.Data.GroundObstacleDataCollection":
                        if (method.DisplayName == "GetKeyForItem" && parameter.Identifier == "item")
                            desiredType = _groundObstacleDataTypeName;
                        break;
                    case "MX.Data.GroundObstacleDataHashComparer":
                        if ((method.DisplayName == "Equals" && (parameter.Identifier == "x" || parameter.Identifier == "y")) ||
                            (method.DisplayName == "Compare" && (parameter.Identifier == "x" || parameter.Identifier == "rhs")) ||
                            (method.DisplayName == "GetHashCode" && parameter.Identifier == "obj"))
                        {
                            desiredType = _groundObstacleDataTypeName;
                        }
                        break;
                    case "GroundObstacleDataRepository":
                        if (method.DisplayName == "TryGetValue" && parameter.Identifier == "value")
                        {
                            desiredType = _groundObstacleDataTypeName;
                            modifierPrefix = "out";
                        }
                        break;
                    case "FurnitureInventoryObject":
                        if (method.DisplayName == "Sync" && parameter.Identifier == "tables")
                        {
                            desiredType = furnitureDbDictionaryType;
                        }
                        else if (method.DisplayName == "Sync" && parameter.Identifier == "list")
                        {
                            desiredType = furnitureDbListType;
                        }
                        else if (method.DisplayName == "HasListFromTag" && parameter.Identifier == "furnitures")
                        {
                            desiredType = furnitureObjectListType;
                            modifierPrefix = "out";
                        }
                        else if ((method.DisplayName == "GetPlacedFurnitures" && parameter.Identifier == "dbId") ||
                                 (method.DisplayName == "FindFurniture" && parameter.Identifier == "uniqueId"))
                        {
                            desiredType = "System.Int64";
                        }
                        break;
                    case "FurnitureObject":
                        if (method.DisplayName == "set_CafeDBId" && parameter.Identifier == "value")
                        {
                            desiredType = "System.Int64";
                        }
                        else if (method.DisplayName == "set_Tags" && parameter.Identifier == "value")
                        {
                            desiredType = furnitureTagsDictionaryType;
                        }
                        else if (method.DisplayName == "set_FurnitureExcel" && parameter.Identifier == "value")
                        {
                            desiredType = furnitureExcelType;
                        }
                        else if (method.DisplayName == "set_Position" && parameter.Identifier == "value")
                        {
                            desiredType = _unityVector2TypeName;
                        }
                        else if ((method.DisplayName == "set_LeftTop" || method.DisplayName == "set_RightBottom") &&
                                 parameter.Identifier == "value")
                        {
                            desiredType = _unityVector2TypeName;
                        }
                        break;
                }

                if (isEventDelegateParameter && method.DisplayName == ".ctor")
                {
                    if (parameter.Identifier == "obj")
                    {
                        desiredType = "UnityEngine.Object";
                    }
                    else if (parameter.Identifier == "field")
                    {
                        desiredType = "System.String";
                    }
                }

                return desiredType is null
                    ? parameter
                    : parameter with
                    {
                        TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType),
                        ModifierPrefix = modifierPrefix,
                    };
        }).ToArray();
    }
}
