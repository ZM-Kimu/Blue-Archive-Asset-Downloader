using static CnMetadataExporter.TypeNameHelpers;

namespace CnMetadataExporter;

internal sealed class MemoryPackFormatterResolver
{
    private readonly string? _flatDataTagTypeName;
    private readonly string? _mediaCatalogTypeName;
    private readonly string? _mediaTypeName;
    private readonly string? _memoryPackableTypeName;
    private readonly string? _memoryPackFormatterTypeName;
    private readonly string? _memoryPackReaderTypeName;
    private readonly string? _memoryPackWriterTypeName;
    private readonly string? _patchFileInfoTypeName;
    private readonly string? _tableBundleTypeName;
    private readonly string? _tableCatalogTypeName;
    private readonly string? _tablePatchPackTypeName;

    public MemoryPackFormatterResolver(KnownTypeCatalog knownTypes)
    {
        _flatDataTagTypeName = knownTypes.FlatDataTagTypeName;
        _mediaCatalogTypeName = knownTypes.MediaCatalogTypeName;
        _mediaTypeName = knownTypes.MediaTypeName;
        _memoryPackableTypeName = knownTypes.MemoryPackableTypeName;
        _memoryPackFormatterTypeName = knownTypes.MemoryPackFormatterTypeName;
        _memoryPackReaderTypeName = knownTypes.MemoryPackReaderTypeName;
        _memoryPackWriterTypeName = knownTypes.MemoryPackWriterTypeName;
        _patchFileInfoTypeName = knownTypes.PatchFileInfoTypeName;
        _tableBundleTypeName = knownTypes.TableBundleTypeName;
        _tableCatalogTypeName = knownTypes.TableCatalogTypeName;
        _tablePatchPackTypeName = knownTypes.TablePatchPackTypeName;
    }

    public ResolvedMemberSet ApplyMemoryPackAdjustments(
        TypeDefinition type,
        string safeTypeName,
        string? declaringType,
        ResolvedMemberSet members)
    {
        var relationships = members.Relationships;
        var fields = members.Fields;
        var properties = members.Properties;
        var events = members.Events;
        var methods = members.Methods;
        var methodNames = methods.Select(method => method.DisplayName).ToHashSet(StringComparer.Ordinal);
        var hasSerialize = methodNames.Contains("Serialize");
        var hasDeserialize = methodNames.Contains("Deserialize");
        var hasRegisterFormatter = methodNames.Contains("RegisterFormatter");
        var isMemoryPackFormatterType = !string.IsNullOrWhiteSpace(declaringType) &&
                                        type.Name.EndsWith("Formatter", StringComparison.Ordinal) &&
                                        hasSerialize &&
                                        hasDeserialize;
        var isMemoryPackableType = TypeKind(type) is "class" or "struct" &&
                                   hasSerialize &&
                                   hasDeserialize &&
                                   hasRegisterFormatter;

        if (!isMemoryPackFormatterType &&
            !isMemoryPackableType &&
            type.FullName is not "TableBundle" and not "TablePatchPack" and not "TableCatalog" and not "Media.Service.Media" and not "Media.Service.MediaCatalog" and not "MX.Logic.Data.TagConstraint")
        {
            return members;
        }

        string? serializerTargetType = isMemoryPackFormatterType
            ? declaringType
            : !string.IsNullOrWhiteSpace(type.Namespace)
                ? $"{type.Namespace}.{safeTypeName}"
                : safeTypeName;

        if (isMemoryPackableType)
        {
            var memoryPackableInterface = BuildClosedGenericType(_memoryPackableTypeName, serializerTargetType);
            if (!string.IsNullOrWhiteSpace(memoryPackableInterface) &&
                !relationships.Interfaces.Contains(memoryPackableInterface, StringComparer.Ordinal))
            {
                relationships = new TypeRelationships(
                    relationships.BaseType,
                    [memoryPackableInterface!, .. relationships.Interfaces],
                    relationships.Comments);
            }
        }

        if (isMemoryPackFormatterType)
        {
            var formatterBase = BuildClosedGenericType(_memoryPackFormatterTypeName, serializerTargetType);
            if (!string.IsNullOrWhiteSpace(formatterBase) &&
                IsWeakMemoryPackType(relationships.BaseType))
            {
                relationships = new TypeRelationships(
                    formatterBase,
                    relationships.Interfaces,
                    relationships.Comments);
            }
        }

        var stringListType = BuildListType("System.String");
        var patchFileInfoEnumerableType = BuildEnumerableType(_patchFileInfoTypeName);
        var tableBundleArrayType = BuildArrayType(_tableBundleTypeName);
        var tableDictionaryType = BuildDictionaryType("System.String", _tableBundleTypeName);
        var tablePackDictionaryType = BuildDictionaryType("System.String", _tablePatchPackTypeName);
        var tableBundleEnumerableType = BuildEnumerableType(_tableBundleTypeName);
        var mediaDictionaryType = BuildDictionaryType("System.String", _mediaTypeName);
        var mediaEnumerableType = BuildEnumerableType(_mediaTypeName);
        var tagListType = BuildListType(_flatDataTagTypeName);

        string? DesiredMemoryPackFieldType(string identifier) => type.FullName switch
        {
            "TableBundle" => identifier switch
            {
                "<Size>k__BackingField" or "_Size_k__BackingField" => "System.Int64",
                "<Crc>k__BackingField" or "_Crc_k__BackingField" => "System.Int64",
                "<Includes>k__BackingField" or "_Includes_k__BackingField" => stringListType,
                _ => null,
            },
            "TablePatchPack" => identifier switch
            {
                "<Size>k__BackingField" or "_Size_k__BackingField" => "System.Int64",
                "<Crc>k__BackingField" or "_Crc_k__BackingField" => "System.Int64",
                "<BundleFiles>k__BackingField" or "_BundleFiles_k__BackingField" => tableBundleArrayType,
                _ => null,
            },
            "TableCatalog" => identifier switch
            {
                "<Table>k__BackingField" or "_Table_k__BackingField" => tableDictionaryType,
                "<TablePack>k__BackingField" or "_TablePack_k__BackingField" => tablePackDictionaryType,
                _ => null,
            },
            "Media.Service.Media" => identifier switch
            {
                "<Bytes>k__BackingField" or "_Bytes_k__BackingField" => "System.Int64",
                "<Crc>k__BackingField" or "_Crc_k__BackingField" => "System.Int64",
                "<IsPrologue>k__BackingField" or "_IsPrologue_k__BackingField" => "System.Boolean",
                "<IsSplitDownload>k__BackingField" or "_IsSplitDownload_k__BackingField" => "System.Boolean",
                "filePath" or "fileURI" or "hashFilePath" or "persistentPath" or "preinPath" or "uriPath" => "System.String",
                "fileNameHash" => "System.UInt64",
                _ => null,
            },
            "Media.Service.MediaCatalog" => identifier switch
            {
                "<Table>k__BackingField" or "_Table_k__BackingField" => mediaDictionaryType,
                _ => null,
            },
            "MX.Logic.Data.TagConstraint" => identifier switch
            {
                "Empty" => type.FullName,
                "tagNameList" or "TagNamesInt" => tagListType,
                _ => null,
            },
            _ => null,
        };

        string? DesiredMemoryPackPropertyType(string identifier) => type.FullName switch
        {
            "TableBundle" => identifier switch
            {
                "Size" or "Crc" => "System.Int64",
                "Includes" => stringListType,
                _ => null,
            },
            "TablePatchPack" => identifier switch
            {
                "Size" or "Crc" => "System.Int64",
                "BundleFiles" => tableBundleArrayType,
                _ => null,
            },
            "TableCatalog" => identifier switch
            {
                "Table" => tableDictionaryType,
                "TablePack" => tablePackDictionaryType,
                _ => null,
            },
            "Media.Service.Media" => identifier switch
            {
                "Bytes" or "Crc" => "System.Int64",
                "IsPrologue" or "IsSplitDownload" => "System.Boolean",
                _ => null,
            },
            "Media.Service.MediaCatalog" => identifier switch
            {
                "Table" => mediaDictionaryType,
                _ => null,
            },
            "MX.Logic.Data.TagConstraint" => identifier switch
            {
                "TagNameList" => tagListType,
                _ => null,
            },
            _ => null,
        };

        var adjustedFields = fields.Select(field =>
        {
            var desiredType = DesiredMemoryPackFieldType(field.Identifier);
            if (desiredType is null)
                return field;

            var adjustedField = field with
            {
                TypeName = type.FullName is "TableBundle" or "TablePatchPack" or "TableCatalog" or "Media.Service.Media" or "Media.Service.MediaCatalog" or "MX.Logic.Data.TagConstraint"
                    ? desiredType
                    : PreferMemoryPackType(field.TypeName, desiredType),
            };

            if (type.FullName == "MX.Logic.Data.TagConstraint" && field.Identifier == "Empty")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "static", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            return adjustedField;
        }).ToArray();

        var adjustedProperties = properties.Select(property =>
        {
            var desiredType = DesiredMemoryPackPropertyType(property.DisplayName);
            return desiredType is null
                ? property
                : property with
                {
                    TypeName = type.FullName is "TableBundle" or "TablePatchPack" or "TableCatalog" or "Media.Service.Media" or "Media.Service.MediaCatalog" or "MX.Logic.Data.TagConstraint"
                        ? desiredType
                        : PreferMemoryPackType(property.TypeName, desiredType),
                };
        }).ToArray();

        var adjustedMethods = methods.Select(method =>
        {
            string? desiredReturnType = null;
            if (type.FullName == "TableCatalog" && method.DisplayName == "Diff")
                desiredReturnType = tableBundleEnumerableType;
            else if (type.FullName == "Media.Service.MediaCatalog" && method.DisplayName == "Diff")
                desiredReturnType = mediaEnumerableType;
            else if (type.FullName == "MX.Logic.Data.TagConstraint")
            {
                var propertyAccessorTarget = method.DisplayName.StartsWith("get_", StringComparison.Ordinal)
                    ? DesiredMemoryPackPropertyType(method.DisplayName[4..])
                    : method.DisplayName.StartsWith("set_", StringComparison.Ordinal)
                        ? DesiredMemoryPackPropertyType(method.DisplayName[4..])
                        : null;

                if (method.DisplayName.StartsWith("get_", StringComparison.Ordinal) && propertyAccessorTarget is not null)
                    desiredReturnType = propertyAccessorTarget;
                else if (method.DisplayName == "<get_TagNameList>g__GetTagNameList|2_0")
                    desiredReturnType = tagListType;
            }
            else if (type.FullName is "TableBundle" or "TablePatchPack" or "TableCatalog")
            {
                var propertyAccessorTarget = method.DisplayName.StartsWith("get_", StringComparison.Ordinal)
                    ? DesiredMemoryPackPropertyType(method.DisplayName[4..])
                    : method.DisplayName.StartsWith("set_", StringComparison.Ordinal)
                        ? DesiredMemoryPackPropertyType(method.DisplayName[4..])
                        : null;

                if (method.DisplayName.StartsWith("get_", StringComparison.Ordinal) && propertyAccessorTarget is not null)
                    desiredReturnType = propertyAccessorTarget;
            }
            else if (type.FullName is "Media.Service.Media" or "Media.Service.MediaCatalog")
            {
                var propertyAccessorTarget = method.DisplayName.StartsWith("get_", StringComparison.Ordinal)
                    ? DesiredMemoryPackPropertyType(method.DisplayName[4..])
                    : method.DisplayName.StartsWith("set_", StringComparison.Ordinal)
                        ? DesiredMemoryPackPropertyType(method.DisplayName[4..])
                        : null;

                if (method.DisplayName.StartsWith("get_", StringComparison.Ordinal) && propertyAccessorTarget is not null)
                    desiredReturnType = propertyAccessorTarget;
            }

            var adjustedParameters = method.Parameters.Select((parameter, index) =>
            {
                string? desiredType = null;

                if (method.DisplayName == "Serialize")
                {
                    if (index == 0)
                        desiredType = _memoryPackWriterTypeName;
                    else if (parameter.Identifier == "value")
                        desiredType = serializerTargetType;
                }
                else if (method.DisplayName == "Deserialize")
                {
                    if (index == 0)
                        desiredType = _memoryPackReaderTypeName;
                    else if (parameter.Identifier == "value")
                        desiredType = serializerTargetType;
                }
                else
                {
                    desiredType = type.FullName switch
                    {
                        "TableBundle" when method.DisplayName == "IsAnyOf" && parameter.Identifier == "files" => patchFileInfoEnumerableType,
                        "TableBundle" when method.DisplayName == "IsMatch" && parameter.Identifier == "bundleFile" => _patchFileInfoTypeName,
                        "TableCatalog" when method.DisplayName == "Diff" && parameter.Identifier == "other" => _tableCatalogTypeName,
                        "Media.Service.MediaCatalog" when method.DisplayName == "Diff" && parameter.Identifier == "other" => _mediaCatalogTypeName,
                        "Media.Service.MediaCatalog" when method.DisplayName == "TryGet" && parameter.Identifier == "media" => _mediaTypeName,
                        "MX.Logic.Data.TagConstraint" when method.DisplayName == "IsMatch" && parameter.Identifier == "tagNameList" => tagListType,
                        _ => null,
                    };

                    if (desiredType is null &&
                        type.FullName is "TableBundle" or "TablePatchPack" or "TableCatalog" or "Media.Service.Media" or "Media.Service.MediaCatalog" or "MX.Logic.Data.TagConstraint" &&
                        method.DisplayName.StartsWith("set_", StringComparison.Ordinal) &&
                        parameter.Identifier == "value")
                    {
                        desiredType = DesiredMemoryPackPropertyType(method.DisplayName[4..]);
                    }
                }

                return desiredType is null
                    ? parameter
                    : parameter with
                    {
                        TypeName = type.FullName is "TableBundle" or "TablePatchPack" or "TableCatalog" or "Media.Service.Media" or "Media.Service.MediaCatalog" or "MX.Logic.Data.TagConstraint"
                            ? desiredType
                            : PreferMemoryPackType(parameter.TypeName, desiredType),
                        ModifierPrefix = type.FullName == "Media.Service.MediaCatalog" && method.DisplayName == "TryGet" && parameter.Identifier == "media"
                            ? "out"
                            : parameter.ModifierPrefix,
                    };
            }).ToArray();

            return method with
            {
                ReturnTypeName = desiredReturnType is null
                    ? method.ReturnTypeName
                    : type.FullName is "TableBundle" or "TablePatchPack" or "TableCatalog" or "Media.Service.Media" or "Media.Service.MediaCatalog" or "MX.Logic.Data.TagConstraint"
                        ? desiredReturnType
                        : PreferMemoryPackType(method.ReturnTypeName, desiredReturnType),
                Parameters = adjustedParameters,
            };
        }).ToArray();

        return new ResolvedMemberSet(relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }


    private static bool IsWeakMemoryPackType(string? typeName)
        => string.IsNullOrWhiteSpace(typeName) ||
           typeName!.StartsWith("Type_0x", StringComparison.Ordinal) ||
           string.Equals(typeName, "object", StringComparison.Ordinal) ||
           string.Equals(typeName, "int", StringComparison.Ordinal) ||
           string.Equals(typeName, "long", StringComparison.Ordinal) ||
           string.Equals(typeName, "float", StringComparison.Ordinal) ||
           string.Equals(typeName, "bool", StringComparison.Ordinal) ||
           string.Equals(typeName, "System.Object", StringComparison.Ordinal) ||
           string.Equals(typeName, "System.Int32", StringComparison.Ordinal) ||
           string.Equals(typeName, "System.Int64", StringComparison.Ordinal) ||
           string.Equals(typeName, "System.Single", StringComparison.Ordinal) ||
           string.Equals(typeName, "System.Boolean", StringComparison.Ordinal) ||
           string.Equals(typeName, "MemoryPack.Internal.ReusableLinkedArrayBufferWriter", StringComparison.Ordinal) ||
           string.Equals(typeName, "MemoryPack.Internal.ReusableLinkedArrayBufferWriter<byte>", StringComparison.Ordinal);

    private static string PreferMemoryPackType(string currentType, string desiredType)
        => IsWeakMemoryPackType(currentType) ? desiredType : currentType;
}
