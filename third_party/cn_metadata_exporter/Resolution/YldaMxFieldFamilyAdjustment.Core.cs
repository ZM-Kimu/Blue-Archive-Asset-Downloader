using static YldaDumpCsExporter.YldaTypeNameHelpers;

namespace YldaDumpCsExporter;

internal sealed partial class YldaMxFieldFamilyAdjustment
{
    private readonly string? _campaignStageHistoryDbTypeName;
    private readonly string? _fieldCharacterDbTypeName;
    private readonly string? _fieldDateHistoryDbTypeName;
    private readonly string? _fieldInteractionDbTypeName;
    private readonly string? _fieldMasteryDbTypeName;
    private readonly string? _fieldQuestDbTypeName;
    private readonly string? _fieldQuestInfoTypeName;
    private readonly string? _fieldRewardInfoTypeName;
    private readonly string? _fieldSceneInfoTypeName;
    private readonly string? _fieldSeasonInfoTypeName;
    private readonly string? _fieldSnapshotTypeName;
    private readonly string? _gameCharacterDbTypeName;
    private readonly string? _intStringPairTypeName;
    private readonly string? _iPreloadRequiredTypeName;
    private readonly string? _parcelInfoTypeName;
    private readonly string? _parcelResultDbTypeName;
    private readonly TypeDefinition type;
    private readonly YldaResolvedMemberSet members;
    private readonly TypeRelationships relationships;
    private readonly IReadOnlyList<ResolvedFieldModel> fields;
    private readonly IReadOnlyList<ResolvedPropertyModel> properties;
    private readonly IReadOnlyList<ResolvedEventModel> events;
    private readonly IReadOnlyList<ResolvedMethodModel> methods;
    private readonly string? campaignStageHistoryListType;
    private readonly string? fieldDateHistoryListType;
    private readonly string? fieldInteractionListType;
    private readonly string? fieldQuestListType;
    private readonly string? fieldQuestInfoListType;
    private readonly string? fieldQuestInfoEnumerableType;
    private readonly string? characterDbListType;
    private readonly string? parcelInfoListType;
    private readonly string? fieldDateHistoryIListType;
    private readonly string? fieldInteractionIListType;
    private readonly string? fieldQuestIListType;
    private readonly string? rewardInfoListType;
    private readonly string? rewardInfoEnumerableType;
    private readonly string? rewardInfoDictionaryType;
    private readonly string? questInfoDictionaryType;
    private readonly string? originalQuestInfoDictionaryType;
    private readonly string? int64EnumerableType;
    private readonly string? preloadRequiredListType;
    private readonly string? intStringPairArrayType;
    private readonly string? DateTimeType;

    public YldaMxFieldFamilyAdjustment(YldaKnownTypeCatalog knownTypes, TypeDefinition type, YldaResolvedMemberSet members)
    {
        _campaignStageHistoryDbTypeName = knownTypes.CampaignStageHistoryDbTypeName;
        _fieldCharacterDbTypeName = knownTypes.FieldCharacterDbTypeName;
        _fieldDateHistoryDbTypeName = knownTypes.FieldDateHistoryDbTypeName;
        _fieldInteractionDbTypeName = knownTypes.FieldInteractionDbTypeName;
        _fieldMasteryDbTypeName = knownTypes.FieldMasteryDbTypeName;
        _fieldQuestDbTypeName = knownTypes.FieldQuestDbTypeName;
        _fieldQuestInfoTypeName = knownTypes.FieldQuestInfoTypeName;
        _fieldRewardInfoTypeName = knownTypes.FieldRewardInfoTypeName;
        _fieldSceneInfoTypeName = knownTypes.FieldSceneInfoTypeName;
        _fieldSeasonInfoTypeName = knownTypes.FieldSeasonInfoTypeName;
        _fieldSnapshotTypeName = knownTypes.FieldSnapshotTypeName;
        _gameCharacterDbTypeName = knownTypes.GameCharacterDbTypeName;
        _intStringPairTypeName = knownTypes.IntStringPairTypeName;
        _iPreloadRequiredTypeName = knownTypes.IPreloadRequiredTypeName;
        _parcelInfoTypeName = knownTypes.ParcelInfoTypeName;
        _parcelResultDbTypeName = knownTypes.ParcelResultDbTypeName;
        this.type = type;
        this.members = members;
        relationships = members.Relationships;
        fields = members.Fields;
        properties = members.Properties;
        events = members.Events;
        methods = members.Methods;
        campaignStageHistoryListType = BuildListType(_campaignStageHistoryDbTypeName);
        fieldDateHistoryListType = BuildListType(_fieldDateHistoryDbTypeName);
        fieldInteractionListType = BuildListType(_fieldInteractionDbTypeName);
        fieldQuestListType = BuildListType(_fieldQuestDbTypeName);
        fieldQuestInfoListType = BuildListType(_fieldQuestInfoTypeName);
        fieldQuestInfoEnumerableType = BuildEnumerableType(_fieldQuestInfoTypeName);
        characterDbListType = BuildListType(_gameCharacterDbTypeName);
        parcelInfoListType = BuildListType(_parcelInfoTypeName);
        fieldDateHistoryIListType = BuildIListType(_fieldDateHistoryDbTypeName);
        fieldInteractionIListType = BuildIListType(_fieldInteractionDbTypeName);
        fieldQuestIListType = BuildIListType(_fieldQuestDbTypeName);
        rewardInfoListType = BuildListType(_fieldRewardInfoTypeName);
        rewardInfoEnumerableType = BuildEnumerableType(_fieldRewardInfoTypeName);
        rewardInfoDictionaryType = BuildDictionaryType("System.Int64", _fieldRewardInfoTypeName);
        questInfoDictionaryType = BuildDictionaryType("System.Int64", fieldQuestInfoListType);
        originalQuestInfoDictionaryType = BuildDictionaryType("System.Int64", _fieldQuestInfoTypeName);
        int64EnumerableType = "System.Collections.Generic.IEnumerable<System.Int64>";
        preloadRequiredListType = BuildListType(_iPreloadRequiredTypeName);
        intStringPairArrayType = BuildArrayType(_intStringPairTypeName);
        DateTimeType = "System.DateTime";
    }

    public YldaResolvedMemberSet Apply()
    {
        var adjustedFields = AdjustFields();
        var adjustedProperties = AdjustProperties();
        var adjustedMethods = AdjustMethods();

        return new YldaResolvedMemberSet(relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }

        static bool IsWeakFieldFamilyType(string typeName)
            => string.IsNullOrWhiteSpace(typeName) ||
               typeName.StartsWith("Type_0x", StringComparison.Ordinal) ||
               string.Equals(typeName, "int", StringComparison.Ordinal) ||
               string.Equals(typeName, "long", StringComparison.Ordinal) ||
               string.Equals(typeName, "float", StringComparison.Ordinal) ||
               string.Equals(typeName, "bool", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Collections.IEnumerable", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Collections.IList", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Int32", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Int64", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Single", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Boolean", StringComparison.Ordinal);

        static string PreferFieldFamilyType(string currentType, string? desiredType)
            => string.IsNullOrWhiteSpace(desiredType) || !IsWeakFieldFamilyType(currentType) ? currentType : desiredType!;
}
