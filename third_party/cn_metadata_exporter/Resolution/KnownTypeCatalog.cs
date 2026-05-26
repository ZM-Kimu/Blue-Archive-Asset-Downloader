namespace CnMetadataExporter;

internal sealed class KnownTypeCatalog
{
    private readonly MetadataModel _model;
    private readonly TypeResolver _typeResolver;
    private readonly RelationshipResolver _relationshipResolver;

    public KnownTypeCatalog(
        MetadataModel model,
        TypeResolver typeResolver,
        RelationshipResolver relationshipResolver)
    {
        _model = model;
        _typeResolver = typeResolver;
        _relationshipResolver = relationshipResolver;
        TypeFullNames = model.Types.Select(item => item.FullName).ToHashSet(StringComparer.Ordinal);
        FutureInterfaceTypeName = TryFindTypeFullName("IFuture`1");
        FutureValueCallbackTypeName = TryFindTypeFullName("FutureValueCallback`1");
        FutureCallbackTypeName = TryFindTypeFullName("FutureCallback`1");
        FutureErrorCallbackTypeName = TryFindTypeFullName("FutureErrorCallback");
        HubConnectionTypeName = TryFindTypeFullName("HubConnection");
        CampaignStageHistoryDbTypeName = TryFindTypeFullName("CampaignStageHistoryDB");
        CampaignStageInfoTypeName = TryFindTypeFullName("CampaignStageInfo");
        FieldContentStageInfoTypeName = TryFindTypeFullName("FieldContentStageInfo");
        UiFieldLobbyTypeName = TryFindTypeFullName("UIFieldLobby");
        FieldDateHistoryDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldDateHistoryDB");
        FieldInteractionDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldInteractionDB");
        FieldQuestDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldQuestDB");
        FieldSnapshotTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldSnapshot");
        FieldCharacterDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldCharacterDB");
        FieldMasteryDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldMasteryDB");
        FieldSeasonInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldSeasonInfo");
        FieldSceneInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldSceneInfo");
        FieldQuestInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldQuestInfo");
        GameCharacterDbTypeName = TryFindExactTypeFullName("MX.GameLogic.DBModel.CharacterDB");
        IPreloadRequiredTypeName = TryFindExactTypeFullName("MXField.Core.IPreloadRequired");
        IntStringPairTypeName = TryFindExactTypeFullName("MXField.LUT.IntStringPair");
        ParcelInfoTypeName = TryFindExactTypeFullName("MX.GameLogic.Parcel.ParcelInfo");
        ParcelResultDbTypeName = TryFindExactTypeFullName("MX.GameLogic.Parcel.ParcelResultDB");
        FieldRewardInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldRewardInfo");
        FieldInteractionInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldInteractionInfo");
        FieldSaveSoTypeName = TryFindExactTypeFullName("MXField.Core.Save.FieldSaveSO");
        FieldSaveRepositoryTypeName = TryFindExactTypeFullName("MXField.Core.Save.FieldSaveRepository");
        FieldInteractionRequestTypeName = TryFindExactTypeFullName("MXField.Shared.NetworkProtocol.FieldInteractionRequest");
        FieldInteractionResponseTypeName = TryFindExactTypeFullName("MXField.Shared.NetworkProtocol.FieldInteractionResponse");
        FieldDateInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldDateInfo");
        EventContentSeasonInfoTypeName = TryFindExactTypeFullName("MX.Data.EventContentSeasonInfo");
        MxContentBridgeTypeName = TryFindTypeFullName("MXContentBridge");
        FieldGameManagerDisplayClass82TypeName = TryFindNestedTypeReference("MXField.FieldGameManager", "<>c__DisplayClass82_0");
        EquatableTypeName = TryFindExactTypeFullName("System.IEquatable`1");
        MemoryPackableTypeName = TryFindExactTypeFullName("MemoryPack.IMemoryPackable`1");
        MemoryPackFormatterTypeName = TryFindExactTypeFullName("MemoryPack.MemoryPackFormatter`1");
        MemoryPackWriterTypeName = TryFindExactTypeFullName("MemoryPack.MemoryPackWriter");
        MemoryPackReaderTypeName = TryFindExactTypeFullName("MemoryPack.MemoryPackReader");
        TableBundleTypeName = TryFindExactTypeFullName("TableBundle");
        TablePatchPackTypeName = TryFindExactTypeFullName("TablePatchPack");
        TableCatalogTypeName = TryFindExactTypeFullName("TableCatalog");
        FlatDataTagTypeName = TryFindExactTypeFullName("FlatData.Tag");
        PatchFileInfoTypeName = TryFindExactTypeFullName("MX.AssetBundles.PatchFileInfo");
        MediaTypeName = TryFindExactTypeFullName("Media.Service.Media");
        MediaCatalogTypeName = TryFindExactTypeFullName("Media.Service.MediaCatalog");
        SkillAbilityModifierDaoTypeName = TryFindExactTypeFullName("MX.GameData.DAO.Battle.SkillAbilityModifierDAO");
        UnityVector2TypeName = TryFindExactTypeFullName("UnityEngine.Vector2");
        UnityVector3TypeName = TryFindExactTypeFullName("UnityEngine.Vector3");
        GroundObstacleDataTypeName = TryFindExactTypeFullName("MX.Data.GroundObstacleData");
    }

    public IReadOnlySet<string> TypeFullNames { get; }
    public string? FutureInterfaceTypeName { get; }
    public string? FutureValueCallbackTypeName { get; }
    public string? FutureCallbackTypeName { get; }
    public string? FutureErrorCallbackTypeName { get; }
    public string? HubConnectionTypeName { get; }
    public string? CampaignStageHistoryDbTypeName { get; }
    public string? CampaignStageInfoTypeName { get; }
    public string? FieldContentStageInfoTypeName { get; }
    public string? UiFieldLobbyTypeName { get; }
    public string? FieldDateHistoryDbTypeName { get; }
    public string? FieldInteractionDbTypeName { get; }
    public string? FieldQuestDbTypeName { get; }
    public string? FieldSnapshotTypeName { get; }
    public string? FieldCharacterDbTypeName { get; }
    public string? FieldMasteryDbTypeName { get; }
    public string? FieldSeasonInfoTypeName { get; }
    public string? FieldSceneInfoTypeName { get; }
    public string? FieldQuestInfoTypeName { get; }
    public string? GameCharacterDbTypeName { get; }
    public string? IPreloadRequiredTypeName { get; }
    public string? IntStringPairTypeName { get; }
    public string? ParcelInfoTypeName { get; }
    public string? ParcelResultDbTypeName { get; }
    public string? FieldRewardInfoTypeName { get; }
    public string? FieldInteractionInfoTypeName { get; }
    public string? FieldSaveSoTypeName { get; }
    public string? FieldSaveRepositoryTypeName { get; }
    public string? FieldInteractionRequestTypeName { get; }
    public string? FieldInteractionResponseTypeName { get; }
    public string? FieldDateInfoTypeName { get; }
    public string? EventContentSeasonInfoTypeName { get; }
    public string? MxContentBridgeTypeName { get; }
    public string? FieldGameManagerDisplayClass82TypeName { get; }
    public string? EquatableTypeName { get; }
    public string? MemoryPackableTypeName { get; }
    public string? MemoryPackFormatterTypeName { get; }
    public string? MemoryPackWriterTypeName { get; }
    public string? MemoryPackReaderTypeName { get; }
    public string? TableBundleTypeName { get; }
    public string? TablePatchPackTypeName { get; }
    public string? TableCatalogTypeName { get; }
    public string? FlatDataTagTypeName { get; }
    public string? PatchFileInfoTypeName { get; }
    public string? MediaTypeName { get; }
    public string? MediaCatalogTypeName { get; }
    public string? SkillAbilityModifierDaoTypeName { get; }
    public string? UnityVector2TypeName { get; }
    public string? UnityVector3TypeName { get; }
    public string? GroundObstacleDataTypeName { get; }

    private string? TryFindTypeFullName(string rawTypeName)
    {
        foreach (var type in _model.Types)
        {
            if (string.Equals(type.Name, rawTypeName, StringComparison.Ordinal))
                return type.FullName;
        }

        return null;
    }

    private string? TryFindExactTypeFullName(string fullTypeName)
    {
        foreach (var type in _model.Types)
        {
            if (string.Equals(type.FullName, fullTypeName, StringComparison.Ordinal))
                return type.FullName;
        }

        return null;
    }

    private string? TryFindNestedTypeReference(string declaringTypeName, string rawTypeName)
    {
        foreach (var type in _model.Types)
        {
            if (!string.Equals(type.Name, rawTypeName, StringComparison.Ordinal))
                continue;

            var resolvedDeclaringType = _relationshipResolver.ResolveDeclaringType(type, _typeResolver.GlobalTypeNames);
            if (string.Equals(resolvedDeclaringType, declaringTypeName, StringComparison.Ordinal))
                return $"{declaringTypeName}.{rawTypeName}";
        }

        return null;
    }
}
