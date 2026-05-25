namespace YldaDumpCsExporter;

internal sealed partial class YldaMxFieldFamilyAdjustment
{
    private IReadOnlyList<ResolvedFieldModel> AdjustFields()
    {
        string? DesiredFieldType(string identifier)
        {
            return type.FullName switch
            {
                "MXField.Shared.NetworkProtocol.FieldSyncRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldSyncResponse" => identifier switch
                {
                    "<FieldSnapshot>k__BackingField" or "_FieldSnapshot_k__BackingField" => _fieldSnapshotTypeName,
                    "<PlayableDateId>k__BackingField" or "_PlayableDateId_k__BackingField" => "System.Int64",
                    "<StageHistoryDBs>k__BackingField" or "_StageHistoryDBs_k__BackingField" => campaignStageHistoryListType,
                    _ => null,
                },
                "MXField.Network.Task.FieldSyncResponseMessage" => identifier switch
                {
                    "<Snapshot>k__BackingField" or "_Snapshot_k__BackingField" => _fieldSnapshotTypeName,
                    "<StageHistoryDBs>k__BackingField" or "_StageHistoryDBs_k__BackingField" => campaignStageHistoryListType,
                    "<PlayableDateId>k__BackingField" or "_PlayableDateId_k__BackingField" => "System.Int64",
                    _ => null,
                },
                "MXField.Shared.NetworkProtocol.FieldInteractionRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<UniqueId>k__BackingField" or "_UniqueId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldInteractionResponse" => identifier switch
                {
                    "<InteractionDB>k__BackingField" or "_InteractionDB_k__BackingField" => _fieldInteractionDbTypeName,
                    "<CharacterDB>k__BackingField" or "_CharacterDB_k__BackingField" => _fieldCharacterDbTypeName,
                    "<MasteryDB>k__BackingField" or "_MasteryDB_k__BackingField" => _fieldMasteryDbTypeName,
                    "<ParcelResultDB>k__BackingField" or "_ParcelResultDB_k__BackingField" => _parcelResultDbTypeName,
                    _ => null,
                },
                "MXField.Shared.NetworkProtocol.FieldQuestClearRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<UniqueId>k__BackingField" or "_UniqueId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldQuestClearResponse" => identifier is "<Quest>k__BackingField" or "_Quest_k__BackingField" ? _fieldQuestDbTypeName : null,
                "MXField.Shared.NetworkProtocol.FieldSceneChangedRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<DateId>k__BackingField" or "_DateId_k__BackingField" or "<SceneId>k__BackingField" or "_SceneId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldEndDateRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<DateId>k__BackingField" or "_DateId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldEndDateResponse" => identifier is "<DateHistoryDB>k__BackingField" or "_DateHistoryDB_k__BackingField" ? _fieldDateHistoryDbTypeName : null,
                "MXField.Shared.NetworkProtocol.FieldEnterStageRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<StageUniqueId>k__BackingField" or "_StageUniqueId_k__BackingField" or "<LastEnterStageEchelonNumber>k__BackingField" or "_LastEnterStageEchelonNumber_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldStageResultRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldStageResultResponse" => identifier switch
                {
                    "<CampaignStageHistoryDB>k__BackingField" or "_CampaignStageHistoryDB_k__BackingField" => _campaignStageHistoryDbTypeName,
                    "<LevelUpCharacterDBs>k__BackingField" or "_LevelUpCharacterDBs_k__BackingField" => characterDbListType,
                    "<FirstClearReward>k__BackingField" or "_FirstClearReward_k__BackingField" => parcelInfoListType,
                    "<ThreeStarReward>k__BackingField" or "_ThreeStarReward_k__BackingField" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldDateHistoryDB" => identifier switch
                {
                    "<DateId>k__BackingField" or "_DateId_k__BackingField" => "System.Int64",
                    "<ClearDate>k__BackingField" or "_ClearDate_k__BackingField" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldInteractionDB" => identifier switch
                {
                    "<SeasonId>k__BackingField" or "_SeasonId_k__BackingField" => "System.Int64",
                    "<UniqueId>k__BackingField" or "_UniqueId_k__BackingField" => "System.Int64",
                    "<UpdateDate>k__BackingField" or "_UpdateDate_k__BackingField" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldQuestDB" => identifier switch
                {
                    "<SeasonId>k__BackingField" or "_SeasonId_k__BackingField" => "System.Int64",
                    "<UniqueId>k__BackingField" or "_UniqueId_k__BackingField" => "System.Int64",
                    "<UpdateDate>k__BackingField" or "_UpdateDate_k__BackingField" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldCharacterDB" => identifier is "<CurrentSceneId>k__BackingField" or "_CurrentSceneId_k__BackingField" or "<PreviousSceneId>k__BackingField" or "_PreviousSceneId_k__BackingField" or "<LastMasteryId>k__BackingField" or "_LastMasteryId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.Model.FieldMasteryDB" => identifier is "<Exp>k__BackingField" or "_Exp_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.Model.FieldSnapshot" => identifier switch
                {
                    "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" => "System.Int64",
                    "<AccountId>k__BackingField" or "_AccountId_k__BackingField" => "System.Int64",
                    "<ServerTime>k__BackingField" or "_ServerTime_k__BackingField" => DateTimeType,
                    "<DateHistoryDBs>k__BackingField" or "_DateHistoryDBs_k__BackingField" => fieldDateHistoryListType,
                    "<Interactions>k__BackingField" or "_Interactions_k__BackingField" => fieldInteractionListType,
                    "<MainQuests>k__BackingField" or "_MainQuests_k__BackingField" => fieldQuestListType,
                    "<DailyQuests>k__BackingField" or "_DailyQuests_k__BackingField" => fieldQuestListType,
                    "_seasonInfoCache" => _fieldSeasonInfoTypeName,
                    _ => null,
                },
                "MXField.Shared.Data.FieldQuestInfo" => identifier switch
                {
                    "<SeasonId>k__BackingField" or "_SeasonId_k__BackingField" => "System.Int64",
                    "<Id>k__BackingField" or "_Id_k__BackingField" => "System.Int64",
                    "<DateId>k__BackingField" or "_DateId_k__BackingField" => "System.Int64",
                    "<RewardId>k__BackingField" or "_RewardId_k__BackingField" => "System.Int64",
                    "<Prob>k__BackingField" or "_Prob_k__BackingField" => "System.Int64",
                    "<OpenDate>k__BackingField" or "_OpenDate_k__BackingField" => "System.Int64",
                    _ => null,
                },
                "MXField.Shared.Data.FieldQuestData" => identifier switch
                {
                    "questInfoDict" => questInfoDictionaryType,
                    "originalQuestInfoDict" => originalQuestInfoDictionaryType,
                    _ => null,
                },
                "MXField.Shared.Data.FieldRewardInfo" => identifier switch
                {
                    "<Id>k__BackingField" or "_Id_k__BackingField" => "System.Int64",
                    "<ParcelInfos>k__BackingField" or "_ParcelInfos_k__BackingField" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Shared.Data.FieldRewardData" => identifier is "fieldRewardInfos" ? rewardInfoDictionaryType : null,
                "MXField.Network.Task.FieldInteractionResponseMessage" => identifier switch
                {
                    "<InteractionDB>k__BackingField" or "_InteractionDB_k__BackingField" => _fieldInteractionDbTypeName,
                    "<MasteryDB>k__BackingField" or "_MasteryDB_k__BackingField" => _fieldMasteryDbTypeName,
                    "<ParcelInfos>k__BackingField" or "_ParcelInfos_k__BackingField" => parcelInfoListType,
                    "<DisplaySequence>k__BackingField" or "_DisplaySequence_k__BackingField" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Level.FieldDesignLevelRoot" => identifier switch
                {
                    "<SceneInfo>k__BackingField" or "_SceneInfo_k__BackingField" => _fieldSceneInfoTypeName,
                    "<Preloaders>k__BackingField" or "_Preloaders_k__BackingField" => preloadRequiredListType,
                    _ => null,
                },
                "MXField.LUT.IntStringPair" => identifier switch
                {
                    "Key" => "System.Int32",
                    "Value" => "System.String",
                    _ => null,
                },
                "MXField.LUT.IntStringLUT" => identifier is "pairs" ? intStringPairArrayType : null,
                _ => null,
            };
        }

        var adjustedFields = fields.Select(field =>
        {
            var desiredType = DesiredFieldType(field.Identifier);
            return desiredType is null ? field : field with { TypeName = PreferFieldFamilyType(field.TypeName, desiredType) };
        }).ToArray();

        return adjustedFields;
    }
}
