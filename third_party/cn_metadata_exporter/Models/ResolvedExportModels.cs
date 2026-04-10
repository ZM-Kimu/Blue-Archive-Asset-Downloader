namespace YldaDumpCsExporter;

[Flags]
internal enum PrivateMemberKinds
{
    None = 0,
    Fields = 1 << 0,
    Properties = 1 << 1,
    Events = 1 << 2,
    Methods = 1 << 3,
    All = Fields | Properties | Events | Methods,
}

internal enum ExportMemberAccessibility
{
    Unknown = 0,
    Private,
    PrivateProtected,
    Internal,
    Protected,
    ProtectedInternal,
    Public,
}

internal sealed record TypeIndexArtifact(
    Dictionary<uint, string> GlobalTypeNames,
    Dictionary<int, Dictionary<uint, string>> LocalTypeOverridesByType);

internal sealed record RelationshipIndexEntry(
    int TypeIndex,
    string? DeclaringType,
    string? BaseType,
    string[] Interfaces,
    string[] Comments);

internal sealed record RelationshipIndexArtifact(
    Dictionary<int, RelationshipIndexEntry> RelationshipsByType);

internal sealed record MemberIndexArtifact(
    ResolvedExportTypeModel[] Types);

internal sealed record ResolvedExportArtifact(
    string BaselineLibrary,
    CachedSectionDescriptor[] Sections,
    TypeIndexArtifact TypeIndex,
    RelationshipIndexArtifact RelationshipIndex,
    MemberIndexArtifact MemberIndex)
{
    public Dictionary<uint, string> GlobalTypeNames => TypeIndex.GlobalTypeNames;
    public ResolvedExportTypeModel[] Types => MemberIndex.Types;
}

internal sealed record ResolvedExportTypeModel(
    int TypeIndex,
    uint TypeToken,
    string FullName,
    string ImageName,
    string NamespaceName,
    string SafeTypeName,
    string? OriginalTypeName,
    string[] GenericParameterNames,
    string[] Modifiers,
    string? DeclaringType,
    string? BaseType,
    string[] Interfaces,
    string[] Comments,
    ResolvedExportFieldModel[] Fields,
    ResolvedExportPropertyModel[] Properties,
    ResolvedExportEventModel[] Events,
    ResolvedExportMethodModel[] Methods);

internal readonly record struct ResolvedExportFieldModel(
    uint Token,
    string Identifier,
    string TypeName,
    string[] Modifiers,
    ExportMemberAccessibility Accessibility);

internal readonly record struct ResolvedExportParameterModel(
    string Identifier,
    string TypeName,
    string ModifierPrefix);

internal readonly record struct ResolvedExportMethodModel(
    uint Token,
    string DisplayName,
    string ReturnTypeName,
    string[] Modifiers,
    ExportMemberAccessibility Accessibility,
    ushort Slot,
    ResolvedExportParameterModel[] Parameters);

internal readonly record struct ResolvedExportPropertyModel(
    uint Token,
    string DisplayName,
    string TypeName,
    string[] Modifiers,
    ExportMemberAccessibility Accessibility,
    string[] Accessors);

internal readonly record struct ResolvedExportEventModel(
    uint Token,
    string DisplayName,
    string TypeName,
    string[] Modifiers,
    ExportMemberAccessibility Accessibility);

internal readonly record struct CachedSectionDescriptor(
    int HeaderOffset,
    string Name,
    int Offset,
    int Size,
    int? RecordSize,
    bool IsKnown);
