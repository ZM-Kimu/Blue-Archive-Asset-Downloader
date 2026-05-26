using static CnMetadataExporter.TypeNameHelpers;

namespace CnMetadataExporter;

internal sealed partial class ReferenceModelAdjustment
{
    private string? DesiredFieldType(string identifier) => type.FullName switch
        {
            "AutoUseRuleDAO" => identifier switch
            {
                "Empty" => "AutoUseRuleDAO",
                "ConditionArgument" => "System.String",
                "TryToUseSkillModifiers" => skillAbilityModifierListType,
                _ => null,
            },
            "MX.Logic.Data.TacticEntityConstraint" => identifier switch
            {
                "Empty" => "MX.Logic.Data.TacticEntityConstraint",
                _ => null,
            },
            "MX.Logic.Data.TacticRangeConstraint" => identifier switch
            {
                "Empty" => "MX.Logic.Data.TacticRangeConstraint",
                "TacticRanges" => tacticRangeArrayType,
                _ => null,
            },
            "MX.Logic.Data.TacticRoleConstraint" => identifier switch
            {
                "Empty" => "MX.Logic.Data.TacticRoleConstraint",
                "TacticRole" => tacticRoleArrayType,
                _ => null,
            },
            "MX.Logic.Data.TagConstraint" => identifier switch
            {
                "Empty" => "MX.Logic.Data.TagConstraint",
                _ => null,
            },
            "MX.Logic.Data.AreaCollisionProperty" => identifier switch
            {
                "Empty" => "MX.Logic.Data.AreaCollisionProperty",
                _ => null,
            },
            "MX.Visual.Data.PositionSetting" => identifier switch
            {
                "Empty" => "MX.Visual.Data.PositionSetting",
                "BoneNameCustom" => "System.String",
                "WorldPosition" or "PositionOffset" or "RandomPositionOffsetMin" or "RandomPositionOffsetMax" or "AlignRotationOffset" => _unityVector3TypeName,
                _ => null,
            },
            "AccountBillingInfo" => identifier switch
            {
                "_MonthlyProductRewards_k__BackingField" => monthlyProductRewardsType,
                "_RepurchasableProductPurchaseCountDBList_k__BackingField" => purchaseCountDbListType,
                "_RepurchasableProductList_k__BackingField" => repurchasableProductListType,
                "_NewProductList_k__BackingField" => purchaseCountDbListType,
                "_PurchaseCountList_k__BackingField" => purchaseCountDbListType,
                "_BlockedProductList_k__BackingField" => blockedProductDbListType,
                _ => null,
            },
            "ByteReader" => identifier switch
            {
                "mBuffer" => "System.Byte[]",
                "mTemp" => betterListStringType,
                _ => null,
            },
            "BMFont" => identifier switch
            {
                "mSaved" => bmGlyphListType,
                "mDict" => bmGlyphDictionaryType,
                _ => null,
            },
            "BMGlyph" => identifier switch
            {
                "index" or "x" or "y" or "width" or "height" or "offsetX" or "offsetY" or "advance" or "channel" => "System.Int32",
                "kerning" => intListType,
                _ => null,
            },
            "BMSymbol" => identifier switch
            {
                "sequence" or "spriteName" => "System.String",
                _ => null,
            },
            "MemoryPack.Compression.BitPackFormatter" => identifier switch
            {
                "Default" => "MemoryPack.Compression.BitPackFormatter",
                _ => null,
            },
            _ when isRuntimeInspectorUtils => identifier switch
            {
                "typeToVariables" => typeToVariablesDictionaryType,
                "typeToExposedMethods" => typeToExposedMethodsDictionaryType,
                "commonSerializableTypes" => typeHashSetType,
                "validVariablesList" => BuildListType("System.Reflection.MemberInfo"),
                "typesToSearchForVariablesList" => typeListType,
                "propertyNamesInVariablesList" => stringListType,
                "exposedMethodsList" => exposedMethodListType,
                "exposedExtensionMethods" => exposedExtensionMethodHolderListType,
                "customEditors" => typeToTypeDictionaryType,
                "customEditorAttributes" => customEditorAttributeListType,
                "IgnoredTransformsInHierarchy" => transformHashSetType,
                "popupCanvas" or "popupReferenceCanvas" => "UnityEngine.Canvas",
                "tooltipPopup" => "RuntimeInspectorNamespace.Tooltip",
                "draggedReferenceItemsPool" => draggedReferenceItemStackType,
                "numberFormat" => numberFormatInfoType,
                "stringBuilder" => stringBuilderType,
                _ => null,
            },
            _ when isWwwForm => identifier switch
            {
                "formData" => byteArrayListType,
                "fieldNames" or "fileNames" or "types" => stringListType,
                "boundary" or "dDash" or "crlf" or "contentTypeHeader" or "dispositionHeader" or "endQuote" or "fileNameField" or "ampersand" or "equal" => byteArrayType,
                "containsFiles" => "System.Boolean",
                _ => null,
            },
            "NGUIText" => identifier switch
            {
                "bitmapFont" => "INGUIFont",
                "dynamicFont" => fontType,
                "glyph" => glyphInfoType,
                "fontSize" or "rectWidth" or "rectHeight" or "regionWidth" or "regionHeight" or "maxLines" or "finalSize" => "System.Int32",
                "fontScale" or "pixelDensity" or "spacingX" or "spacingY" or "finalSpacingX" or "finalLineHeight" or "baseline" or "mAlpha" or "sizeShrinkage" => "System.Single",
                "fontStyle" => fontStyleType,
                "alignment" => alignmentType,
                "tint" or "gradientBottom" or "gradientTop" or "mInvisible" or "s_c0" or "s_c1" => colorType,
                "gradient" or "encoding" or "premultiply" or "useSymbols" => "System.Boolean",
                "symbolStyle" => symbolStyleType,
                "mColors" => betterListColorType,
                "mSizes" => betterListSingleType,
                "mBoldOffset" => singleArrayType,
                _ => null,
            },
            "UIDrawCall" => identifier switch
            {
                "mActiveList" or "mInactiveList" => uiDrawCallListType,
                "widgetCount" or "depthStart" or "depthEnd" or "mClipCount" or "mRenderQueue" or "mTriangles" or "mSortingOrder" or "dx9BugWorkaround" => "System.Int32",
                "manager" or "panel" => "UIPanel",
                "clipTexture" => texture2DType,
                "alwaysOnScreen" or "mRebuildMat" or "mLegacyShader" or "isDirty" or "mTextureClip" or "mIsNew" => "System.Boolean",
                "verts" or "norms" => vector3ListType,
                "tans" or "uv2" => vector4ListType,
                "uvs" or "clipUVs" => vector2ListType,
                "cols" => colorListType,
                "mMaterial" or "mDynamicMat" => materialType,
                "mTexture" => textureType,
                "mTrans" => transformType,
                "mMesh" => meshType,
                "mFilter" => meshFilterType,
                "mRenderer" => meshRendererType,
                "mIndices" => intArrayType,
                "mCache" => "Nordeus.DataStructures.VaryingIntList",
                "mBlock" => materialPropertyBlockType,
                "ClipRange" or "ClipArgs" or "ClipParams" => intArrayType,
                _ => null,
            },
            _ when isBetterList => identifier switch
            {
                "buffer" => genericItemArrayType,
                "size" => "System.Int32",
                _ => null,
            },
            "CachedGeometries" => identifier switch
            {
                "cachedListsOfVector2List" => stackVector2ListArrayType,
                "cachedBigListsOfVector2List" => linkedVector2ListType,
                "cachedListsOfVector3List" => stackVector3ListArrayType,
                "cachedBigListsOfVector3List" => linkedVector3ListType,
                "cachedListsOfColorList" => stackColorListArrayType,
                "cachedBigListsOfColorList" => linkedColorListType,
                _ => null,
            },
            "EventDelegate" => identifier switch
            {
                "mTarget" => "UnityEngine.MonoBehaviour",
                "mMethodName" => "System.String",
                "mParameters" => eventDelegateParameterArrayType,
                "mCachedCallback" => "Callback",
                "mRawDelegate" or "mCached" => "System.Boolean",
                "mMethod" => "System.Reflection.MethodInfo",
                "mParameterInfos" => parameterInfoArrayType,
                "mArgs" => objectArrayType,
                "oneShot" => "System.Boolean",
                "s_Hash" => "System.Int32",
                _ => null,
            },
            _ when isPropertyReference => identifier switch
            {
                "mProperty" => "System.Reflection.PropertyInfo",
                "s_Hash" => "System.Int32",
                _ => null,
            },
            "FurnitureInventoryObject" => identifier switch
            {
                _ => null,
            },
            "FurnitureObject" => identifier switch
            {
                "_CafeDBId_k__BackingField" => "System.Int64",
                "_Tags_k__BackingField" => furnitureTagsDictionaryType,
                "availableCharacterStates" => furnitureTimelineStateListType,
                "furnitureExcel" => furnitureExcelType,
                "rotationDegree" => "System.Single",
                "_InvalidId_k__BackingField" => "System.Int64",
                _ => null,
            },
            "MX.Data.GroundObstacleData" => identifier switch
            {
                "Scale" or "Offset" or "Size" or "Direction" => _unityVector2TypeName,
                "PreDuration" or "DestroyDuration" or "RetreatDuration" or "RemainTime" => "System.Single",
                "UniqueName" => "System.String",
                "NameHash" => "System.UInt32",
                "EnemyPoints" or "PlayerPoints" => vector2ListType,
                _ => null,
            },
            _ when isEventDelegateParameter => identifier switch
            {
                "obj" => "UnityEngine.Object",
                "field" => "System.String",
                "expectedType" => "System.Type",
                "cached" => "System.Boolean",
                "propInfo" => "System.Reflection.PropertyInfo",
                "fieldInfo" => "System.Reflection.FieldInfo",
                _ => null,
            },
            _ when isFurnitureFilter => identifier switch
            {
                "CategoryList" => furnitureCategoryListType,
                "SubCategoryList" => furnitureSubCategoryListType,
                _ => null,
            },
            _ when isWebRequestUtils => identifier switch
            {
                "domainRegex" => "System.Text.RegularExpressions.Regex",
                _ => null,
            },
            _ when isFlatBuffersByteBuffer => identifier switch
            {
                "_buffer" => "System.Byte[]",
                "floathelper" => "System.Single[]",
                "inthelper" => "System.Int32[]",
                "doublehelper" => "System.Double[]",
                "ulonghelper" => "System.UInt64[]",
                "_pos" => "System.Int32",
                _ => null,
            },
            _ when isAddTypeMenuAttribute => identifier switch
            {
                "_Order_k__BackingField" => "System.Int32",
                "k_Separeters" => "System.Char[]",
                _ => null,
            },
            _ when isGenericGraphNodeMetadata => identifier switch
            {
                "Position" => _unityVector2TypeName,
                "IsSet" => "System.Boolean",
                _ => null,
            },
            _ when isSkeletonAnimationPlayableHandle => identifier switch
            {
                "skeletonAnimation" => "Spine.Unity.SkeletonAnimation",
                _ => null,
            },
            _ when isSignalRCoreStreamItemContainer => identifier switch
            {
                "id" => "System.Int64",
                "_Items_k__BackingField" or "<Items>k__BackingField" => genericListType,
                "_LastAdded_k__BackingField" or "<LastAdded>k__BackingField" => genericItemType,
                "IsCanceled" => "System.Boolean",
                _ => null,
            },
            _ when isSignalRCoreCallbackDescriptor => identifier switch
            {
                "ParamTypes" => typeArrayType,
                "Callback" => actionObjectArrayType,
                _ => null,
            },
            _ when isSocketIO3EventsCallbackDescriptor => identifier switch
            {
                "ParamTypes" => typeArrayType,
                "Callback" => actionObjectArrayType,
                "Once" => "System.Boolean",
                _ => null,
            },
            _ when isSocketIO3EventsSubscription => identifier switch
            {
                "callbacks" => "System.Collections.Generic.List`1<BestHTTP.SocketIO3.Events.CallbackDescriptor>",
                _ => null,
            },
            _ when isSocketIO3EventsTypedEventTable => identifier switch
            {
                "subscriptions" => "System.Collections.Generic.Dictionary`2<System.String, BestHTTP.SocketIO3.Events.Subscription>",
                _ => null,
            },
            _ when isBestHttpCoreConnectionEventInfo => identifier switch
            {
                "Source" => "BestHTTP.Connections.ConnectionBase",
                "Event" => "BestHTTP.Core.ConnectionEvents",
                "State" => "BestHTTP.Connections.HTTPConnectionStates",
                "ProtocolSupport" => "BestHTTP.Core.HostProtocolSupport",
                "Request" => "BestHTTP.HTTPRequest",
                _ => null,
            },
            _ when isBestHttpCoreConnectionEventHelper => identifier switch
            {
                "connectionEventQueue" => "System.Collections.Concurrent.ConcurrentQueue`1<BestHTTP.Core.ConnectionEventInfo>",
                "OnEvent" => "System.Action`1<BestHTTP.Core.ConnectionEventInfo>",
                _ => null,
            },
            _ when isBestHttpCoreHostProtocolSupport => identifier switch
            {
                "value__" => "System.Byte",
                _ => null,
            },
            _ when isBestHttpCoreHostConnection => identifier switch
            {
                "_LastProtocolSupportUpdate_k__BackingField" or "<LastProtocolSupportUpdate>k__BackingField" => "System.DateTime",
                "Connections" => "System.Collections.Generic.List`1<BestHTTP.Connections.ConnectionBase>",
                "Queue" => "System.Collections.Generic.List`1<BestHTTP.HTTPRequest>",
                _ => null,
            },
            _ when isBestHttpCoreHostDefinition => identifier switch
            {
                "Alternates" => "System.Collections.Generic.List`1<BestHTTP.Core.HostConnection>",
                "hostConnectionVariant" => "System.Collections.Generic.Dictionary`2<System.String, BestHTTP.Core.HostConnection>",
                "keyBuilder" => "System.Text.StringBuilder",
                "keyBuilderLock" => "System.Threading.ReaderWriterLockSlim",
                _ => null,
            },
            _ when isBestHttpCoreHostConnectionKey => identifier switch
            {
                "Host" => "System.String",
                "Connection" => "System.String",
                _ => null,
            },
            _ when isBestHttpCorePluginEventInfo => identifier switch
            {
                "Event" => "BestHTTP.Core.PluginEvents",
                "Payload" => "System.Object",
                _ => null,
            },
            _ when isBestHttpCorePluginEventHelper => identifier switch
            {
                "pluginEvents" => "System.Collections.Concurrent.ConcurrentQueue`1<BestHTTP.Core.PluginEventInfo>",
                "OnEvent" => "System.Action`1<BestHTTP.Core.PluginEventInfo>",
                _ => null,
            },
            _ when isBestHttpCoreAltSvcEventInfo => identifier switch
            {
                "Host" => "System.String",
                "Response" => "BestHTTP.HTTPResponse",
                _ => null,
            },
            _ when isBestHttpCoreHttp2ConnectProtocolInfo => identifier switch
            {
                "Host" => "System.String",
                "Enabled" => "System.Boolean",
                _ => null,
            },
            _ when isBestHttpCoreProtocolEventInfo => identifier switch
            {
                "Source" => "BestHTTP.Core.IProtocol",
                _ => null,
            },
            _ when isBestHttpCoreProtocolEventHelper => identifier switch
            {
                "protocolEvents" => "System.Collections.Concurrent.ConcurrentQueue`1<BestHTTP.Core.ProtocolEventInfo>",
                "ActiveProtocols" => "System.Collections.Generic.List`1<BestHTTP.Core.IProtocol>",
                "OnEvent" => "System.Action`1<BestHTTP.Core.ProtocolEventInfo>",
                _ => null,
            },
            _ when isBestHttpCoreRequestEventInfo => identifier switch
            {
                "SourceRequest" => "BestHTTP.HTTPRequest",
                "Event" => "BestHTTP.Core.RequestEvents",
                "State" => "BestHTTP.HTTPRequestStates",
                "Progress" => "System.Int64",
                "ProgressLength" => "System.Int64",
                "Data" => "System.Byte[]",
                "DataLength" => "System.Int32",
                _ => null,
            },
            _ when isBestHttpCoreRequestEventHelper => identifier switch
            {
                "requestEventQueue" => "System.Collections.Concurrent.ConcurrentQueue`1<BestHTTP.Core.RequestEventInfo>",
                "OnEvent" => "System.Action`1<BestHTTP.Core.RequestEventInfo>",
                _ => null,
            },
            _ when isSignalRCoreInvocationDefinition => identifier switch
            {
                "callback" => actionSignalRMessageType,
                "returnType" => "System.Type",
                _ => null,
            },
            _ => null,
        };
}
