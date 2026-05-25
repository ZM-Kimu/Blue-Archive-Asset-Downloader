using static YldaDumpCsExporter.YldaTypeNameHelpers;

namespace YldaDumpCsExporter;

internal sealed class YldaFieldBridgeResolver
{
    private readonly string? _campaignStageHistoryDbTypeName;
    private readonly string? _campaignStageInfoTypeName;
    private readonly string? _eventContentSeasonInfoTypeName;
    private readonly string? _fieldContentStageInfoTypeName;
    private readonly string? _fieldDateInfoTypeName;
    private readonly string? _fieldGameManagerDisplayClass82TypeName;
    private readonly string? _fieldInteractionInfoTypeName;
    private readonly string? _fieldInteractionRequestTypeName;
    private readonly string? _fieldInteractionResponseTypeName;
    private readonly string? _fieldQuestDbTypeName;
    private readonly string? _fieldSaveRepositoryTypeName;
    private readonly string? _fieldSaveSoTypeName;
    private readonly string? _fieldSceneInfoTypeName;
    private readonly string? _fieldSeasonInfoTypeName;
    private readonly string? _mxContentBridgeTypeName;
    private readonly string? _uiFieldLobbyTypeName;

    public YldaFieldBridgeResolver(YldaKnownTypeCatalog knownTypes)
    {
        _campaignStageHistoryDbTypeName = knownTypes.CampaignStageHistoryDbTypeName;
        _campaignStageInfoTypeName = knownTypes.CampaignStageInfoTypeName;
        _eventContentSeasonInfoTypeName = knownTypes.EventContentSeasonInfoTypeName;
        _fieldContentStageInfoTypeName = knownTypes.FieldContentStageInfoTypeName;
        _fieldDateInfoTypeName = knownTypes.FieldDateInfoTypeName;
        _fieldGameManagerDisplayClass82TypeName = knownTypes.FieldGameManagerDisplayClass82TypeName;
        _fieldInteractionInfoTypeName = knownTypes.FieldInteractionInfoTypeName;
        _fieldInteractionRequestTypeName = knownTypes.FieldInteractionRequestTypeName;
        _fieldInteractionResponseTypeName = knownTypes.FieldInteractionResponseTypeName;
        _fieldQuestDbTypeName = knownTypes.FieldQuestDbTypeName;
        _fieldSaveRepositoryTypeName = knownTypes.FieldSaveRepositoryTypeName;
        _fieldSaveSoTypeName = knownTypes.FieldSaveSoTypeName;
        _fieldSceneInfoTypeName = knownTypes.FieldSceneInfoTypeName;
        _fieldSeasonInfoTypeName = knownTypes.FieldSeasonInfoTypeName;
        _mxContentBridgeTypeName = knownTypes.MxContentBridgeTypeName;
        _uiFieldLobbyTypeName = knownTypes.UiFieldLobbyTypeName;
    }

    public YldaResolvedMemberSet ApplyFieldBridgeAdjustments(
        TypeDefinition type,
        string? declaringType,
        YldaResolvedMemberSet members)
    {
        var relationships = members.Relationships;
        var fields = members.Fields;
        var properties = members.Properties;
        var events = members.Events;
        var methods = members.Methods;
        static bool MatchesFamily(TypeDefinition candidateType, string? candidateDeclaringType, string fullName, string simpleName)
            => string.Equals(candidateType.FullName, fullName, StringComparison.Ordinal) ||
               string.Equals(candidateType.Name, simpleName, StringComparison.Ordinal) ||
               string.Equals(candidateDeclaringType, fullName, StringComparison.Ordinal) ||
               string.Equals(candidateDeclaringType, simpleName, StringComparison.Ordinal) ||
               (!string.IsNullOrWhiteSpace(candidateDeclaringType) &&
                candidateDeclaringType.EndsWith($".{simpleName}", StringComparison.Ordinal));

        var fieldBridgeFamily = MatchesFamily(type, declaringType, "MXField.FieldBridge", "FieldBridge");
        var playUnderCoverFamily = MatchesFamily(type, declaringType, "MXField.Actions.PlayUnderCoverStageAction", "PlayUnderCoverStageAction");
        var fieldGameManagerFamily = MatchesFamily(type, declaringType, "MXField.FieldGameManager", "FieldGameManager");

        if (!fieldBridgeFamily && !playUnderCoverFamily && !fieldGameManagerFamily)
            return members;

        var historiesListType = !string.IsNullOrWhiteSpace(_campaignStageHistoryDbTypeName)
            ? $"System.Collections.Generic.List<{_campaignStageHistoryDbTypeName}>"
            : null;
        var historiesEnumerableType = !string.IsNullOrWhiteSpace(_campaignStageHistoryDbTypeName)
            ? $"System.Collections.Generic.IEnumerable<{_campaignStageHistoryDbTypeName}>"
            : null;
        var fieldQuestDbListType = !string.IsNullOrWhiteSpace(_fieldQuestDbTypeName)
            ? $"System.Collections.Generic.List<{_fieldQuestDbTypeName}>"
            : null;
        var uiFieldLobbyActionType = !string.IsNullOrWhiteSpace(_uiFieldLobbyTypeName)
            ? $"System.Action<{_uiFieldLobbyTypeName}>"
            : null;
        var fieldInteractionResponseActionType = !string.IsNullOrWhiteSpace(_fieldInteractionResponseTypeName)
            ? $"System.Action<{_fieldInteractionResponseTypeName}>"
            : null;
        var fieldSaveSoActionType = !string.IsNullOrWhiteSpace(_fieldSaveSoTypeName)
            ? $"System.Action<{_fieldSaveSoTypeName}>"
            : null;
        const string NullableInt64Type = "System.Nullable<System.Int64>";

        static bool IsIntLike(string typeName)
            => string.Equals(typeName, "int", StringComparison.Ordinal) ||
               string.Equals(typeName, "long", StringComparison.Ordinal) ||
               string.Equals(typeName, "float", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Int32", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Int64", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Single", StringComparison.Ordinal);

        string PreferFieldBridgeType(string currentType, string? desiredType)
        {
            if (string.IsNullOrWhiteSpace(desiredType))
                return currentType;
            if (string.IsNullOrWhiteSpace(currentType) ||
                currentType.StartsWith("Type_0x", StringComparison.Ordinal) ||
                IsIntLike(currentType) ||
                string.Equals(currentType, "bool", StringComparison.Ordinal) ||
               string.Equals(currentType, "System.Boolean", StringComparison.Ordinal))
            {
                return desiredType!;
            }

            return currentType;
        }

        string? DesiredIdLikeType(string name)
        {
            return name switch
            {
                "SeasonId" or "PrevMasteryLevel" or "PrevMasteryExp" or "seasonId" or "stageId" or "id" or "eventContentId" or "lastClearedStageId" => "System.Int64",
                _ => null,
            };
        }

        string? DesiredFieldType(string identifier)
        {
            if (fieldBridgeFamily)
            {
                if (string.Equals(type.FullName, "MXField.FieldBridge", StringComparison.Ordinal))
                {
                    return identifier switch
                    {
                        "<Histories>k__BackingField" or "_Histories_k__BackingField" => historiesListType,
                        "<PrevMasteryLevel>k__BackingField" or "_PrevMasteryLevel_k__BackingField" => "System.Int64",
                        "<PrevMasteryExp>k__BackingField" or "_PrevMasteryExp_k__BackingField" => "System.Int64",
                        _ => DesiredIdLikeType(identifier),
                    };
                }

                return identifier switch
                {
                    "seasonInfo" => _fieldSeasonInfoTypeName,
                    "stageInfo" => _fieldContentStageInfoTypeName,
                    "onLoaded" => uiFieldLobbyActionType,
                    "prefabName" => "System.String",
                    "message" => "System.String",
                    "__9__2" or "__9__3" or "__9__4" => "System.Action",
                    _ => DesiredIdLikeType(identifier),
                };
            }

            if (playUnderCoverFamily)
            {
                return identifier switch
                {
                    "interactionInfo" => _fieldInteractionInfoTypeName,
                    "undercoverStageId" => "System.Int64",
                    "nextSceneId" => NullableInt64Type,
                    "eventSeasonId" => "System.Int64",
                    "request" => _fieldInteractionRequestTypeName,
                    "playingSaveSO" or "saveSO" => _fieldSaveSoTypeName,
                    "repo" or "saveRepository" => _fieldSaveRepositoryTypeName,
                    "__9__3" => fieldInteractionResponseActionType,
                    _ => null,
                };
            }

            if (fieldGameManagerFamily)
            {
                return identifier switch
                {
                    "saveSO" or "<SaveSO>k__BackingField" or "_SaveSO_k__BackingField" or "<saveSOBackup>5__2" or "_saveSOBackup_5__2" => _fieldSaveSoTypeName,
                    "<SeasonInfo>k__BackingField" or "_SeasonInfo_k__BackingField" or "seasonInfo" => _fieldSeasonInfoTypeName,
                    "<CurrentDate>k__BackingField" or "_CurrentDate_k__BackingField" => _fieldDateInfoTypeName,
                    "openDate" or "<AccountId>k__BackingField" or "_AccountId_k__BackingField" or "<Level>k__BackingField" or "_Level_k__BackingField" or "<Exp>k__BackingField" or "_Exp_k__BackingField" => "System.Int64",
                    _ => null,
                };
            }

            return null;
        }

        var adjustedFields = fields.Select(field =>
        {
            string? desiredType = DesiredFieldType(field.Identifier);

            desiredType ??= YldaResolutionUtilities.BackingFieldPropertyName(field.Identifier) is { } backingPropertyName
                ? DesiredIdLikeType(backingPropertyName)
                : null;

            var adjustedField = desiredType is null ? field : field with { TypeName = PreferFieldBridgeType(field.TypeName, desiredType) };

            if (fieldGameManagerFamily &&
                string.Equals(type.FullName, "MXField.FieldGameManager", StringComparison.Ordinal) &&
                string.Equals(field.Identifier, "Instance", StringComparison.Ordinal))
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "static"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            if (fieldGameManagerFamily &&
                string.Equals(type.Name, "<>c__DisplayClass82_0", StringComparison.Ordinal) &&
                field.Identifier is "seasonInfo" or "sceneInfo" or "openDate" or "__4__this")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            return adjustedField;
        }).ToArray();

        var adjustedProperties = properties.Select(property =>
        {
            string? desiredType = property.DisplayName switch
            {
                "Histories" when fieldBridgeFamily => historiesListType,
                "SeasonId" when fieldBridgeFamily => "System.Int64",
                "PrevMasteryLevel" or "PrevMasteryExp" when fieldBridgeFamily => "System.Int64",
                "SeasonInfo" when fieldGameManagerFamily => _fieldSeasonInfoTypeName,
                "SaveSO" when fieldGameManagerFamily => _fieldSaveSoTypeName,
                "CurrentDate" when fieldGameManagerFamily => _fieldDateInfoTypeName,
                "AccountId" or "Level" or "Exp" when fieldGameManagerFamily => "System.Int64",
                _ => DesiredIdLikeType(property.DisplayName),
            };

            return desiredType is null ? property : property with { TypeName = PreferFieldBridgeType(property.TypeName, desiredType) };
        }).ToArray();

        var adjustedMethods = methods.Select(method =>
        {
            string? desiredReturnType = method.DisplayName switch
            {
                "get_Histories" => historiesListType,
                "get_SeasonId" or "get_PrevMasteryLevel" or "get_PrevMasteryExp" => "System.Int64",
                "GetStageHistory" => _campaignStageHistoryDbTypeName,
                "GetCurrentEventContentId" => "System.Int64",
                "<TryContinue>b__0" when fieldBridgeFamily && string.Equals(type.Name, "<>c__DisplayClass49_0", StringComparison.Ordinal) => null,
                "<OpenPopupOnStageClear>b__0" when fieldBridgeFamily && string.Equals(type.Name, "<>c__DisplayClass63_0", StringComparison.Ordinal) => null,
                "get_SeasonInfo" when fieldGameManagerFamily => _fieldSeasonInfoTypeName,
                "get_SaveSO" when fieldGameManagerFamily => _fieldSaveSoTypeName,
                "get_CurrentDate" when fieldGameManagerFamily => _fieldDateInfoTypeName,
                "get_CurrentScene" when fieldGameManagerFamily => _fieldSceneInfoTypeName,
                "get_AccountId" or "get_Level" or "get_Exp" or "GetCurrentEventContentId" when fieldGameManagerFamily => "System.Int64",
                "<EnterSceneDirectly>g__GetDailyQuests|82_0" when fieldGameManagerFamily => fieldQuestDbListType,
                ".ctor" when playUnderCoverFamily && string.Equals(type.FullName, "MXField.Actions.PlayUnderCoverStageAction", StringComparison.Ordinal) => null,
                _ => null,
            };

            var adjustedParameters = method.Parameters.Select(parameter =>
            {
                string? desiredType = null;
                var modifierPrefix = parameter.ModifierPrefix;

                switch (method.DisplayName)
                {
                    case "set_Histories":
                        if (parameter.Identifier == "value")
                            desiredType = historiesListType;
                        break;
                    case "SyncRequired":
                    case "IsAlreadyClear":
                    case "GetContentName":
                    case "RequestSync":
                    case "GetStageHistory":
                        desiredType = DesiredIdLikeType(parameter.Identifier);
                        break;
                    case "TryGetStageInfo":
                        if (parameter.Identifier == "stageId")
                            desiredType = "System.Int64";
                        else if (parameter.Identifier == "fieldStage")
                        {
                            desiredType = _campaignStageInfoTypeName;
                            modifierPrefix = "out";
                        }
                        break;
                    case "CoContinueFieldContentStage":
                        if (parameter.Identifier == "stageInfo")
                            desiredType = _fieldContentStageInfoTypeName;
                        else if (parameter.Identifier == "eventContentId")
                            desiredType = "System.Int64";
                        break;
                    case "CoOpenFieldLobby":
                    case "OpenContentLobby":
                    case "Co_EventLobbyLoading":
                        if (parameter.Identifier == "eventContentId")
                            desiredType = "System.Int64";
                        break;
                    case "OpenFieldLobbyUI":
                    case "OpenFieldLobby":
                        if (parameter.Identifier == "onLoaded")
                            desiredType = uiFieldLobbyActionType;
                        break;
                    case "SetData":
                        if (parameter.Identifier == "histories")
                            desiredType = historiesEnumerableType;
                        break;
                    case "OpenPopupOnStageClear":
                        if (parameter.Identifier == "lastClearedStageId")
                            desiredType = "System.Int64";
                        break;
                    case "set_PrevMasteryLevel":
                    case "set_PrevMasteryExp":
                        if (parameter.Identifier == "value")
                            desiredType = "System.Int64";
                        break;
                }

                if (fieldBridgeFamily)
                {
                    if (string.Equals(type.Name, "<>c__DisplayClass49_0", StringComparison.Ordinal) &&
                        method.DisplayName == "<TryContinue>b__0" &&
                        parameter.Identifier == "e")
                    {
                        desiredType = _eventContentSeasonInfoTypeName;
                    }
                    else if (string.Equals(type.Name, "<>c__DisplayClass63_0", StringComparison.Ordinal) &&
                             method.DisplayName == "<OpenPopupOnStageClear>b__0" &&
                             parameter.Identifier == "e")
                    {
                        desiredType = _fieldDateInfoTypeName;
                    }
                    else if (string.Equals(type.FullName, "MXField.FieldBridge", StringComparison.Ordinal))
                    {
                        switch (method.DisplayName)
                        {
                            case "TryGetStageInfo":
                                if (parameter.Identifier == "stageId")
                                    desiredType = "System.Int64";
                                else if (parameter.Identifier == "fieldStage")
                                {
                                    desiredType = _campaignStageInfoTypeName;
                                    modifierPrefix = "out";
                                }
                                break;
                            case "CoContinueFieldContentStage":
                                if (parameter.Identifier == "stageInfo")
                                    desiredType = _fieldContentStageInfoTypeName;
                                else if (parameter.Identifier == "eventContentId")
                                    desiredType = "System.Int64";
                                break;
                            case "CoOpenFieldLobby":
                            case "OpenContentLobby":
                            case "Co_EventLobbyLoading":
                                if (parameter.Identifier == "eventContentId")
                                    desiredType = "System.Int64";
                                break;
                            case "OpenFieldLobbyUI":
                            case "OpenFieldLobby":
                                if (parameter.Identifier == "onLoaded")
                                    desiredType = uiFieldLobbyActionType;
                                break;
                            case "SetData":
                                if (parameter.Identifier == "histories")
                                    desiredType = historiesEnumerableType;
                                break;
                            case "OpenPopupOnStageClear":
                                if (parameter.Identifier == "lastClearedStageId")
                                    desiredType = "System.Int64";
                                break;
                        }
                    }
                }

                if (playUnderCoverFamily)
                {
                    switch (method.DisplayName)
                    {
                        case ".ctor":
                            if (parameter.Identifier == "info")
                                desiredType = _fieldInteractionInfoTypeName;
                            else if (parameter.Identifier == "ucStageId")
                                desiredType = "System.Int64";
                            break;
                        case "ReserveNextScene":
                            if (parameter.Identifier == "sceneId")
                                desiredType = "System.Int64";
                            break;
                        case "CoReturnToField":
                            if (parameter.Identifier == "playingSaveSO")
                                desiredType = _fieldSaveSoTypeName;
                            break;
                        case "EnterField":
                            if (parameter.Identifier == "saveRepository")
                                desiredType = _fieldSaveRepositoryTypeName;
                            else if (parameter.Identifier == "saveSO")
                                desiredType = _fieldSaveSoTypeName;
                            break;
                        case "<Execute>b__7_0":
                            if (parameter.Identifier == "saveSo")
                                desiredType = _fieldSaveSoTypeName;
                            break;
                        case "<Execute>b__3":
                            if (parameter.Identifier == "response")
                                desiredType = _fieldInteractionResponseTypeName;
                            break;
                        case "<Execute>b__7_1":
                        case "<CoReturnToField>b__8_0":
                            if (parameter.Identifier == "x")
                                desiredType = _mxContentBridgeTypeName;
                            break;
                    }
                }

                if (fieldGameManagerFamily)
                {
                    switch (method.DisplayName)
                    {
                        case "set_SeasonInfo":
                            if (parameter.Identifier == "value")
                                desiredType = _fieldSeasonInfoTypeName;
                            break;
                        case "set_CurrentDate":
                            if (parameter.Identifier == "value")
                                desiredType = _fieldDateInfoTypeName;
                            break;
                        case "EnterField":
                            if (parameter.Identifier == "saveRepository")
                                desiredType = _fieldSaveRepositoryTypeName;
                            else if (parameter.Identifier == "save")
                                desiredType = _fieldSaveSoTypeName;
                            break;
                        case "EncounterQuit":
                        case "CoQuit_Encounter":
                            if (parameter.Identifier == "onComplete")
                                desiredType = fieldSaveSoActionType;
                            break;
                        case "EnterNewGame":
                            if (parameter.Identifier == "seasonId")
                                desiredType = "System.Int64";
                            break;
                        case "EnterSceneDirectly":
                            if (parameter.Identifier == "sceneInfo")
                                desiredType = _fieldSceneInfoTypeName;
                            else if (parameter.Identifier == "openDate")
                                desiredType = "System.Int64";
                            else if (parameter.Identifier == "selectedSeasonId")
                                desiredType = NullableInt64Type;
                            break;
                        case "<EnterSceneDirectly>g__GetDailyQuests|82_0":
                            if (parameter.Identifier == "param_0" || parameter.Identifier == "_")
                                desiredType = _fieldGameManagerDisplayClass82TypeName;
                            break;
                        case "ProcessDateChanged":
                            if (parameter.Identifier == "dateInfo")
                                desiredType = _fieldDateInfoTypeName;
                            break;
                        case "IsSatisfied":
                            if (parameter.Identifier == "id")
                                desiredType = "System.Int64";
                            break;
                    }
                }

                if (desiredType is null)
                    return parameter with { ModifierPrefix = modifierPrefix };

                return parameter with
                {
                    TypeName = PreferFieldBridgeType(parameter.TypeName, desiredType),
                    ModifierPrefix = modifierPrefix,
                };
            }).ToArray();

            if (fieldGameManagerFamily &&
                string.Equals(type.FullName, "MXField.FieldGameManager", StringComparison.Ordinal) &&
                string.Equals(method.DisplayName, "EnterSceneDirectly", StringComparison.Ordinal) &&
                adjustedParameters.Length == 2 &&
                !adjustedParameters.Any(parameter => string.Equals(parameter.Identifier, "selectedSeasonId", StringComparison.Ordinal)))
            {
                adjustedParameters =
                [
                    .. adjustedParameters,
                    new ResolvedParameterModel(
                        new ParameterDefinition(-1, "selectedSeasonId", 0, 0),
                        "selectedSeasonId",
                        NullableInt64Type)
                ];
            }

            if (fieldGameManagerFamily &&
                string.Equals(method.DisplayName, "<EnterSceneDirectly>g__GetDailyQuests|82_0", StringComparison.Ordinal) &&
                adjustedParameters.Length == 1 &&
                !string.IsNullOrWhiteSpace(_fieldGameManagerDisplayClass82TypeName))
            {
                adjustedParameters =
                [
                    adjustedParameters[0] with
                    {
                        Identifier = "_",
                        TypeName = _fieldGameManagerDisplayClass82TypeName,
                    }
                ];
            }

            return method with
            {
                ReturnTypeName = desiredReturnType is null ? method.ReturnTypeName : PreferFieldBridgeType(method.ReturnTypeName, desiredReturnType),
                Parameters = adjustedParameters,
            };
        }).ToArray();

        return new YldaResolvedMemberSet(relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }



}
