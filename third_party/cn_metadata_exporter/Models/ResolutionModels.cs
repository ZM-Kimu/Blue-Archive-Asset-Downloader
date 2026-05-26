namespace CnMetadataExporter;

internal readonly record struct TypeRelationships(
    string? BaseType,
    IReadOnlyList<string> Interfaces,
    IReadOnlyList<string> Comments);

internal readonly record struct InterfaceContract(
    string FullName,
    IReadOnlySet<string> MemberNames,
    IReadOnlySet<string> Members,
    int MemberCount);

internal sealed record ResolvedTypeModel(
    TypeDefinition Type,
    string ImageName,
    string NamespaceName,
    string SafeTypeName,
    string? OriginalTypeName,
    IReadOnlyList<string> GenericParameterNames,
    IReadOnlyList<string> Modifiers,
    string? DeclaringType,
    TypeRelationships Relationships,
    IReadOnlyList<ResolvedFieldModel> Fields,
    IReadOnlyList<ResolvedPropertyModel> Properties,
    IReadOnlyList<ResolvedEventModel> Events,
    IReadOnlyList<ResolvedMethodModel> Methods);

internal readonly record struct ResolvedFieldModel(
    FieldDefinition Definition,
    string Identifier,
    string TypeName,
    IReadOnlyList<string> Modifiers,
    ExportMemberAccessibility Accessibility);

internal readonly record struct ResolvedParameterModel(
    ParameterDefinition Definition,
    string Identifier,
    string TypeName,
    string ModifierPrefix = "");

internal readonly record struct ResolvedMethodModel(
    MethodDefinition Definition,
    string DisplayName,
    string ReturnTypeName,
    IReadOnlyList<string> Modifiers,
    ExportMemberAccessibility Accessibility,
    IReadOnlyList<ResolvedParameterModel> Parameters);

internal readonly record struct ResolvedPropertyModel(
    PropertyDefinition Definition,
    string DisplayName,
    string TypeName,
    IReadOnlyList<string> Modifiers,
    ExportMemberAccessibility Accessibility,
    IReadOnlyList<string> Accessors);

internal readonly record struct ResolvedEventModel(
    EventDefinition Definition,
    string DisplayName,
    string TypeName,
    IReadOnlyList<string> Modifiers,
    ExportMemberAccessibility Accessibility);

internal readonly record struct ResolvedTypeContext(
    IReadOnlyDictionary<uint, string> TypeNameMap,
    IReadOnlyDictionary<string, string> PropertyTypeByName,
    string? DeclaringType,
    TypeRelationships Relationships);
