namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private IReadOnlyList<ResolvedMethodModel> AdjustMethods()
        => methods.Select(AdjustMethod).Select(ApplyFurnitureMethodReturnOverrides).ToArray();

    private ResolvedMethodModel AdjustMethod(ResolvedMethodModel method)
    {
        var adjustedParameters = AdjustInitialParameters(method);
        var desiredReturnType = ResolveDesiredMethodReturnType(method, adjustedParameters);
        adjustedParameters = AdjustSecondaryParameters(method, adjustedParameters);
        var adjustedDisplayName = ResolveAdjustedDisplayName(method, adjustedParameters);
        var adjustedMethod = method with
        {
            DisplayName = adjustedDisplayName,
            Parameters = adjustedParameters,
        };

        if (desiredReturnType is not null)
        {
            adjustedMethod = adjustedMethod with
            {
                ReturnTypeName = forceReferenceTypes
                    ? desiredReturnType
                    : PreferReferenceType(adjustedMethod.ReturnTypeName, desiredReturnType),
            };
        }

        if (isFurnitureObject &&
            method.DisplayName is "set_LeftTop" or "set_RightBottom")
        {
            adjustedMethod = adjustedMethod with
            {
                ReturnTypeName = "System.Void",
                Modifiers = ["private"],
                Accessibility = ExportMemberAccessibility.Private,
            };
        }

        if (isFurnitureFilter &&
            method.DisplayName == "<>iFixBaseProxy_IsShowAfterFiltering")
        {
            adjustedMethod = adjustedMethod with
            {
                Parameters = adjustedMethod.Parameters.Select(parameter =>
                    parameter.Identifier == "P0"
                        ? parameter with { TypeName = assetObjectBaseType! }
                        : parameter).ToArray(),
            };
        }

        return adjustedMethod;
    }

    private ResolvedMethodModel ApplyFurnitureMethodReturnOverrides(ResolvedMethodModel method)
    {
            string? desiredType = null;
            if (type.FullName == "FurnitureObject")
            {
                desiredType = method.DisplayName switch
                {
                    "get_CafeDBId" or "get_LevelUpFeedCostAmount" or "get_LevelUpFeedExp" or "get_SetGroupId" or "get_InvalidId" => "System.Int64",
                    "get_Tags" => furnitureTagsDictionaryType,
                    "get_AvailableCharacterStates" => furnitureTimelineStateListType,
                    "get_FurnitureExcel" => furnitureExcelType,
                    "set_CafeDBId" or "set_Tags" or "set_FurnitureExcel" or "set_Position" or "set_LeftTop" or "set_RightBottom" => "System.Void",
                    _ => null,
                };
            }
            else if (type.FullName == "FurnitureInventoryObject")
            {
                desiredType = method.DisplayName switch
                {
                    "GetLevelExp" => "System.Int64",
                    "GetPlacedFurnitures" or "GetAllPlacedFurnitures" => furnitureObjectEnumerableType,
                    "FindFurniture" => "FurnitureObject",
                    _ => null,
                };
            }

            return desiredType is null
                ? method
                : method with { ReturnTypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(method.ReturnTypeName, desiredType) };
    }
}
