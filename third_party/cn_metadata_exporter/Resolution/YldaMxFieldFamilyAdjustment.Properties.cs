namespace YldaDumpCsExporter;

internal sealed partial class YldaMxFieldFamilyAdjustment
{
    private IReadOnlyList<ResolvedPropertyModel> AdjustProperties()
    {
        string? DesiredPropertyType(string displayName)
        {
            return type.FullName switch
            {
                "MXField.Shared.NetworkProtocol.FieldSyncRequest" when displayName == "FieldSeasonId" => "System.Int64",
                "MXField.Shared.NetworkProtocol.FieldSyncResponse" => displayName switch
                {
                    "FieldSnapshot" => _fieldSnapshotTypeName,
                    "PlayableDateId" => "System.Int64",
                    "StageHistoryDBs" => campaignStageHistoryListType,
                    _ => null,
                },
                "MXField.Network.Task.FieldSyncResponseMessage" => displayName switch
                {
                    "Snapshot" => _fieldSnapshotTypeName,
                    "StageHistoryDBs" => campaignStageHistoryListType,
                    "PlayableDateId" => "System.Int64",
                    _ => null,
                },
                "MXField.Shared.NetworkProtocol.FieldInteractionRequest" => displayName is "FieldSeasonId" or "UniqueId" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldInteractionResponse" => displayName switch
                {
                    "InteractionDB" => _fieldInteractionDbTypeName,
                    "CharacterDB" => _fieldCharacterDbTypeName,
                    "MasteryDB" => _fieldMasteryDbTypeName,
                    "ParcelResultDB" => _parcelResultDbTypeName,
                    _ => null,
                },
                "MXField.Shared.NetworkProtocol.FieldQuestClearRequest" => displayName is "FieldSeasonId" or "UniqueId" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldQuestClearResponse" when displayName == "Quest" => _fieldQuestDbTypeName,
                "MXField.Shared.NetworkProtocol.FieldSceneChangedRequest" => displayName is "FieldSeasonId" or "DateId" or "SceneId" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldEndDateRequest" => displayName is "FieldSeasonId" or "DateId" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldEndDateResponse" when displayName == "DateHistoryDB" => _fieldDateHistoryDbTypeName,
                "MXField.Shared.NetworkProtocol.FieldEnterStageRequest" => displayName is "FieldSeasonId" or "StageUniqueId" or "LastEnterStageEchelonNumber" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldStageResultRequest" when displayName == "FieldSeasonId" => "System.Int64",
                "MXField.Shared.NetworkProtocol.FieldStageResultResponse" => displayName switch
                {
                    "CampaignStageHistoryDB" => _campaignStageHistoryDbTypeName,
                    "LevelUpCharacterDBs" => characterDbListType,
                    "FirstClearReward" => parcelInfoListType,
                    "ThreeStarReward" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldDateHistoryDB" => displayName switch
                {
                    "DateId" => "System.Int64",
                    "ClearDate" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldInteractionDB" => displayName switch
                {
                    "SeasonId" or "UniqueId" or "DateId" => "System.Int64",
                    "UpdateDate" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldQuestDB" => displayName switch
                {
                    "SeasonId" or "UniqueId" or "DateId" => "System.Int64",
                    "UpdateDate" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldCharacterDB" => displayName is "CurrentSceneId" or "PreviousSceneId" or "LastMasteryId" ? "System.Int64" : null,
                "MXField.Shared.Model.FieldMasteryDB" when displayName == "Exp" => "System.Int64",
                "MXField.Shared.Model.FieldSnapshot" => displayName switch
                {
                    "FieldSeasonId" or "AccountId" or "CurrentDateId" or "StartDaysSince" => "System.Int64",
                    "ServerTime" => DateTimeType,
                    "DateHistoryDBs" => fieldDateHistoryListType,
                    "Interactions" => fieldInteractionListType,
                    "MainQuests" => fieldQuestListType,
                    "DailyQuests" => fieldQuestListType,
                    "ClearDateIds" or "MainQuestIds" or "InteractionIds" or "EvidenceUniqueIds" => int64EnumerableType,
                    "SeasonInfo" => _fieldSeasonInfoTypeName,
                    _ => null,
                },
                "MXField.Shared.Data.FieldQuestInfo" => displayName is "SeasonId" or "Id" or "DateId" or "RewardId" or "Prob" or "OpenDate" ? "System.Int64" : null,
                "MXField.Shared.Data.FieldRewardInfo" => displayName switch
                {
                    "Id" => "System.Int64",
                    "ParcelInfos" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Shared.Data.FieldRewardData" => displayName switch
                {
                    _ => null,
                },
                "MXField.Network.Task.FieldInteractionResponseMessage" => displayName switch
                {
                    "InteractionDB" => _fieldInteractionDbTypeName,
                    "MasteryDB" => _fieldMasteryDbTypeName,
                    "ParcelInfos" => parcelInfoListType,
                    "DisplaySequence" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Level.FieldDesignLevelRoot" => displayName switch
                {
                    "SceneInfo" => _fieldSceneInfoTypeName,
                    "Preloaders" => preloadRequiredListType,
                    _ => null,
                },
                _ => null,
            };
        }

        var adjustedProperties = properties.Select(property =>
        {
            var desiredType = DesiredPropertyType(property.DisplayName);
            return desiredType is null ? property : property with { TypeName = PreferFieldFamilyType(property.TypeName, desiredType) };
        }).ToArray();

        return adjustedProperties;
    }
}
