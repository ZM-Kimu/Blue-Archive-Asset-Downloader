using static CnMetadataExporter.TypeNameHelpers;

namespace CnMetadataExporter;

internal sealed partial class ReferenceModelAdjustment
{
    private readonly string? _equatableTypeName;
    private readonly string? _futureInterfaceTypeName;
    private readonly string? _groundObstacleDataTypeName;
    private readonly string? _hubConnectionTypeName;
    private readonly string? _memoryPackFormatterTypeName;
    private readonly string? _memoryPackReaderTypeName;
    private readonly string? _memoryPackWriterTypeName;
    private readonly string? _parcelInfoTypeName;
    private readonly string? _skillAbilityModifierDaoTypeName;
    private readonly string? _unityVector2TypeName;
    private readonly string? _unityVector3TypeName;
    private readonly TypeDefinition type;
    private readonly string safeTypeName;
    private readonly string? declaringType;
    private readonly ResolvedMemberSet members;
    private TypeRelationships relationships;
    private readonly IReadOnlyList<ResolvedFieldModel> fields;
    private readonly IReadOnlyList<ResolvedPropertyModel> properties;
    private readonly IReadOnlyList<ResolvedEventModel> events;
    private readonly IReadOnlyList<ResolvedMethodModel> methods;
    private readonly bool isAutoUseRuleDao;
    private readonly bool isGroundObstacleData;
    private readonly bool isGroundObstacleDataCollection;
    private readonly bool isGroundObstacleDataHashComparer;
    private readonly bool isPositionSetting;
    private readonly bool isAreaCollisionProperty;
    private readonly bool isAccountBillingInfo;
    private readonly bool isByteReader;
    private readonly bool isBmFont;
    private readonly bool isBmGlyph;
    private readonly bool isBmSymbol;
    private readonly bool isRuntimeInspectorUtils;
    private readonly bool isHubConnectionExtensions;
    private readonly bool isUploadItemControllerExtensions;
    private readonly bool isBitPackFormatter;
    private readonly bool isSystemRuntimeUnsafe;
    private readonly bool isCommunityToolkitArrayExtensions;
    private readonly bool isTimelineExtensions;
    private readonly bool isWebRequestUtils;
    private readonly bool isJsonUtility;
    private readonly bool isFlatBuffersByteBuffer;
    private readonly bool isSocketIoTransportInterface;
    private readonly bool isSocketIoJsonEncoder;
    private readonly bool isSocketIoDefaultJsonEncoder;
    private readonly bool isSignalRCoreEncoder;
    private readonly bool isSignalRCoreProtocol;
    private readonly bool isSignalRCoreUploadItemController;
    private readonly bool isSignalRCoreStreamItemContainer;
    private readonly bool isSignalRCoreCallbackDescriptor;
    private readonly bool isSocketIO3EventsCallbackDescriptor;
    private readonly bool isSocketIO3EventsSubscription;
    private readonly bool isSocketIO3EventsTypedEventTable;
    private readonly bool isBestHttpCorePluginEventInfo;
    private readonly bool isBestHttpCorePluginEventHelper;
    private readonly bool isBestHttpCoreConnectionEventInfo;
    private readonly bool isBestHttpCoreConnectionEventHelper;
    private readonly bool isBestHttpCoreHostProtocolSupport;
    private readonly bool isBestHttpCoreHostConnection;
    private readonly bool isBestHttpCoreHostDefinition;
    private readonly bool isBestHttpCoreHostConnectionKey;
    private readonly bool isBestHttpCoreAltSvcEventInfo;
    private readonly bool isBestHttpCoreHttp2ConnectProtocolInfo;
    private readonly bool isBestHttpCoreProtocolEventInfo;
    private readonly bool isBestHttpCoreProtocolEventHelper;
    private readonly bool isBestHttpCoreRequestEventInfo;
    private readonly bool isBestHttpCoreRequestEventHelper;
    private readonly bool isSignalRCoreInvocationDefinition;
    private readonly bool isSignalRCoreTransportInterface;
    private readonly bool isFutureCallback;
    private readonly bool isFutureValueCallback;
    private readonly bool isAddTypeMenuAttribute;
    private readonly bool isGenericGraphNodeMetadata;
    private readonly bool isSkeletonAnimationPlayableHandle;
    private readonly bool isWwwForm;
    private readonly (string BaseName, IReadOnlyList<string> Args)? parsedSafeGeneric;
    private readonly bool isSystemActionDelegate;
    private readonly bool isSystemFuncDelegate;
    private readonly bool isNguiText;
    private readonly bool isUiDrawCall;
    private readonly bool isBetterList;
    private readonly bool isCachedGeometries;
    private readonly bool isEventDelegate;
    private readonly bool isEventDelegateParameter;
    private readonly bool isPropertyReference;
    private readonly bool isFurnitureInventoryObject;
    private readonly bool isFurnitureObject;
    private readonly bool isFurnitureFilter;
    private readonly bool isConstraintStruct;
    private readonly bool isGroundObstacleRepository;
    private readonly string? equatableInterface;
    private readonly string? vector2ListType;
    private readonly string? skillAbilityModifierListType;
    private readonly string? tacticRangeArrayType;
    private readonly string? tacticRoleArrayType;
    private readonly string? keyedCollectionGroundObstacleType;
    private readonly string? equalityComparerGroundObstacleType;
    private readonly string? comparerGroundObstacleType;
    private readonly string? furnitureObjectListType;
    private readonly string? furnitureObjectEnumerableType;
    private readonly string? furnitureDbListType;
    private readonly string? furnitureDbDictionaryType;
    private readonly string? furnitureCategoryListType;
    private readonly string? furnitureSubCategoryListType;
    private readonly string? secureLongListType;
    private readonly string? furnitureTagsDictionaryType;
    private readonly string? purchaseCountDbListType;
    private readonly string? blockedProductDbListType;
    private readonly string? bmGlyphListType;
    private readonly string? bmGlyphDictionaryType;
    private readonly string? intListType;
    private readonly string? memberInfoArrayType;
    private readonly string? exposedMethodArrayType;
    private readonly string? byteArrayType;
    private readonly string? byteArrayListType;
    private readonly string? typeHashSetType;
    private readonly string? transformHashSetType;
    private readonly string? typeListType;
    private readonly string? stringListType;
    private readonly string? exposedMethodListType;
    private readonly string? exposedExtensionMethodHolderListType;
    private readonly string? customEditorAttributeListType;
    private readonly string? draggedReferenceItemStackType;
    private readonly string? typeToVariablesDictionaryType;
    private readonly string? typeToExposedMethodsDictionaryType;
    private readonly string? typeToTypeDictionaryType;
    private readonly string? unityObjectArrayType;
    private readonly string? betterListColorType;
    private readonly string? betterListSingleType;
    private readonly string? uiDrawCallListType;
    private readonly string? vector3ListType;
    private readonly string? vector4ListType;
    private readonly string? intArrayType;
    private readonly string? singleArrayType;
    private readonly string? glyphInfoType;
    private readonly string? fontType;
    private readonly string? fontStyleType;
    private readonly string? alignmentType;
    private readonly string? symbolStyleType;
    private readonly string? colorType;
    private readonly string? stringBuilderType;
    private readonly string? texture2DType;
    private readonly string? materialType;
    private readonly string? textureType;
    private readonly string? transformType;
    private readonly string? meshType;
    private readonly string? meshFilterType;
    private readonly string? meshRendererType;
    private readonly string? materialPropertyBlockType;
    private readonly string? uiSkinType;
    private readonly string? draggedReferenceItemType;
    private readonly string? numberFormatInfoType;
    private readonly string? monthlyProductRewardsType;
    private readonly string? betterListStringType;
    private readonly string? stringDictionaryType;
    private readonly string? eventDelegateParameterArrayType;
    private readonly string? eventDelegateListType;
    private readonly string? parameterInfoArrayType;
    private readonly string? objectArrayType;
    private readonly string? boolArrayType;
    private readonly string? stringArrayType;
    private readonly string? typeArrayType;
    private readonly string? colorListType;
    private readonly string? listObjectType;
    private readonly string? socketIoPacketListType;
    private readonly string? signalRMessageListType;
    private readonly string? actionObjectArrayType;
    private readonly string? actionSignalRMessageType;
    private readonly string? actionTransportStatesPairType;
    private readonly string? bufferSegmentType;
    private readonly string? stackVector2ListArrayType;
    private readonly string? stackVector3ListArrayType;
    private readonly string? stackColorListArrayType;
    private readonly string? linkedVector2ListType;
    private readonly string? linkedVector3ListType;
    private readonly string? linkedColorListType;
    private readonly string? genericStackListArrayType;
    private readonly string? genericLinkedListType;
    private readonly string? genericListType;
    private readonly string? repurchasableProductListType;
    private readonly string? furnitureTimelineStateListType;
    private readonly string? furnitureExcelType;
    private readonly string? inventoryObjectBaseFurnitureType;
    private readonly string? assetObjectBaseType;
    private readonly string? genericItemType;
    private readonly string? genericItemArrayType;
    private readonly string? genericEnumeratorType;
    private readonly string? compareFuncType;
    private readonly bool forceReferenceTypes;

    public ReferenceModelAdjustment(
        KnownTypeCatalog knownTypes,
        TypeDefinition type,
        string safeTypeName,
        string? declaringType,
        ResolvedMemberSet members)
    {
        _equatableTypeName = knownTypes.EquatableTypeName;
        _futureInterfaceTypeName = knownTypes.FutureInterfaceTypeName;
        _groundObstacleDataTypeName = knownTypes.GroundObstacleDataTypeName;
        _hubConnectionTypeName = knownTypes.HubConnectionTypeName;
        _memoryPackFormatterTypeName = knownTypes.MemoryPackFormatterTypeName;
        _memoryPackReaderTypeName = knownTypes.MemoryPackReaderTypeName;
        _memoryPackWriterTypeName = knownTypes.MemoryPackWriterTypeName;
        _parcelInfoTypeName = knownTypes.ParcelInfoTypeName;
        _skillAbilityModifierDaoTypeName = knownTypes.SkillAbilityModifierDaoTypeName;
        _unityVector2TypeName = knownTypes.UnityVector2TypeName;
        _unityVector3TypeName = knownTypes.UnityVector3TypeName;
        this.type = type;
        this.safeTypeName = safeTypeName;
        this.declaringType = declaringType;
        this.members = members;
        relationships = members.Relationships;
        fields = members.Fields;
        properties = members.Properties;
        events = members.Events;
        methods = members.Methods;
        isAutoUseRuleDao = string.Equals(type.FullName, "AutoUseRuleDAO", StringComparison.Ordinal);
        isGroundObstacleData = string.Equals(type.FullName, "MX.Data.GroundObstacleData", StringComparison.Ordinal);
        isGroundObstacleDataCollection = string.Equals(type.FullName, "MX.Data.GroundObstacleDataCollection", StringComparison.Ordinal);
        isGroundObstacleDataHashComparer = string.Equals(type.FullName, "MX.Data.GroundObstacleDataHashComparer", StringComparison.Ordinal);
        isPositionSetting = string.Equals(type.FullName, "MX.Visual.Data.PositionSetting", StringComparison.Ordinal);
        isAreaCollisionProperty = string.Equals(type.FullName, "MX.Logic.Data.AreaCollisionProperty", StringComparison.Ordinal);
        isAccountBillingInfo = string.Equals(type.FullName, "AccountBillingInfo", StringComparison.Ordinal);
        isByteReader =
            string.Equals(type.FullName, "ByteReader", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ByteReader", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isBmFont =
            string.Equals(type.FullName, "BMFont", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "BMFont", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isBmGlyph =
            string.Equals(type.FullName, "BMGlyph", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "BMGlyph", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isBmSymbol =
            string.Equals(type.FullName, "BMSymbol", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "BMSymbol", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isRuntimeInspectorUtils =
            string.Equals(type.FullName, "RuntimeInspectorNamespace.RuntimeInspectorUtils", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "RuntimeInspectorUtils", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isHubConnectionExtensions =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.HubConnectionExtensions", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "HubConnectionExtensions", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isUploadItemControllerExtensions =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.UploadItemControllerExtensions", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "UploadItemControllerExtensions", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isBitPackFormatter =
            string.Equals(type.FullName, "MemoryPack.Compression.BitPackFormatter", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "BitPackFormatter", StringComparison.Ordinal) && string.Equals(type.Namespace, "MemoryPack.Compression", StringComparison.Ordinal));
        isSystemRuntimeUnsafe =
            string.Equals(type.FullName, "System.Runtime.CompilerServices.Unsafe", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "Unsafe", StringComparison.Ordinal) && string.Equals(type.Namespace, "System.Runtime.CompilerServices", StringComparison.Ordinal));
        isCommunityToolkitArrayExtensions =
            string.Equals(type.FullName, "CommunityToolkit.HighPerformance.ArrayExtensions", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ArrayExtensions", StringComparison.Ordinal) && string.Equals(type.Namespace, "CommunityToolkit.HighPerformance", StringComparison.Ordinal));
        isTimelineExtensions =
            string.Equals(type.FullName, "Spine.Unity.AnimationTools.TimelineExtensions", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "TimelineExtensions", StringComparison.Ordinal) && string.Equals(type.Namespace, "Spine.Unity.AnimationTools", StringComparison.Ordinal));
        isWebRequestUtils =
            string.Equals(type.FullName, "UnityEngineInternal.WebRequestUtils", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "WebRequestUtils", StringComparison.Ordinal) && string.Equals(type.Namespace, "UnityEngineInternal", StringComparison.Ordinal));
        isJsonUtility =
            string.Equals(type.FullName, "UnityEngine.JsonUtility", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "JsonUtility", StringComparison.Ordinal) && string.Equals(type.Namespace, "UnityEngine", StringComparison.Ordinal));
        isFlatBuffersByteBuffer =
            string.Equals(type.FullName, "FlatBuffers.ByteBuffer", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ByteBuffer", StringComparison.Ordinal) && string.Equals(type.Namespace, "FlatBuffers", StringComparison.Ordinal));
        isSocketIoTransportInterface =
            string.Equals(type.FullName, "BestHTTP.SocketIO.Transports.ITransport", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ITransport", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SocketIO.Transports", StringComparison.Ordinal));
        isSocketIoJsonEncoder =
            string.Equals(type.FullName, "BestHTTP.SocketIO.JsonEncoders.IJsonEncoder", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "IJsonEncoder", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SocketIO.JsonEncoders", StringComparison.Ordinal));
        isSocketIoDefaultJsonEncoder =
            string.Equals(type.FullName, "BestHTTP.SocketIO.JsonEncoders.DefaultJSonEncoder", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "DefaultJSonEncoder", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SocketIO.JsonEncoders", StringComparison.Ordinal));
        isSignalRCoreEncoder =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.IEncoder", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "IEncoder", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isSignalRCoreProtocol =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.IProtocol", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "IProtocol", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isSignalRCoreUploadItemController =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.IUPloadItemController`1", StringComparison.Ordinal) ||
            (string.Equals(type.Name, "IUPloadItemController`1", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isSignalRCoreStreamItemContainer =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.StreamItemContainer`1", StringComparison.Ordinal) ||
            (string.Equals(type.Name, "StreamItemContainer`1", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isSignalRCoreCallbackDescriptor =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.CallbackDescriptor", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "CallbackDescriptor", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isSocketIO3EventsCallbackDescriptor =
            string.Equals(type.FullName, "BestHTTP.SocketIO3.Events.CallbackDescriptor", StringComparison.Ordinal);
        isSocketIO3EventsSubscription =
            string.Equals(type.FullName, "BestHTTP.SocketIO3.Events.Subscription", StringComparison.Ordinal);
        isSocketIO3EventsTypedEventTable =
            string.Equals(type.FullName, "BestHTTP.SocketIO3.Events.TypedEventTable", StringComparison.Ordinal);
        isBestHttpCorePluginEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.PluginEventInfo", StringComparison.Ordinal);
        isBestHttpCorePluginEventHelper =
            string.Equals(type.FullName, "BestHTTP.Core.PluginEventHelper", StringComparison.Ordinal);
        isBestHttpCoreConnectionEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.ConnectionEventInfo", StringComparison.Ordinal);
        isBestHttpCoreConnectionEventHelper =
            string.Equals(type.FullName, "BestHTTP.Core.ConnectionEventHelper", StringComparison.Ordinal);
        isBestHttpCoreHostProtocolSupport =
            string.Equals(type.FullName, "BestHTTP.Core.HostProtocolSupport", StringComparison.Ordinal);
        isBestHttpCoreHostConnection =
            string.Equals(type.FullName, "BestHTTP.Core.HostConnection", StringComparison.Ordinal);
        isBestHttpCoreHostDefinition =
            string.Equals(type.FullName, "BestHTTP.Core.HostDefinition", StringComparison.Ordinal);
        isBestHttpCoreHostConnectionKey =
            string.Equals(type.FullName, "BestHTTP.Core.HostConnectionKey", StringComparison.Ordinal);
        isBestHttpCoreAltSvcEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.AltSvcEventInfo", StringComparison.Ordinal);
        isBestHttpCoreHttp2ConnectProtocolInfo =
            string.Equals(type.FullName, "BestHTTP.Core.HTTP2ConnectProtocolInfo", StringComparison.Ordinal);
        isBestHttpCoreProtocolEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.ProtocolEventInfo", StringComparison.Ordinal);
        isBestHttpCoreProtocolEventHelper =
            string.Equals(type.FullName, "BestHTTP.Core.ProtocolEventHelper", StringComparison.Ordinal);
        isBestHttpCoreRequestEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.RequestEventInfo", StringComparison.Ordinal);
        isBestHttpCoreRequestEventHelper =
            string.Equals(type.FullName, "BestHTTP.Core.RequestEventHelper", StringComparison.Ordinal);
        isSignalRCoreInvocationDefinition =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.InvocationDefinition", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "InvocationDefinition", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isSignalRCoreTransportInterface =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.ITransport", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ITransport", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        isFutureCallback =
            string.Equals(type.FullName, "BestHTTP.Futures.FutureCallback`1", StringComparison.Ordinal) ||
            (string.Equals(type.Name, "FutureCallback`1", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.Futures", StringComparison.Ordinal));
        isFutureValueCallback =
            string.Equals(type.FullName, "BestHTTP.Futures.FutureValueCallback`1", StringComparison.Ordinal) ||
            (string.Equals(type.Name, "FutureValueCallback`1", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.Futures", StringComparison.Ordinal));
        isAddTypeMenuAttribute =
            string.Equals(type.FullName, "AddTypeMenuAttribute", StringComparison.Ordinal) &&
            string.IsNullOrWhiteSpace(type.Namespace);
        isGenericGraphNodeMetadata =
            string.Equals(type.FullName, "MXGenericGraph.GenericGraphNodeMetadata", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "GenericGraphNodeMetadata", StringComparison.Ordinal) && string.Equals(type.Namespace, "MXGenericGraph", StringComparison.Ordinal));
        isSkeletonAnimationPlayableHandle =
            string.Equals(type.FullName, "Spine.Unity.Playables.SkeletonAnimationPlayableHandle", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "SkeletonAnimationPlayableHandle", StringComparison.Ordinal) && string.Equals(type.Namespace, "Spine.Unity.Playables", StringComparison.Ordinal));
        isWwwForm =
            string.Equals(type.FullName, "UnityEngine.WWWForm", StringComparison.Ordinal) ||
            string.Equals(type.FullName, "WWWForm", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "WWWForm", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        parsedSafeGeneric = ResolutionUtilities.ParseGenericType(safeTypeName);
        isSystemActionDelegate =
            string.Equals(type.Namespace, "System", StringComparison.Ordinal) &&
            parsedSafeGeneric is { BaseName: "Action" };
        isSystemFuncDelegate =
            string.Equals(type.Namespace, "System", StringComparison.Ordinal) &&
            parsedSafeGeneric is { BaseName: "Func" };
        isNguiText =
            string.Equals(type.FullName, "NGUIText", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "NGUIText", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isUiDrawCall =
            string.Equals(type.FullName, "UIDrawCall", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "UIDrawCall", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isBetterList =
            string.Equals(type.Name, "BetterList`1", StringComparison.Ordinal) ||
            (safeTypeName.StartsWith("BetterList<", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isCachedGeometries =
            string.Equals(type.FullName, "CachedGeometries", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "CachedGeometries", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isEventDelegate =
            string.Equals(type.FullName, "EventDelegate", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "EventDelegate", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isEventDelegateParameter =
            string.Equals(safeTypeName, "Parameter", StringComparison.Ordinal) &&
            string.Equals(declaringType, "EventDelegate", StringComparison.Ordinal);
        isPropertyReference =
            string.Equals(type.FullName, "PropertyReference", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "PropertyReference", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        isFurnitureInventoryObject = string.Equals(type.FullName, "FurnitureInventoryObject", StringComparison.Ordinal);
        isFurnitureObject = string.Equals(type.FullName, "FurnitureObject", StringComparison.Ordinal);
        isFurnitureFilter =
            string.Equals(safeTypeName, "FurnitureFilter", StringComparison.Ordinal) &&
            string.Equals(declaringType, "FurnitureInventoryObject", StringComparison.Ordinal);
        isConstraintStruct =
            string.Equals(type.FullName, "MX.Logic.Data.TacticEntityConstraint", StringComparison.Ordinal) ||
            string.Equals(type.FullName, "MX.Logic.Data.TacticRangeConstraint", StringComparison.Ordinal) ||
            string.Equals(type.FullName, "MX.Logic.Data.TacticRoleConstraint", StringComparison.Ordinal) ||
            string.Equals(type.FullName, "MX.Logic.Data.TagConstraint", StringComparison.Ordinal);
        isGroundObstacleRepository = string.Equals(type.FullName, "GroundObstacleDataRepository", StringComparison.Ordinal);

        equatableInterface = BuildClosedGenericType(_equatableTypeName, !string.IsNullOrWhiteSpace(type.Namespace) ? $"{type.Namespace}.{safeTypeName}" : safeTypeName);
        vector2ListType = BuildListType(_unityVector2TypeName);
        skillAbilityModifierListType = BuildListType(_skillAbilityModifierDaoTypeName);
        tacticRangeArrayType = BuildArrayType("FlatData.TacticRange");
        tacticRoleArrayType = BuildArrayType("FlatData.TacticRole");
        keyedCollectionGroundObstacleType = !string.IsNullOrWhiteSpace(_groundObstacleDataTypeName)
            ? $"System.Collections.ObjectModel.KeyedCollection<System.UInt32, {_groundObstacleDataTypeName}>"
            : null;
        equalityComparerGroundObstacleType = BuildClosedGenericType("System.Collections.Generic.IEqualityComparer`1", _groundObstacleDataTypeName);
        comparerGroundObstacleType = BuildClosedGenericType("System.Collections.Generic.IComparer`1", _groundObstacleDataTypeName);
        furnitureObjectListType = BuildListType("FurnitureObject");
        furnitureObjectEnumerableType = BuildEnumerableType("FurnitureObject");
        furnitureDbListType = BuildListType("MX.GameLogic.DBModel.FurnitureDB");
        furnitureDbDictionaryType = BuildDictionaryType("System.Int64", "MX.GameLogic.DBModel.FurnitureDB");
        furnitureCategoryListType = BuildListType("FlatData.FurnitureCategory");
        furnitureSubCategoryListType = BuildListType("FlatData.FurnitureSubCategory");
        secureLongListType = BuildListType("SecureLong");
        furnitureTagsDictionaryType = BuildDictionaryType("FlatData.Tag", "System.Int32");
        purchaseCountDbListType = BuildListType("MX.GameLogic.DBModel.PurchaseCountDB");
        blockedProductDbListType = BuildListType("MX.GameLogic.DBModel.BlockedProductDB");
        bmGlyphListType = BuildListType("BMGlyph");
        bmGlyphDictionaryType = BuildDictionaryType("System.Int32", "BMGlyph");
        intListType = BuildListType("System.Int32");
        memberInfoArrayType = BuildArrayType("System.Reflection.MemberInfo");
        exposedMethodArrayType = BuildArrayType("RuntimeInspectorNamespace.ExposedMethod");
        byteArrayType = BuildArrayType("System.Byte");
        byteArrayListType = BuildListType(byteArrayType!);
        typeHashSetType = BuildClosedGenericType("System.Collections.Generic.HashSet`1", "System.Type");
        transformHashSetType = BuildClosedGenericType("System.Collections.Generic.HashSet`1", "UnityEngine.Transform");
        typeListType = BuildListType("System.Type");
        stringListType = BuildListType("System.String");
        exposedMethodListType = BuildListType("RuntimeInspectorNamespace.ExposedMethod");
        exposedExtensionMethodHolderListType = BuildListType("RuntimeInspectorNamespace.ExposedExtensionMethodHolder");
        customEditorAttributeListType = BuildListType("RuntimeInspectorNamespace.RuntimeInspectorCustomEditorAttribute");
        draggedReferenceItemStackType = BuildClosedGenericType("System.Collections.Generic.Stack`1", "RuntimeInspectorNamespace.DraggedReferenceItem");
        typeToVariablesDictionaryType = BuildDictionaryType("System.Type", memberInfoArrayType);
        typeToExposedMethodsDictionaryType = BuildDictionaryType("System.Type", exposedMethodArrayType);
        typeToTypeDictionaryType = BuildDictionaryType("System.Type", "System.Type");
        unityObjectArrayType = BuildArrayType("UnityEngine.Object");
        betterListColorType = BuildClosedGenericType("BetterList`1", "UnityEngine.Color");
        betterListSingleType = BuildClosedGenericType("BetterList`1", "System.Single");
        uiDrawCallListType = BuildClosedGenericType("BetterList`1", "UIDrawCall");
        vector3ListType = BuildListType(_unityVector3TypeName);
        vector4ListType = BuildListType("UnityEngine.Vector4");
        intArrayType = BuildArrayType("System.Int32");
        singleArrayType = BuildArrayType("System.Single");
        glyphInfoType = "NGUIText.GlyphInfo";
        fontType = "UnityEngine.Font";
        fontStyleType = "UnityEngine.FontStyle";
        alignmentType = "NGUIText.Alignment";
        symbolStyleType = "NGUIText.SymbolStyle";
        colorType = "UnityEngine.Color";
        stringBuilderType = "System.Text.StringBuilder";
        texture2DType = "UnityEngine.Texture2D";
        materialType = "UnityEngine.Material";
        textureType = "UnityEngine.Texture";
        transformType = "UnityEngine.Transform";
        meshType = "UnityEngine.Mesh";
        meshFilterType = "UnityEngine.MeshFilter";
        meshRendererType = "UnityEngine.MeshRenderer";
        materialPropertyBlockType = "UnityEngine.MaterialPropertyBlock";
        uiSkinType = "RuntimeInspectorNamespace.UISkin";
        draggedReferenceItemType = "RuntimeInspectorNamespace.DraggedReferenceItem";
        numberFormatInfoType = "System.Globalization.NumberFormatInfo";
        monthlyProductRewardsType = !string.IsNullOrWhiteSpace(_parcelInfoTypeName)
            ? BuildDictionaryType("FlatData.RewardTag", BuildListType(_parcelInfoTypeName))
            : null;
        betterListStringType = BuildClosedGenericType("BetterList`1", "System.String");
        stringDictionaryType = BuildDictionaryType("System.String", "System.String");
        eventDelegateParameterArrayType = BuildArrayType("EventDelegate.Parameter");
        eventDelegateListType = BuildListType("EventDelegate");
        parameterInfoArrayType = BuildArrayType("System.Reflection.ParameterInfo");
        objectArrayType = BuildArrayType("System.Object");
        boolArrayType = BuildArrayType("System.Boolean");
        stringArrayType = BuildArrayType("System.String");
        typeArrayType = BuildArrayType("System.Type");
        colorListType = BuildListType("UnityEngine.Color");
        listObjectType = BuildListType("System.Object");
        socketIoPacketListType = BuildListType("BestHTTP.SocketIO.Packet");
        signalRMessageListType = BuildListType("BestHTTP.SignalRCore.Messages.Message");
        actionObjectArrayType = BuildClosedGenericType("System.Action`1", objectArrayType);
        actionSignalRMessageType = BuildClosedGenericType("System.Action`1", "BestHTTP.SignalRCore.Messages.Message");
        actionTransportStatesPairType = BuildClosedGenericType("System.Action`2", "BestHTTP.SignalRCore.TransportStates", "BestHTTP.SignalRCore.TransportStates");
        bufferSegmentType = "BestHTTP.PlatformSupport.Memory.BufferSegment";
        stackVector2ListArrayType = string.IsNullOrWhiteSpace(vector2ListType) ? null : $"System.Collections.Generic.Stack<{vector2ListType}>[]";
        stackVector3ListArrayType = string.IsNullOrWhiteSpace(_unityVector3TypeName) ? null : $"System.Collections.Generic.Stack<{BuildListType(_unityVector3TypeName)!}>[]";
        stackColorListArrayType = string.IsNullOrWhiteSpace(colorListType) ? null : $"System.Collections.Generic.Stack<{colorListType}>[]";
        linkedVector2ListType = string.IsNullOrWhiteSpace(vector2ListType) ? null : $"System.Collections.Generic.LinkedList<{vector2ListType}>";
        linkedVector3ListType = string.IsNullOrWhiteSpace(_unityVector3TypeName) ? null : $"System.Collections.Generic.LinkedList<{BuildListType(_unityVector3TypeName)!}>";
        linkedColorListType = string.IsNullOrWhiteSpace(colorListType) ? null : $"System.Collections.Generic.LinkedList<{colorListType}>";
        genericStackListArrayType = "System.Collections.Generic.Stack<System.Collections.Generic.List<T>>[]";
        genericLinkedListType = "System.Collections.Generic.LinkedList<System.Collections.Generic.List<T>>";
        genericListType = "System.Collections.Generic.List<T>";
        repurchasableProductListType = "System.Collections.Generic.List<System.ValueTuple<MX.GameLogic.DBModel.PurchaseCountDB, MX.GameLogic.DBModel.MonthlyProductPurchaseDB>>";
        furnitureTimelineStateListType = "System.Collections.Generic.List<System.ValueTuple<FurnitureObject.FurnitureTimelineType, System.String>>";
        furnitureExcelType = "MX.Data.Excel.FurnitureExcel";
        inventoryObjectBaseFurnitureType = "InventoryObjectBase<FurnitureObject>";
        assetObjectBaseType = "AssetObjectBase";
        genericItemType = "T";
        genericItemArrayType = "T[]";
        genericEnumeratorType = "System.Collections.Generic.IEnumerator<T>";
        compareFuncType = "CompareFunc<T>";
        forceReferenceTypes =
            isByteReader ||
            isBmFont ||
            isBmGlyph ||
            isBmSymbol ||
            isRuntimeInspectorUtils ||
            isHubConnectionExtensions ||
            isUploadItemControllerExtensions ||
            isBitPackFormatter ||
            isSystemRuntimeUnsafe ||
            isCommunityToolkitArrayExtensions ||
            isTimelineExtensions ||
            isWebRequestUtils ||
            isJsonUtility ||
            isFlatBuffersByteBuffer ||
            isSocketIoTransportInterface ||
            isSocketIoJsonEncoder ||
            isSocketIoDefaultJsonEncoder ||
            isSignalRCoreEncoder ||
            isSignalRCoreProtocol ||
            isSignalRCoreUploadItemController ||
            isSignalRCoreStreamItemContainer ||
            isSignalRCoreCallbackDescriptor ||
            isSocketIO3EventsCallbackDescriptor ||
            isSocketIO3EventsSubscription ||
            isSocketIO3EventsTypedEventTable ||
            isBestHttpCoreConnectionEventInfo ||
            isBestHttpCoreConnectionEventHelper ||
            isBestHttpCoreHostProtocolSupport ||
            isBestHttpCoreHostConnection ||
            isBestHttpCoreHostDefinition ||
            isBestHttpCoreHostConnectionKey ||
            isBestHttpCorePluginEventInfo ||
            isBestHttpCorePluginEventHelper ||
            isBestHttpCoreAltSvcEventInfo ||
            isBestHttpCoreHttp2ConnectProtocolInfo ||
            isBestHttpCoreProtocolEventInfo ||
            isBestHttpCoreProtocolEventHelper ||
            isBestHttpCoreRequestEventInfo ||
            isBestHttpCoreRequestEventHelper ||
            isSignalRCoreInvocationDefinition ||
            isSignalRCoreTransportInterface ||
            isFutureCallback ||
            isFutureValueCallback ||
            isAddTypeMenuAttribute ||
            isGenericGraphNodeMetadata ||
            isSkeletonAnimationPlayableHandle ||
            isWwwForm ||
            isSystemActionDelegate ||
            isSystemFuncDelegate ||
            isNguiText ||
            isUiDrawCall ||
            isBetterList ||
            isCachedGeometries ||
            isEventDelegate ||
            isEventDelegateParameter ||
            isPropertyReference ||
            isFurnitureInventoryObject ||
            isFurnitureObject ||
            isFurnitureFilter;
    }

    public ResolvedMemberSet Apply()
    {
        if (!isAutoUseRuleDao &&
            !isGroundObstacleData &&
            !isGroundObstacleDataCollection &&
            !isGroundObstacleDataHashComparer &&
            !isPositionSetting &&
            !isAreaCollisionProperty &&
            !isAccountBillingInfo &&
            !isByteReader &&
            !isBmFont &&
            !isBmGlyph &&
            !isBmSymbol &&
            !isRuntimeInspectorUtils &&
            !isHubConnectionExtensions &&
            !isUploadItemControllerExtensions &&
            !isBitPackFormatter &&
            !isSystemRuntimeUnsafe &&
            !isCommunityToolkitArrayExtensions &&
            !isTimelineExtensions &&
            !isWebRequestUtils &&
            !isJsonUtility &&
            !isFlatBuffersByteBuffer &&
            !isSocketIoTransportInterface &&
            !isSocketIoJsonEncoder &&
            !isSocketIoDefaultJsonEncoder &&
            !isSignalRCoreEncoder &&
            !isSignalRCoreProtocol &&
            !isSignalRCoreUploadItemController &&
            !isSignalRCoreStreamItemContainer &&
            !isSignalRCoreCallbackDescriptor &&
            !isSocketIO3EventsCallbackDescriptor &&
            !isSocketIO3EventsSubscription &&
            !isSocketIO3EventsTypedEventTable &&
            !isBestHttpCoreConnectionEventInfo &&
            !isBestHttpCoreConnectionEventHelper &&
            !isBestHttpCoreHostProtocolSupport &&
            !isBestHttpCoreHostConnection &&
            !isBestHttpCoreHostDefinition &&
            !isBestHttpCoreHostConnectionKey &&
            !isBestHttpCorePluginEventInfo &&
            !isBestHttpCorePluginEventHelper &&
            !isBestHttpCoreAltSvcEventInfo &&
            !isBestHttpCoreHttp2ConnectProtocolInfo &&
            !isBestHttpCoreProtocolEventInfo &&
            !isBestHttpCoreProtocolEventHelper &&
            !isBestHttpCoreRequestEventInfo &&
            !isBestHttpCoreRequestEventHelper &&
            !isSignalRCoreInvocationDefinition &&
            !isSignalRCoreTransportInterface &&
            !isFutureCallback &&
            !isFutureValueCallback &&
            !isAddTypeMenuAttribute &&
            !isGenericGraphNodeMetadata &&
            !isSkeletonAnimationPlayableHandle &&
            !isWwwForm &&
            !isSystemActionDelegate &&
            !isSystemFuncDelegate &&
            !isNguiText &&
            !isUiDrawCall &&
            !isBetterList &&
            !isCachedGeometries &&
            !isEventDelegate &&
            !isEventDelegateParameter &&
            !isPropertyReference &&
            !isFurnitureInventoryObject &&
            !isFurnitureObject &&
            !isFurnitureFilter &&
            !isConstraintStruct &&
            !isGroundObstacleRepository)
        {
            return members;
        }

        if (Environment.GetEnvironmentVariable("YLDA_DEBUG_REFERENCE_TYPES") == "1" &&
            (isNguiText || isUiDrawCall || isRuntimeInspectorUtils))
        {
            Console.Error.WriteLine($"[refdbg] type={type.FullName} safe={safeTypeName} decl={declaringType ?? "<null>"} runtimeInspector={isRuntimeInspectorUtils} ngui={isNguiText} draw={isUiDrawCall}");
        }

        if ((isAutoUseRuleDao || isGroundObstacleData || isPositionSetting || isAreaCollisionProperty || isConstraintStruct) &&
            !string.IsNullOrWhiteSpace(equatableInterface) &&
            !relationships.Interfaces.Contains(equatableInterface!, StringComparer.Ordinal))
        {
            relationships = new TypeRelationships(
                relationships.BaseType,
                [equatableInterface!, .. relationships.Interfaces],
                relationships.Comments);
        }

        if (isGroundObstacleDataCollection && !string.IsNullOrWhiteSpace(keyedCollectionGroundObstacleType))
        {
            relationships = new TypeRelationships(
                keyedCollectionGroundObstacleType,
                relationships.Interfaces,
                relationships.Comments);
        }

        if (isFurnitureInventoryObject)
        {
            relationships = new TypeRelationships(
                inventoryObjectBaseFurnitureType,
                relationships.Interfaces,
                relationships.Comments);
        }

        if (isBitPackFormatter)
        {
            var formatterBase = BuildClosedGenericType(_memoryPackFormatterTypeName, boolArrayType);
            if (!string.IsNullOrWhiteSpace(formatterBase))
            {
                relationships = new TypeRelationships(
                    formatterBase,
                    relationships.Interfaces,
                    relationships.Comments);
            }
        }

        if (isGroundObstacleDataHashComparer)
        {
            var interfaceList = new List<string>(relationships.Interfaces);
            if (!string.IsNullOrWhiteSpace(equalityComparerGroundObstacleType) &&
                !interfaceList.Contains(equalityComparerGroundObstacleType, StringComparer.Ordinal))
            {
                interfaceList.Add(equalityComparerGroundObstacleType);
            }

            if (!interfaceList.Contains("System.Collections.IComparer", StringComparer.Ordinal))
                interfaceList.Add("System.Collections.IComparer");

            if (!string.IsNullOrWhiteSpace(comparerGroundObstacleType) &&
                !interfaceList.Contains(comparerGroundObstacleType, StringComparer.Ordinal))
            {
                interfaceList.Add(comparerGroundObstacleType);
            }

            relationships = new TypeRelationships(
                relationships.BaseType,
                interfaceList,
                relationships.Comments);
        }

        var adjustedFields = AdjustFields();
        var adjustedProperties = AdjustProperties();
        var adjustedMethods = AdjustMethods();
        var adjustedEvents = AdjustEvents();

        return new ResolvedMemberSet(relationships, adjustedFields, adjustedProperties, adjustedEvents, adjustedMethods);
    }

        string PreferReferenceType(string currentType, string? desiredType)
        {
            if (string.IsNullOrWhiteSpace(desiredType))
                return currentType;

            if (string.IsNullOrWhiteSpace(currentType) ||
                currentType.StartsWith("Type_0x", StringComparison.Ordinal) ||
                string.Equals(currentType, "int", StringComparison.Ordinal) ||
                string.Equals(currentType, "long", StringComparison.Ordinal) ||
                string.Equals(currentType, "float", StringComparison.Ordinal) ||
                string.Equals(currentType, "bool", StringComparison.Ordinal) ||
                string.Equals(currentType, "System.Int32", StringComparison.Ordinal) ||
                string.Equals(currentType, "System.Int64", StringComparison.Ordinal) ||
                string.Equals(currentType, "System.Single", StringComparison.Ordinal) ||
                string.Equals(currentType, "System.Boolean", StringComparison.Ordinal))
            {
                return desiredType!;
            }

            return currentType;
        }
}
