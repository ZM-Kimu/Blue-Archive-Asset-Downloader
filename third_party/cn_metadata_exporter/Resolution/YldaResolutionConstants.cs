namespace YldaDumpCsExporter;

internal static class YldaResolutionConstants
{
    public const uint TypeAttrVisibilityMask = 0x00000007;
    public const uint TypeAttrPublic = 0x00000001;
    public const uint TypeAttrNestedPublic = 0x00000002;
    public const uint TypeAttrNestedPrivate = 0x00000003;
    public const uint TypeAttrNestedFamily = 0x00000004;
    public const uint TypeAttrNestedAssembly = 0x00000005;
    public const uint TypeAttrNestedFamAndAssem = 0x00000006;
    public const uint TypeAttrNestedFamOrAssem = 0x00000007;
    public const uint TypeAttrAbstract = 0x00000080;
    public const uint TypeAttrSealed = 0x00000100;
    public const uint TypeAttrInterface = 0x00000020;

    public const ushort MethodAttrMemberAccessMask = 0x0007;
    public const ushort MethodAttrPrivate = 0x0001;
    public const ushort MethodAttrFamAndAssem = 0x0002;
    public const ushort MethodAttrAssembly = 0x0003;
    public const ushort MethodAttrFamily = 0x0004;
    public const ushort MethodAttrFamOrAssem = 0x0005;
    public const ushort MethodAttrPublic = 0x0006;
    public const ushort MethodAttrStatic = 0x0010;
    public const ushort MethodAttrFinal = 0x0020;
    public const ushort MethodAttrVirtual = 0x0040;
    public const ushort MethodAttrNewSlot = 0x0100;
    public const ushort MethodAttrAbstract = 0x0400;
    public const ushort MethodImplCodeTypeMask = 0x0003;
    public const ushort MethodImplNative = 0x0001;
    public const ushort MethodImplRuntime = 0x0003;
    public const ushort MethodImplInternalCall = 0x1000;

    public static readonly Dictionary<string, string> SystemAliases = new(StringComparer.Ordinal)
    {
        ["System.Void"] = "void",
        ["System.Boolean"] = "bool",
        ["System.String"] = "string",
        ["System.Object"] = "object",
        ["System.Int32"] = "int",
        ["System.UInt32"] = "uint",
        ["System.Int64"] = "long",
        ["System.UInt64"] = "ulong",
        ["System.Int16"] = "short",
        ["System.UInt16"] = "ushort",
        ["System.Byte"] = "byte",
        ["System.SByte"] = "sbyte",
        ["System.Char"] = "char",
        ["System.Single"] = "float",
        ["System.Double"] = "double",
        ["System.Decimal"] = "decimal",
        ["System.IntPtr"] = "nint",
        ["System.UIntPtr"] = "nuint",
    };

    public static readonly Dictionary<string, string> AliasToSystemType = SystemAliases.ToDictionary(
        pair => pair.Value,
        pair => pair.Key,
        StringComparer.Ordinal);

    public static readonly HashSet<string> LocalInferenceTypeNames = new(StringComparer.Ordinal)
    {
        "System.Collections.Generic.IEnumerable`1",
        "System.Collections.Generic.IEnumerator`1",
        "System.Collections.Generic.IReadOnlyList`1",
        "System.Collections.Generic.IReadOnlyDictionary`2",
        "System.Collections.Generic.List`1",
        "System.Collections.Generic.Dictionary`2",
    };

    public static readonly HashSet<string> IntLikeFieldNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "padLeft",
        "padRight",
        "padBottom",
        "padTop",
        "index",
        "charsPerSecond",
        "mCurrentOffset",
        "mTouchID",
        "minWidth",
        "minHeight",
        "maxWidth",
        "maxHeight",
        "mWidth",
        "mHeight",
        "maxPerLine",
        "tweenGroup",
        "fontSize",
        "currentAction",
        "__1__state",
        "value__",
    };

    public static readonly HashSet<string> BoolLikeFieldNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "ignoreDisabled",
        "keepFullDimensions",
        "dragHighlight",
        "pixelSnap",
        "includeChildren",
        "clickToDrag",
        "cloneOnDrag",
        "interactable",
        "smoothDragStart",
        "restrictWithinPanel",
        "updateAnchors",
        "onHover",
        "onPress",
        "onClick",
        "onDoubleClick",
        "onSelect",
        "onDrag",
        "onDrop",
        "onSubmit",
        "onScroll",
        "animateSmoothly",
        "hideInactive",
        "keepWithinPanel",
        "startsSelected",
        "resetOnPlay",
        "resetIfDisabled",
        "keepValue",
        "isMissionToastReady",
        "showToast",
        "showRedDot",
        "show",
        "isRead",
        "isFeedBack",
    };

    public static readonly HashSet<string> ByteArrayParameterNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "bytes",
        "buffer",
    };

    public static readonly HashSet<string> BoolLikeParameterNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "notify",
        "merge",
        "warnIfMissing",
        "includeInactive",
        "considerChildren",
        "wrapLineColors",
        "useEllipsis",
        "generateNormals",
        "applyRQImmediately",
        "fromFormationPopup",
        "immediate",
        "changeInstantly",
        "forceReplace",
        "fromWork",
        "legacyMode",
        "full",
        "updateAnchors",
        "enabled",
        "visible",
        "hideWhileLoading",
        "show",
        "keepCharCount",
        "considerInactive",
        "useErosion",
        "useUnexpectedEvent",
        "useCalculate",
        "useConquestObject",
    };

    public static readonly HashSet<string> IntLikeParameterNames = new(StringComparer.Ordinal)
    {
        "offset",
        "depth",
        "tier",
        "index",
        "start",
        "X",
        "Y",
        "displayOrder",
        "targetHeightIndex",
        "portalId",
        "moveRange",
        "targetLevel",
        "positionIndex01",
        "positionIndex02",
        "positionIndex03",
        "positionIndex04",
        "positionIndex05",
        "positionIndex06",
        "targetindex",
    };

    public static readonly HashSet<string> FloatLikeParameterNames = new(StringComparer.Ordinal)
    {
        "x",
        "y",
        "z",
        "X",
        "Z",
        "fontScale",
        "delay",
        "rot",
        "normalizedTime",
        "overrideDuration",
        "durationOffset",
        "timeScale",
        "audioPitch",
        "mixDuration",
        "strength",
        "springStrength",
        "animateDuration",
        "maxDistanceFromTarget",
        "resetToTime",
        "zOffset",
        "ratio",
        "epsilon",
        "lifeTime",
        "gap",
        "blend",
        "time",
        "floatParam",
        "speed",
        "dist",
        "volume",
        "Volume",
        "scale",
        "Scale",
        "bodyRadius",
        "BodyRadius",
        "cameraSmoothTime",
        "CameraSmoothTime",
        "waitTimeAfterSpawn",
        "WaitTimeAfterSpawn",
        "firstCoolTime",
        "FirstCoolTime",
        "coolTime",
        "cameraSizeRate",
        "CameraSizeRate",
        "feverCriticalRate",
        "feverAttackRate",
        "FeverCriticalRate",
        "FeverAttackRate",
        "cameraAngle",
        "cameraZoomMax",
        "cameraZoomMin",
        "cameraZoomDefault",
        "CameraAngle",
        "CameraZoomMax",
        "CameraZoomMin",
        "CameraZoomDefault",
        "themeLoadingProgressTime",
        "conquestMapBoundaryOffsetLeft",
        "conquestMapBoundaryOffsetRight",
        "conquestMapBoundaryOffsetTop",
        "conquestMapBoundaryOffsetBottom",
        "conquestMapCenterOffsetX",
        "conquestMapCenterOffsetY",
        "ConquestMapBoundaryOffsetLeft",
        "ConquestMapBoundaryOffsetRight",
        "ConquestMapBoundaryOffsetTop",
        "ConquestMapBoundaryOffsetBottom",
        "ConquestMapCenterOffsetX",
        "ConquestMapCenterOffsetY",
        "hexaMapBoundaryOffset",
        "hexaMapStartCameraOffset",
        "HexaMapBoundaryOffset",
        "positionX",
        "positionY",
        "PositionX",
        "PositionY",
        "rotation",
        "Rotation",
        "offsetX",
        "offsetY",
        "OffsetX",
        "OffsetY",
        "scaleX",
        "scaleY",
        "ScaleX",
        "ScaleY",
        "spineOffsetX",
        "spineOffsetY",
        "SpineOffsetX",
        "SpineOffsetY",
        "dialogOffsetX",
        "dialogOffsetY",
        "DialogOffsetX",
        "DialogOffsetY",
        "inventoryOffsetX",
        "inventoryOffsetY",
        "inventoryOffsetZ",
        "InventoryOffsetX",
        "InventoryOffsetY",
        "InventoryOffsetZ",
        "dateResultSpineOffsetX",
        "DateResultSpineOffsetX",
        "Length",
        "FrameRate",
        "Time",
        "FloatParam",
        "SpeedParamter",
        "StateSpeed",
        "StartX",
        "StartY",
        "Gap",
        "DefaultScale",
        "MinScale",
        "MaxScale",
        "CharacterBodyCenterX",
        "CharacterBodyCenterY",
        "AnimationUnitDelay",
        "MaxDistance",
        "LeftMargin",
        "BottomMargin",
        "PosX",
        "PosY",
        "IconOffsetX",
        "IconOffsetY",
        "HpBarHeight",
        "HighlightFloaterHeight",
        "EmojiOffsetX",
        "EmojiOffsetY",
        "CameraSmoothtime",
        "Waithtimeafterspawn",
    };
}
