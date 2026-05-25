using static YldaDumpCsExporter.YldaTypeNameHelpers;

namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private IReadOnlyList<ResolvedPropertyModel> AdjustProperties()
    {
        string? DesiredPropertyType(string identifier) => type.FullName switch
        {
            "AccountBillingInfo" => identifier switch
            {
                "MonthlyProductRewards" => monthlyProductRewardsType,
                "RepurchasableProductPurchaseCountDBList" => purchaseCountDbListType,
                "RepurchasableProductList" => repurchasableProductListType,
                "NewProductList" => purchaseCountDbListType,
                "PurchaseCountList" => purchaseCountDbListType,
                "BlockedProductList" => blockedProductDbListType,
                _ => null,
            },
            "ByteReader" => identifier switch
            {
                _ => null,
            },
            "BMFont" => identifier switch
            {
                "glyphs" => bmGlyphListType,
                _ => null,
            },
            "UIDrawCall" => identifier switch
            {
                "list" or "activeList" or "inactiveList" => uiDrawCallListType,
                "cachedTransform" => transformType,
                "baseMaterial" or "dynamicMaterial" => materialType,
                _ => null,
            },
            _ when isBetterList => identifier switch
            {
                "Item" => genericItemType,
                _ => null,
            },
            "EventDelegate" => identifier switch
            {
                "target" => "UnityEngine.MonoBehaviour",
                "methodName" => "System.String",
                "parameters" => eventDelegateParameterArrayType,
                _ => null,
            },
            "FurnitureObject" => identifier switch
            {
                "CafeDBId" => "System.Int64",
                "LevelUpFeedCostAmount" => "System.Int64",
                "LevelUpFeedExp" => "System.Int64",
                "SetGroupId" => "System.Int64",
                "Tags" => furnitureTagsDictionaryType,
                "AvailableCharacterStates" => furnitureTimelineStateListType,
                "FurnitureExcel" => furnitureExcelType,
                "InvalidId" => "System.Int64",
                _ => null,
            },
            _ when isFurnitureFilter => identifier switch
            {
                _ => null,
            },
            _ when isWwwForm => identifier switch
            {
                "headers" => BuildDictionaryType("System.String", "System.String"),
                "data" => byteArrayType,
                _ => null,
            },
            _ when isSignalRCoreUploadItemController => identifier switch
            {
                "StreamingIDs" => stringArrayType,
                "Hub" => _hubConnectionTypeName,
                _ => null,
            },
            _ when isBestHttpCoreHostConnection => identifier switch
            {
                "LastProtocolSupportUpdate" => "System.DateTime",
                _ => null,
            },
            _ when isSignalRCoreStreamItemContainer => identifier switch
            {
                "Items" => genericListType,
                "LastAdded" => genericItemType,
                _ => null,
            },
            _ when isSocketIO3EventsTypedEventTable => identifier switch
            {
                _ => null,
            },
            _ => null,
        };

        var adjustedProperties = properties.Select(property =>
        {
            var desiredType = DesiredPropertyType(property.DisplayName);
            return desiredType is null
                ? property
                : property with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(property.TypeName, desiredType) };
        }).ToArray();

        return adjustedProperties;
    }
}
