namespace YldaDumpCsExporter;

internal sealed partial class YldaMxFieldFamilyAdjustment
{
    private IReadOnlyList<ResolvedMethodModel> AdjustMethods()
    {
        var adjustedMethods = methods.Select(method =>
        {
            string? desiredReturnType = null;

            switch (type.FullName)
            {
                case "MXField.Shared.Model.FieldDateHistoryDB":
                    if (method.DisplayName == "get_DateId")
                        desiredReturnType = "System.Int64";
                    else if (method.DisplayName == "get_ClearDate")
                        desiredReturnType = DateTimeType;
                    break;
                case "MXField.Shared.Model.FieldInteractionDB":
                    if (method.DisplayName is "get_SeasonId" or "get_UniqueId" or "get_DateId")
                        desiredReturnType = "System.Int64";
                    else if (method.DisplayName == "get_UpdateDate")
                        desiredReturnType = DateTimeType;
                    break;
                case "MXField.Shared.Model.FieldQuestDB":
                    if (method.DisplayName is "get_SeasonId" or "get_UniqueId" or "get_DateId")
                        desiredReturnType = "System.Int64";
                    else if (method.DisplayName == "get_UpdateDate")
                        desiredReturnType = DateTimeType;
                    break;
                case "MXField.Shared.Model.FieldCharacterDB":
                    if (method.DisplayName is "get_CurrentSceneId" or "get_PreviousSceneId" or "get_LastMasteryId")
                        desiredReturnType = "System.Int64";
                    break;
                case "MXField.Shared.Model.FieldMasteryDB":
                    if (method.DisplayName == "get_Exp")
                        desiredReturnType = "System.Int64";
                    break;
                case "MXField.Shared.Model.FieldSnapshot":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_FieldSeasonId" or "get_AccountId" or "get_CurrentDateId" or "get_StartDaysSince" => "System.Int64",
                        "get_ServerTime" => DateTimeType,
                        "get_DateHistoryDBs" => fieldDateHistoryListType,
                        "get_Interactions" => fieldInteractionListType,
                        "get_MainQuests" => fieldQuestListType,
                        "get_DailyQuests" => fieldQuestListType,
                        "get_ClearDateIds" or "get_MainQuestIds" or "get_InteractionIds" or "get_EvidenceUniqueIds" => int64EnumerableType,
                        "get_SeasonInfo" => _fieldSeasonInfoTypeName,
                        _ => null,
                    };
                    break;
                case "MXField.Shared.Data.FieldQuestInfo":
                    if (method.DisplayName is "get_SeasonId" or "get_Id" or "get_DateId" or "get_RewardId" or "get_Prob" or "get_OpenDate")
                        desiredReturnType = "System.Int64";
                    break;
                case "MXField.Shared.Data.FieldQuestData":
                    desiredReturnType = method.DisplayName switch
                    {
                        "GetAllSeasonQuestInfos" or "GetAllQuestInfos" => fieldQuestInfoEnumerableType,
                        _ => null,
                    };
                    break;
                case "MXField.Network.Task.FieldSyncResponseMessage":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_Snapshot" => _fieldSnapshotTypeName,
                        "get_StageHistoryDBs" => campaignStageHistoryListType,
                        "get_PlayableDateId" => "System.Int64",
                        _ => null,
                    };
                    break;
                case "MXField.Network.Task.FieldInteractionResponseMessage":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_InteractionDB" => _fieldInteractionDbTypeName,
                        "get_MasteryDB" => _fieldMasteryDbTypeName,
                        "get_ParcelInfos" => parcelInfoListType,
                        "get_DisplaySequence" => parcelInfoListType,
                        _ => null,
                    };
                    break;
                case "MXField.Shared.Data.FieldRewardInfo":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_Id" => "System.Int64",
                        "get_ParcelInfos" => parcelInfoListType,
                        _ => null,
                    };
                    break;
                case "MXField.Shared.Data.FieldRewardData":
                    desiredReturnType = method.DisplayName switch
                    {
                        _ => null,
                    };
                    break;
                case "MXField.Level.FieldDesignLevelRoot":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_SceneInfo" => _fieldSceneInfoTypeName,
                        "get_Preloaders" => preloadRequiredListType,
                        _ => null,
                    };
                    break;
            }

            var adjustedParameters = method.Parameters.Select(parameter =>
            {
                string? desiredType = null;
                var modifierPrefix = parameter.ModifierPrefix;

                switch (type.FullName)
                {
                    case "MXField.Shared.NetworkProtocol.FieldSyncRequest":
                        if (method.DisplayName == "set_FieldSeasonId" && parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldSyncResponse":
                        if (method.DisplayName == "set_PlayableDateId" && parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        else if (method.DisplayName == "set_StageHistoryDBs" && parameter.Identifier == "value")
                            desiredType = campaignStageHistoryListType;
                        else if (method.DisplayName == "set_FieldSnapshot" && parameter.Identifier == "value")
                            desiredType = _fieldSnapshotTypeName;
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldInteractionRequest":
                        if ((method.DisplayName == "set_FieldSeasonId" || method.DisplayName == "set_UniqueId") && parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldQuestClearRequest":
                        if ((method.DisplayName == "set_FieldSeasonId" || method.DisplayName == "set_UniqueId") && parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldSceneChangedRequest":
                        if ((method.DisplayName == "set_FieldSeasonId" || method.DisplayName == "set_DateId" || method.DisplayName == "set_SceneId") && parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldEndDateRequest":
                        if ((method.DisplayName == "set_FieldSeasonId" || method.DisplayName == "set_DateId") && parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldEnterStageRequest":
                        if ((method.DisplayName == "set_FieldSeasonId" || method.DisplayName == "set_StageUniqueId" || method.DisplayName == "set_LastEnterStageEchelonNumber") && parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldStageResultRequest":
                        if (method.DisplayName == "set_FieldSeasonId" && parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldEndDateResponse":
                        if (method.DisplayName == "set_DateHistoryDB" && parameter.Identifier == "value")
                            desiredType = _fieldDateHistoryDbTypeName;
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldInteractionResponse":
                        desiredType = method.DisplayName switch
                        {
                            "set_InteractionDB" when parameter.Identifier == "value" => _fieldInteractionDbTypeName,
                            "set_CharacterDB" when parameter.Identifier == "value" => _fieldCharacterDbTypeName,
                            "set_MasteryDB" when parameter.Identifier == "value" => _fieldMasteryDbTypeName,
                            "set_ParcelResultDB" when parameter.Identifier == "value" => _parcelResultDbTypeName,
                            _ => null,
                        };
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldQuestClearResponse":
                        if (method.DisplayName == "set_Quest" && parameter.Identifier == "value")
                            desiredType = _fieldQuestDbTypeName;
                        break;
                    case "MXField.Shared.NetworkProtocol.FieldStageResultResponse":
                        desiredType = method.DisplayName switch
                        {
                            "set_CampaignStageHistoryDB" when parameter.Identifier == "value" => _campaignStageHistoryDbTypeName,
                            "set_LevelUpCharacterDBs" when parameter.Identifier == "value" => characterDbListType,
                            "set_FirstClearReward" when parameter.Identifier == "value" => parcelInfoListType,
                            "set_ThreeStarReward" when parameter.Identifier == "value" => parcelInfoListType,
                            _ => null,
                        };
                        break;
                    case "MXField.Shared.Model.FieldDateHistoryDB":
                        desiredType = method.DisplayName switch
                        {
                            "set_DateId" when parameter.Identifier == "value" => "System.Int64",
                            "set_ClearDate" when parameter.Identifier == "value" => DateTimeType,
                            _ => null,
                        };
                        break;
                    case "MXField.Shared.Model.FieldInteractionDB":
                        desiredType = method.DisplayName switch
                        {
                            "set_SeasonId" or "set_UniqueId" when parameter.Identifier == "value" => "System.Int64",
                            "set_UpdateDate" when parameter.Identifier == "value" => DateTimeType,
                            "Equals" when parameter.Identifier == "other" => _fieldInteractionDbTypeName,
                            _ => null,
                        };
                        break;
                    case "MXField.Shared.Model.FieldQuestDB":
                        desiredType = method.DisplayName switch
                        {
                            "set_SeasonId" or "set_UniqueId" when parameter.Identifier == "value" => "System.Int64",
                            "set_UpdateDate" when parameter.Identifier == "value" => DateTimeType,
                            ".ctor" when parameter.Identifier is "seasonId" or "uniqueId" => "System.Int64",
                            ".ctor" when parameter.Identifier == "serverTime" => DateTimeType,
                            "Clear" when parameter.Identifier == "serverTime" => DateTimeType,
                            _ => null,
                        };
                        break;
                    case "MXField.Shared.Model.FieldCharacterDB":
                        desiredType = method.DisplayName switch
                        {
                            "set_CurrentSceneId" or "set_PreviousSceneId" or "set_LastMasteryId" when parameter.Identifier == "value" => "System.Int64",
                            ".ctor" when parameter.Identifier == "sceneId" => "System.Int64",
                            "CreateCharacterDB" when parameter.Identifier == "seasonId" => "System.Int64",
                            "SceneChange" when parameter.Identifier is "seasonId" or "dateId" or "sceneId" => "System.Int64",
                            "MasteryUpdate" when parameter.Identifier == "uniqueId" => "System.Int64",
                            "CheckMasteryOrder" when parameter.Identifier is "seasonId" or "ineteractionId" => "System.Int64",
                            _ => null,
                        };
                        break;
                    case "MXField.Shared.Model.FieldMasteryDB":
                        desiredType = method.DisplayName switch
                        {
                            "set_Exp" when parameter.Identifier == "value" => "System.Int64",
                            "LevelUp" when parameter.Identifier is "seasonId" or "gainExp" => "System.Int64",
                            _ => null,
                        };
                        break;
                    case "MXField.Shared.Model.FieldSnapshot":
                        desiredType = method.DisplayName switch
                        {
                            "set_FieldSeasonId" or "set_AccountId" when parameter.Identifier == "value" => "System.Int64",
                            "set_ServerTime" when parameter.Identifier == "value" => DateTimeType,
                            "set_DateHistoryDBs" when parameter.Identifier == "value" => fieldDateHistoryListType,
                            "set_Interactions" when parameter.Identifier == "value" => fieldInteractionListType,
                            "set_MainQuests" when parameter.Identifier == "value" => fieldQuestListType,
                            "set_DailyQuests" when parameter.Identifier == "value" => fieldQuestListType,
                            ".ctor" when parameter.Identifier is "accountId" or "fieldSeasonId" => "System.Int64",
                            ".ctor" when parameter.Identifier == "serverTime" => DateTimeType,
                            ".ctor" when parameter.Identifier == "dateHistoryDBs" => fieldDateHistoryIListType,
                            ".ctor" when parameter.Identifier == "interactionDBs" => fieldInteractionIListType,
                            ".ctor" when parameter.Identifier is "mainQuestDBs" or "dalyQuestDBs" => fieldQuestIListType,
                            "TryGetPlayableDateId" when parameter.Identifier == "dateId" => "System.Int64",
                            "CheckOpenCondition" when parameter.Identifier == "stageUniqueIds" => int64EnumerableType,
                            "CreateDailyQuests" when parameter.Identifier == "playableDateId" => "System.Int64",
                            _ => null,
                        };
                        if (method.DisplayName == "TryGetPlayableDateId" && parameter.Identifier == "dateId")
                            modifierPrefix = "out";
                        break;
                    case "MXField.Shared.Data.FieldQuestData":
                        desiredType = method.DisplayName switch
                        {
                            "GetAllSeasonQuestInfos" when parameter.Identifier == "seasonId" => "System.Int64",
                            "TryGetSeasonQuestInfo" when parameter.Identifier is "seasonId" or "questId" => "System.Int64",
                            "TryGetSeasonQuestInfo" when parameter.Identifier == "questInfo" => _fieldQuestInfoTypeName,
                            "TryGetDailyQuestInfos" when parameter.Identifier == "fieldSeasonId" => "System.Int64",
                            "TryGetDailyQuestInfos" when parameter.Identifier == "infos" => fieldQuestInfoEnumerableType,
                            "TryGetQuestInfosByDate" when parameter.Identifier is "seasonId" or "fieldDateId" => "System.Int64",
                            "TryGetQuestInfosByDate" when parameter.Identifier == "infos" => fieldQuestInfoEnumerableType,
                            "TryGetQuestInfo" when parameter.Identifier == "questId" => "System.Int64",
                            "TryGetQuestInfo" when parameter.Identifier == "questInfo" => _fieldQuestInfoTypeName,
                            "TryGetQuestInfoByAssetPath" when parameter.Identifier == "questInfo" => _fieldQuestInfoTypeName,
                            _ => null,
                        };
                        if (method.DisplayName is "TryGetSeasonQuestInfo" or "TryGetDailyQuestInfos" or "TryGetQuestInfosByDate" or "TryGetQuestInfo" or "TryGetQuestInfoByAssetPath")
                        {
                            if (parameter.Identifier is "questInfo" or "infos")
                                modifierPrefix = "out";
                        }
                        break;
                    case "MXField.Shared.Data.FieldRewardInfo":
                        desiredType = method.DisplayName switch
                        {
                            "set_ParcelInfos" when parameter.Identifier == "value" => parcelInfoListType,
                            ".ctor" when parameter.Identifier == "id" => "System.Int64",
                            _ => null,
                        };
                        break;
                    case "MXField.Shared.Data.FieldRewardData":
                        desiredType = method.DisplayName switch
                        {
                            "TryGetRewardInfo" when parameter.Identifier == "uniqueId" => "System.Int64",
                            "TryGetRewardInfo" when parameter.Identifier == "info" => _fieldRewardInfoTypeName,
                            "TryGetAllRewardInfos" when parameter.Identifier == "rewardInfos" => rewardInfoEnumerableType,
                            _ => null,
                        };
                        if (method.DisplayName is "TryGetRewardInfo" or "TryGetAllRewardInfos")
                        {
                            if (parameter.Identifier is "info" or "rewardInfos")
                                modifierPrefix = "out";
                        }
                        break;
                    case "MXField.Network.Task.FieldInteractionResponseMessage":
                        desiredType = method.DisplayName switch
                        {
                            ".ctor" when parameter.Identifier == "response" => "MXField.Shared.NetworkProtocol.FieldInteractionResponse",
                            _ => null,
                        };
                        break;
                    case "MXField.Network.Task.FieldSyncResponseMessage":
                        desiredType = method.DisplayName switch
                        {
                            ".ctor" when parameter.Identifier == "response" => "MXField.Shared.NetworkProtocol.FieldSyncResponse",
                            _ => null,
                        };
                        break;
                    case "MXField.Level.FieldDesignLevelRoot":
                        desiredType = method.DisplayName switch
                        {
                            "set_SceneInfo" when parameter.Identifier == "value" => _fieldSceneInfoTypeName,
                            "set_Preloaders" when parameter.Identifier == "value" => preloadRequiredListType,
                            "SetSceneInfo" when parameter.Identifier == "sceneInfo" => _fieldSceneInfoTypeName,
                            "HandlePreloadComplete" when parameter.Identifier == "preloader" => _iPreloadRequiredTypeName,
                            _ => null,
                        };
                        break;
                }

                return desiredType is null
                    ? parameter with { ModifierPrefix = modifierPrefix }
                    : parameter with { TypeName = PreferFieldFamilyType(parameter.TypeName, desiredType), ModifierPrefix = modifierPrefix };
            }).ToArray();

            return method with
            {
                ReturnTypeName = desiredReturnType is null ? method.ReturnTypeName : PreferFieldFamilyType(method.ReturnTypeName, desiredReturnType),
                Parameters = adjustedParameters,
            };
        }).ToArray();

        return adjustedMethods;
    }
}
