namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private IReadOnlyList<ResolvedFieldModel> AdjustFields()
    {
        var adjustedFields = fields.Select(field =>
        {
            var desiredType = DesiredFieldType(field.Identifier);
            var adjustedField = desiredType is null
                ? field
                : field with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(field.TypeName, desiredType) };

            if ((isAutoUseRuleDao || isConstraintStruct || isAreaCollisionProperty || isPositionSetting) &&
                string.Equals(field.Identifier, "Empty", StringComparison.Ordinal))
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "static", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            if (isFurnitureFilter &&
                (string.Equals(field.Identifier, "CategoryList", StringComparison.Ordinal) ||
                 string.Equals(field.Identifier, "SubCategoryList", StringComparison.Ordinal)))
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            if (isBitPackFormatter && field.Identifier == "Default")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "static", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isWebRequestUtils && field.Identifier == "domainRegex")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["private", "static"],
                    Accessibility = ExportMemberAccessibility.Private,
                };
            }
            else if (isFlatBuffersByteBuffer)
            {
                adjustedField = field.Identifier switch
                {
                    "_buffer" => adjustedField with { Modifiers = ["protected"], Accessibility = ExportMemberAccessibility.Protected },
                    "_pos" or "floathelper" or "inthelper" or "doublehelper" or "ulonghelper"
                        => adjustedField with { Modifiers = ["private"], Accessibility = ExportMemberAccessibility.Private },
                    _ => adjustedField,
                };
            }
            else if (isAddTypeMenuAttribute)
            {
                adjustedField = field.Identifier switch
                {
                    "_MenuName_k__BackingField" or "_Order_k__BackingField" => adjustedField with
                    {
                        Modifiers = ["private", "readonly"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "k_Separeters" => adjustedField with
                    {
                        Modifiers = ["private", "static", "readonly"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    _ => adjustedField,
                };
            }
            else if (isGenericGraphNodeMetadata)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isSkeletonAnimationPlayableHandle && field.Identifier == "skeletonAnimation")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isSignalRCoreStreamItemContainer)
            {
                adjustedField = field.Identifier switch
                {
                    "id" => adjustedField with
                    {
                        Modifiers = ["public", "readonly"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    "_Items_k__BackingField" or "<Items>k__BackingField" or "_LastAdded_k__BackingField" or "<LastAdded>k__BackingField" => adjustedField with
                    {
                        Modifiers = ["private"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "IsCanceled" => adjustedField with
                    {
                        Modifiers = ["public"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    _ => adjustedField,
                };
            }
            else if (isSignalRCoreCallbackDescriptor || isSignalRCoreInvocationDefinition)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isSocketIO3EventsCallbackDescriptor)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isSocketIO3EventsSubscription && field.Identifier == "callbacks")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isBestHttpCoreConnectionEventInfo || isBestHttpCoreRequestEventInfo)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isBestHttpCoreConnectionEventHelper || isBestHttpCoreRequestEventHelper)
            {
                adjustedField = field.Identifier switch
                {
                    "connectionEventQueue" or "requestEventQueue" => adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "OnEvent" => adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    _ => adjustedField,
                };
            }
            else if (isBestHttpCoreHostConnection)
            {
                adjustedField = field.Identifier switch
                {
                    "Connections" or "Queue" => adjustedField with
                    {
                        Modifiers = ["private"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    _ => adjustedField,
                };
            }
            else if (isBestHttpCoreHostDefinition)
            {
                adjustedField = field.Identifier switch
                {
                    "Alternates" or "hostConnectionVariant" => adjustedField with
                    {
                        Modifiers = ["public"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    "keyBuilder" or "keyBuilderLock" => adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    _ => adjustedField,
                };
            }
            else if (isBestHttpCoreHostConnectionKey)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isBestHttpCorePluginEventInfo ||
                     isBestHttpCoreAltSvcEventInfo ||
                     isBestHttpCoreHttp2ConnectProtocolInfo ||
                     isBestHttpCoreProtocolEventInfo)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isBestHttpCorePluginEventHelper)
            {
                adjustedField = field.Identifier switch
                {
                    "pluginEvents" => adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "OnEvent" => adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    _ => adjustedField,
                };
            }
            else if (isBestHttpCoreProtocolEventHelper)
            {
                adjustedField = field.Identifier switch
                {
                    "protocolEvents" or "ActiveProtocols" => adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "OnEvent" => adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    _ => adjustedField,
                };
            }

            if (isFurnitureInventoryObject &&
                string.Equals(field.Identifier, "filterOption", StringComparison.Ordinal))
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["private"],
                    Accessibility = ExportMemberAccessibility.Private,
                };
            }

            return adjustedField;
        }).ToArray();

        return adjustedFields;
    }
}
