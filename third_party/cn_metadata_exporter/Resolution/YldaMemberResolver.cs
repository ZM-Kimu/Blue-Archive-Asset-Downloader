namespace YldaDumpCsExporter;

internal sealed class YldaMemberResolver
{
    private readonly MetadataModel _model;
    private readonly YldaTypeResolver _typeResolver;
    private readonly YldaRelationshipResolver _relationshipResolver;
    private readonly TypeDescriptorIndex _descriptors;
    private readonly string? _futureInterfaceTypeName;
    private readonly string? _futureValueCallbackTypeName;
    private readonly string? _futureCallbackTypeName;
    private readonly string? _futureErrorCallbackTypeName;
    private readonly string? _hubConnectionTypeName;
    private readonly string? _campaignStageHistoryDbTypeName;
    private readonly string? _campaignStageInfoTypeName;
    private readonly string? _fieldContentStageInfoTypeName;
    private readonly string? _uiFieldLobbyTypeName;
    private readonly string? _fieldDateHistoryDbTypeName;
    private readonly string? _fieldInteractionDbTypeName;
    private readonly string? _fieldQuestDbTypeName;
    private readonly string? _fieldSnapshotTypeName;
    private readonly string? _fieldCharacterDbTypeName;
    private readonly string? _fieldMasteryDbTypeName;
    private readonly string? _fieldSeasonInfoTypeName;
    private readonly string? _fieldSceneInfoTypeName;
    private readonly string? _fieldQuestInfoTypeName;
    private readonly string? _gameCharacterDbTypeName;
    private readonly string? _iPreloadRequiredTypeName;
    private readonly string? _intStringPairTypeName;
    private readonly string? _parcelInfoTypeName;
    private readonly string? _parcelResultDbTypeName;
    private readonly string? _fieldRewardInfoTypeName;
    private readonly string? _fieldInteractionInfoTypeName;
    private readonly string? _fieldSaveSoTypeName;
    private readonly string? _fieldSaveRepositoryTypeName;
    private readonly string? _fieldInteractionRequestTypeName;
    private readonly string? _fieldInteractionResponseTypeName;
    private readonly string? _fieldDateInfoTypeName;
    private readonly string? _eventContentSeasonInfoTypeName;
    private readonly string? _mxContentBridgeTypeName;
    private readonly string? _fieldGameManagerDisplayClass82TypeName;
    private readonly string? _equatableTypeName;
    private readonly string? _memoryPackableTypeName;
    private readonly string? _memoryPackFormatterTypeName;
    private readonly string? _memoryPackWriterTypeName;
    private readonly string? _memoryPackReaderTypeName;
    private readonly string? _tableBundleTypeName;
    private readonly string? _tablePatchPackTypeName;
    private readonly string? _tableCatalogTypeName;
    private readonly string? _flatDataTagTypeName;
    private readonly string? _patchFileInfoTypeName;
    private readonly string? _mediaTypeName;
    private readonly string? _mediaCatalogTypeName;
    private readonly string? _skillAbilityModifierDaoTypeName;
    private readonly string? _unityVector2TypeName;
    private readonly string? _unityVector3TypeName;
    private readonly string? _groundObstacleDataTypeName;

    public YldaMemberResolver(
        MetadataModel model,
        YldaTypeResolver typeResolver,
        YldaRelationshipResolver relationshipResolver,
        TypeDescriptorIndex descriptors)
    {
        _model = model;
        _typeResolver = typeResolver;
        _relationshipResolver = relationshipResolver;
        _descriptors = descriptors;
        _futureInterfaceTypeName = TryFindTypeFullName("IFuture`1");
        _futureValueCallbackTypeName = TryFindTypeFullName("FutureValueCallback`1");
        _futureCallbackTypeName = TryFindTypeFullName("FutureCallback`1");
        _futureErrorCallbackTypeName = TryFindTypeFullName("FutureErrorCallback");
        _hubConnectionTypeName = TryFindTypeFullName("HubConnection");
        _campaignStageHistoryDbTypeName = TryFindTypeFullName("CampaignStageHistoryDB");
        _campaignStageInfoTypeName = TryFindTypeFullName("CampaignStageInfo");
        _fieldContentStageInfoTypeName = TryFindTypeFullName("FieldContentStageInfo");
        _uiFieldLobbyTypeName = TryFindTypeFullName("UIFieldLobby");
        _fieldDateHistoryDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldDateHistoryDB");
        _fieldInteractionDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldInteractionDB");
        _fieldQuestDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldQuestDB");
        _fieldSnapshotTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldSnapshot");
        _fieldCharacterDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldCharacterDB");
        _fieldMasteryDbTypeName = TryFindExactTypeFullName("MXField.Shared.Model.FieldMasteryDB");
        _fieldSeasonInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldSeasonInfo");
        _fieldSceneInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldSceneInfo");
        _fieldQuestInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldQuestInfo");
        _gameCharacterDbTypeName = TryFindExactTypeFullName("MX.GameLogic.DBModel.CharacterDB");
        _iPreloadRequiredTypeName = TryFindExactTypeFullName("MXField.Core.IPreloadRequired");
        _intStringPairTypeName = TryFindExactTypeFullName("MXField.LUT.IntStringPair");
        _parcelInfoTypeName = TryFindExactTypeFullName("MX.GameLogic.Parcel.ParcelInfo");
        _parcelResultDbTypeName = TryFindExactTypeFullName("MX.GameLogic.Parcel.ParcelResultDB");
        _fieldRewardInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldRewardInfo");
        _fieldInteractionInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldInteractionInfo");
        _fieldSaveSoTypeName = TryFindExactTypeFullName("MXField.Core.Save.FieldSaveSO");
        _fieldSaveRepositoryTypeName = TryFindExactTypeFullName("MXField.Core.Save.FieldSaveRepository");
        _fieldInteractionRequestTypeName = TryFindExactTypeFullName("MXField.Shared.NetworkProtocol.FieldInteractionRequest");
        _fieldInteractionResponseTypeName = TryFindExactTypeFullName("MXField.Shared.NetworkProtocol.FieldInteractionResponse");
        _fieldDateInfoTypeName = TryFindExactTypeFullName("MXField.Shared.Data.FieldDateInfo");
        _eventContentSeasonInfoTypeName = TryFindExactTypeFullName("MX.Data.EventContentSeasonInfo");
        _mxContentBridgeTypeName = TryFindTypeFullName("MXContentBridge");
        _fieldGameManagerDisplayClass82TypeName = TryFindNestedTypeReference("MXField.FieldGameManager", "<>c__DisplayClass82_0");
        _equatableTypeName = TryFindExactTypeFullName("System.IEquatable`1");
        _memoryPackableTypeName = TryFindExactTypeFullName("MemoryPack.IMemoryPackable`1");
        _memoryPackFormatterTypeName = TryFindExactTypeFullName("MemoryPack.MemoryPackFormatter`1");
        _memoryPackWriterTypeName = TryFindExactTypeFullName("MemoryPack.MemoryPackWriter");
        _memoryPackReaderTypeName = TryFindExactTypeFullName("MemoryPack.MemoryPackReader");
        _tableBundleTypeName = TryFindExactTypeFullName("TableBundle");
        _tablePatchPackTypeName = TryFindExactTypeFullName("TablePatchPack");
        _tableCatalogTypeName = TryFindExactTypeFullName("TableCatalog");
        _flatDataTagTypeName = TryFindExactTypeFullName("FlatData.Tag");
        _patchFileInfoTypeName = TryFindExactTypeFullName("MX.AssetBundles.PatchFileInfo");
        _mediaTypeName = TryFindExactTypeFullName("Media.Service.Media");
        _mediaCatalogTypeName = TryFindExactTypeFullName("Media.Service.MediaCatalog");
        _skillAbilityModifierDaoTypeName = TryFindExactTypeFullName("MX.GameData.DAO.Battle.SkillAbilityModifierDAO");
        _unityVector2TypeName = TryFindExactTypeFullName("UnityEngine.Vector2");
        _unityVector3TypeName = TryFindExactTypeFullName("UnityEngine.Vector3");
        _groundObstacleDataTypeName = TryFindExactTypeFullName("MX.Data.GroundObstacleData");
    }

    public ResolvedTypeModel ResolveType(TypeDefinition type)
    {
        var methodRows = GetTypeMethods(type);
        var fieldRows = GetTypeFields(type);
        var propertyRows = GetTypeProperties(type);
        var eventRows = GetTypeEvents(type);
        var typeNameMap = _typeResolver.CreateTypeNameMap(type, methodRows, fieldRows);
        var relationships = _relationshipResolver.ResolveTypeRelationships(type, methodRows, typeNameMap);
        var declaringType = _relationshipResolver.ResolveDeclaringType(type, typeNameMap);
        return ResolveType(type, typeNameMap, new RelationshipIndexEntry(
            type.Index,
            declaringType,
            relationships.BaseType,
            relationships.Interfaces.ToArray(),
            relationships.Comments.ToArray()));
    }

    public ResolvedTypeModel ResolveType(
        TypeDefinition type,
        IReadOnlyDictionary<uint, string> typeNameMap,
        RelationshipIndexEntry relationshipEntry)
    {
        var methodRows = GetTypeMethods(type);
        var fieldRows = GetTypeFields(type);
        var propertyRows = GetTypeProperties(type);
        var eventRows = GetTypeEvents(type);
        var declaringType = relationshipEntry.DeclaringType;
        var genericParameterNames = ResolveTypeGenericParameterNames(type);
        var relationships = new TypeRelationships(
            ApplyGenericContext(relationshipEntry.BaseType, genericParameterNames),
            relationshipEntry.Interfaces.Select(interfaceName => ApplyGenericContext(interfaceName, genericParameterNames) ?? interfaceName).ToArray(),
            relationshipEntry.Comments);
        var propertyTypeByName = BuildPropertyTypeByName(type, propertyRows, typeNameMap);

        var safeTypeName = FormatTypeDisplayName(type, genericParameterNames);
        var originalTypeName = string.Equals(safeTypeName, type.Name, StringComparison.Ordinal) ? null : type.Name;

        IReadOnlyList<ResolvedFieldModel> fields = ResolveFields(type, fieldRows, methodRows, propertyTypeByName, typeNameMap, declaringType)
            .Select(field => field with { TypeName = ApplyGenericContext(field.TypeName, genericParameterNames) ?? field.TypeName })
            .ToArray();
        IReadOnlyList<ResolvedPropertyModel> properties = ResolveProperties(type, propertyRows, methodRows, typeNameMap)
            .Select(property => property with { TypeName = ApplyGenericContext(property.TypeName, genericParameterNames) ?? property.TypeName })
            .ToArray();
        IReadOnlyList<ResolvedEventModel> events = ResolveEvents(type, eventRows, methodRows, typeNameMap)
            .Select(evt => evt with { TypeName = ApplyGenericContext(evt.TypeName, genericParameterNames) ?? evt.TypeName })
            .ToArray();
        IReadOnlyList<ResolvedMethodModel> methods = ResolveMethods(type, methodRows, typeNameMap)
            .Select(method => method with
            {
                ReturnTypeName = ApplyGenericContext(method.ReturnTypeName, genericParameterNames) ?? method.ReturnTypeName,
                Parameters = method.Parameters.Select(parameter => parameter with
                {
                    TypeName = ApplyGenericContext(parameter.TypeName, genericParameterNames) ?? parameter.TypeName,
                }).ToArray(),
            })
            .ToArray();

        (relationships, fields, properties, events, methods) = ApplyFutureLikeAdjustments(
            type,
            methodRows,
            genericParameterNames,
            relationships,
            fields,
            properties,
            events,
            methods);

        (relationships, fields, properties, events, methods) = ApplyMxFieldFamilyAdjustments(
            type,
            relationships,
            fields,
            properties,
            events,
            methods);

        (relationships, fields, properties, events, methods) = ApplyFlatBufferTableAdjustments(
            type,
            relationships,
            fields,
            properties,
            events,
            methods);

        (relationships, fields, properties, events, methods) = ApplyMemoryPackAdjustments(
            type,
            safeTypeName,
            declaringType,
            relationships,
            fields,
            properties,
            events,
            methods);

        (relationships, fields, properties, events, methods) = ApplyFieldBridgeAdjustments(
            type,
            declaringType,
            relationships,
            fields,
            properties,
            events,
            methods);

        (relationships, fields, properties, events, methods) = ApplyReferenceModelAdjustments(
            type,
            safeTypeName,
            declaringType,
            relationships,
            fields,
            properties,
            events,
            methods);

        return new ResolvedTypeModel(
            type,
            ImageForType(type.Index),
            string.IsNullOrEmpty(type.Namespace) ? "<global>" : type.Namespace,
            safeTypeName,
            originalTypeName,
            genericParameterNames,
            _relationshipResolver.ResolveTypeModifiers(type),
            declaringType,
            relationships,
            fields,
            properties,
            events,
            methods);
    }

    private IReadOnlyList<ResolvedFieldModel> ResolveFields(
        TypeDefinition type,
        IReadOnlyList<FieldDefinition> rows,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<string, string> propertyTypeByName,
        IReadOnlyDictionary<uint, string> typeNameMap,
        string? declaringTypeName)
    {
        var resolved = new List<ResolvedFieldModel>(rows.Count);
        var isEnum = IsEnumType(type);
        foreach (var field in rows)
        {
            string? inferredType = null;
            var backingName = YldaResolutionUtilities.BackingFieldPropertyName(field.Name);
            if (backingName is not null && propertyTypeByName.TryGetValue(backingName, out var propertyType))
                inferredType = propertyType;
            else if (YldaResolutionUtilities.ConventionalPropertyCandidate(field.Name) is { } conventionalName &&
                     propertyTypeByName.TryGetValue(conventionalName, out propertyType))
            {
                inferredType = propertyType;
            }
            else if (field.Name == "__p" &&
                     methodRows.Any(method => method.Name == "get_ByteBuffer") &&
                     methodRows.Any(method => method.Name == "__assign"))
            {
                inferredType = "FlatBuffers.Table";
            }
            else if (field.Name == "TableKey" && methodRows.Any(method => method.Name == "InitKey"))
            {
                inferredType = "byte[]";
            }
            else if (!string.IsNullOrWhiteSpace(declaringTypeName) && (field.Name == "<>4__this" || field.Name == "__4__this"))
            {
                inferredType = declaringTypeName;
            }

            var resolvedTypeName = isEnum
                ? ResolveEnumFieldTypeName(type, field, methodRows, typeNameMap)
                : _typeResolver.ResolveContextualTypeName(type, field.Name, field.TypeIndex, methodRows, typeNameMap, inferredType);

            var modifiers = isEnum
                ? ResolveEnumFieldModifiers(field)
                : ResolveFieldModifiers(field);

            var accessibility = isEnum
                ? ExportMemberAccessibility.Public
                : ResolveFieldAccessibility(field);

            resolved.Add(new ResolvedFieldModel(
                field,
                YldaResolutionUtilities.SanitizeIdentifier(field.Name, $"field_{field.Index}"),
                resolvedTypeName,
                modifiers,
                accessibility));
        }

        return resolved;
    }

    private IReadOnlyList<ResolvedPropertyModel> ResolveProperties(
        TypeDefinition type,
        IReadOnlyList<PropertyDefinition> rows,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var resolved = new List<ResolvedPropertyModel>(rows.Count);
        foreach (var property in rows)
        {
            var accessors = new List<string>();
            var propertyType = ResolvePropertyType(type, property, methodRows, typeNameMap);
            bool? confirmedOverride = null;

            if (property.GetterDelta != uint.MaxValue)
            {
                var getter = _model.Methods[type.FirstMethodIndex + (int)property.GetterDelta];
                accessors.Add("get;");
                confirmedOverride = MergeOverrideEvidence(confirmedOverride, _relationshipResolver.ResolveOverride(type, getter, typeNameMap));
            }

            if (property.SetterDelta != uint.MaxValue)
            {
                var setter = _model.Methods[type.FirstMethodIndex + (int)property.SetterDelta];
                accessors.Add("set;");
                confirmedOverride = MergeOverrideEvidence(confirmedOverride, _relationshipResolver.ResolveOverride(type, setter, typeNameMap));
            }

            resolved.Add(new ResolvedPropertyModel(
                property,
                property.Name,
                propertyType,
                _relationshipResolver.ResolvePropertyModifiers(type, property, confirmedOverride),
                _relationshipResolver.ResolvePropertyAccessibility(type, property),
                accessors));
        }

        return resolved;
    }

    private IReadOnlyList<ResolvedEventModel> ResolveEvents(
        TypeDefinition type,
        IReadOnlyList<EventDefinition> rows,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var resolved = new List<ResolvedEventModel>(rows.Count);
        foreach (var evt in rows)
        {
            bool? confirmedOverride = null;
            if (evt.AddDelta != uint.MaxValue)
                confirmedOverride = MergeOverrideEvidence(confirmedOverride, _relationshipResolver.ResolveOverride(type, _model.Methods[type.FirstMethodIndex + (int)evt.AddDelta], typeNameMap));
            if (evt.RemoveDelta != uint.MaxValue)
                confirmedOverride = MergeOverrideEvidence(confirmedOverride, _relationshipResolver.ResolveOverride(type, _model.Methods[type.FirstMethodIndex + (int)evt.RemoveDelta], typeNameMap));
            if (evt.RaiseDelta != uint.MaxValue)
                confirmedOverride = MergeOverrideEvidence(confirmedOverride, _relationshipResolver.ResolveOverride(type, _model.Methods[type.FirstMethodIndex + (int)evt.RaiseDelta], typeNameMap));

            resolved.Add(new ResolvedEventModel(
                evt,
                evt.Name,
                _typeResolver.ResolveContextualTypeName(type, evt.Name, evt.TypeIndex, methodRows, typeNameMap),
                _relationshipResolver.ResolveEventModifiers(type, evt, confirmedOverride),
                _relationshipResolver.ResolveEventAccessibility(type, evt)));
        }

        return resolved;
    }

    private IReadOnlyList<ResolvedMethodModel> ResolveMethods(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> rows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var resolved = new List<ResolvedMethodModel>(rows.Count);
        foreach (var method in rows)
        {
            var parameters = _descriptors.GetParameters(method)
                .Select((parameter, index) => new ResolvedParameterModel(
                    parameter,
                    YldaResolutionUtilities.SanitizeIdentifier(parameter.Name, $"param_{index}"),
                    ResolveParameterType(type, method, parameter, rows, typeNameMap)))
                .ToArray();

            resolved.Add(new ResolvedMethodModel(
                method,
                method.Name,
                ResolveMethodReturnType(type, method, rows, typeNameMap),
                _relationshipResolver.ResolveMethodModifiers(method, _relationshipResolver.ResolveOverride(type, method, typeNameMap)),
                _relationshipResolver.ResolveMethodAccessibility(method),
                parameters));
        }

        return resolved;
    }

    private IReadOnlyDictionary<string, string> BuildPropertyTypeByName(
        TypeDefinition type,
        IReadOnlyList<PropertyDefinition> properties,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var propertyTypeByName = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var methodRows = GetTypeMethods(type);
        var propertyTypeIndexByName = _descriptors.GetPropertyTypeIndices(type);
        foreach (var property in properties)
        {
            var propertyType = ResolvePropertyType(type, property, methodRows, typeNameMap, propertyTypeIndexByName);

            if (!string.IsNullOrWhiteSpace(propertyType))
                propertyTypeByName[property.Name] = propertyType;
        }

        return propertyTypeByName;
    }

    private string ResolvePropertyType(
        TypeDefinition type,
        PropertyDefinition property,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap,
        IReadOnlyDictionary<string, uint>? propertyTypeIndexByName = null)
    {
        propertyTypeIndexByName ??= _descriptors.GetPropertyTypeIndices(type);
        if (propertyTypeIndexByName.TryGetValue(property.Name, out var propertyTypeIndex))
            return _typeResolver.ResolveContextualTypeName(type, property.Name, propertyTypeIndex, methodRows, typeNameMap);

        return "Type_Unknown";
    }

    private string ResolveMethodReturnType(
        TypeDefinition type,
        MethodDefinition method,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var memberName = method.Name.StartsWith("get_", StringComparison.Ordinal) ||
                         method.Name.StartsWith("set_", StringComparison.Ordinal) ||
                         method.Name.StartsWith("add_", StringComparison.Ordinal) ||
                         method.Name.StartsWith("remove_", StringComparison.Ordinal)
            ? method.Name[(method.Name.IndexOf('_') + 1)..]
            : method.Name;

        return _typeResolver.ResolveContextualTypeName(type, memberName, method.ReturnTypeIndex, methodRows, typeNameMap);
    }

    private string ResolveParameterType(
        TypeDefinition type,
        MethodDefinition method,
        ParameterDefinition parameter,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        return _typeResolver.ResolveContextualTypeName(type, parameter.Name, parameter.TypeIndex, methodRows, typeNameMap);
    }

    private string ImageForType(int typeIndex)
        => typeIndex >= 0 && typeIndex < _model.Types.Count
            ? _descriptors.GetImageName(_model.Types[typeIndex])
            : "unknown";

    private MethodDefinition[] GetTypeMethods(TypeDefinition type) => _descriptors.GetMethods(type);
    private FieldDefinition[] GetTypeFields(TypeDefinition type) => _descriptors.GetFields(type);
    private PropertyDefinition[] GetTypeProperties(TypeDefinition type) => _descriptors.GetProperties(type);
    private EventDefinition[] GetTypeEvents(TypeDefinition type) => _descriptors.GetEvents(type);

    private static bool? MergeOverrideEvidence(bool? current, bool? next)
    {
        if (next == true)
            return true;
        return current ?? next;
    }

    private static ExportMemberAccessibility ResolveFieldAccessibility(FieldDefinition field)
    {
        if (field.Name == "value__")
            return ExportMemberAccessibility.Public;

        if (YldaResolutionUtilities.BackingFieldPropertyName(field.Name) is not null ||
            field.Name.Contains("i__Field", StringComparison.Ordinal) ||
            field.Name.StartsWith('<') ||
            field.Name.StartsWith('_') ||
            field.Name.StartsWith("__", StringComparison.Ordinal) ||
            (field.Name.Length > 1 && field.Name[0] == 'm' && char.IsUpper(field.Name[1])))
        {
            return ExportMemberAccessibility.Private;
        }

        return ExportMemberAccessibility.Unknown;
    }

    private static IReadOnlyList<string> ResolveFieldModifiers(FieldDefinition field)
    {
        var accessibility = ResolveFieldAccessibility(field);
        var modifier = YldaResolutionUtilities.AccessibilityModifier(accessibility);
        return string.IsNullOrEmpty(modifier) ? [] : [modifier];
    }

    private static bool IsEnumType(TypeDefinition type) => (type.Bitfield & 0x2) != 0;

    private string ResolveEnumFieldTypeName(
        TypeDefinition type,
        FieldDefinition field,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (field.Name == "value__")
        {
            var underlyingType = _typeResolver.ResolveContextualTypeName(type, field.Name, field.TypeIndex, methodRows, typeNameMap, null);
            return YldaResolutionConstants.AliasToSystemType.GetValueOrDefault(underlyingType, underlyingType);
        }

        return type.FullName;
    }

    private static IReadOnlyList<string> ResolveEnumFieldModifiers(FieldDefinition field)
    {
        if (field.Name == "value__")
            return ["public"];

        return ["public", "static", "const"];
    }

    private string[] ResolveTypeGenericParameterNames(TypeDefinition type)
    {
        GenericContainerEntry? container = null;
        foreach (var candidate in _model.GenericContainers)
        {
            if (candidate.IsMethod == 0 && candidate.OwnerIndex == (uint)type.Index)
            {
                container = candidate;
                break;
            }
        }

        if (container is not { TypeArgumentCount: > 0 })
            return [];

        var names = new List<string>((int)container.Value.TypeArgumentCount);
        for (var i = 0; i < container.Value.TypeArgumentCount; i++)
        {
            var parameterIndex = checked((int)(container.Value.GenericParameterStart + i));
            if (parameterIndex >= 0 && parameterIndex < _model.GenericParameters.Count)
            {
                var parameter = _model.GenericParameters[parameterIndex];
                var safeName = YldaResolutionUtilities.SanitizeIdentifier(parameter.Name, $"T{i}");
                names.Add(string.IsNullOrWhiteSpace(safeName) ? $"T{i}" : safeName);
            }
            else
            {
                names.Add($"T{i}");
            }
        }

        return names.ToArray();
    }

    private static string FormatTypeDisplayName(TypeDefinition type, IReadOnlyList<string> genericParameterNames)
    {
        var safeBaseName = YldaResolutionUtilities.SanitizeIdentifier(RemoveGenericAritySuffix(type.Name), $"type_{type.Index}");
        if (genericParameterNames.Count == 0)
            return safeBaseName;

        return $"{safeBaseName}<{string.Join(", ", genericParameterNames)}>";
    }

    private static string? ApplyGenericContext(string? typeName, IReadOnlyList<string> genericParameterNames)
    {
        if (string.IsNullOrWhiteSpace(typeName) || genericParameterNames.Count == 0)
            return typeName;
        if (typeName!.Contains('<', StringComparison.Ordinal))
            return typeName;

        var tickIndex = typeName.LastIndexOf('`');
        if (tickIndex <= 0 || tickIndex == typeName.Length - 1)
            return typeName;

        if (!int.TryParse(typeName[(tickIndex + 1)..], out var arity))
            return typeName;
        if (arity != genericParameterNames.Count)
            return typeName;

        return $"{typeName[..tickIndex]}<{string.Join(", ", genericParameterNames)}>";
    }

    private static string RemoveGenericAritySuffix(string typeName)
    {
        var tickIndex = typeName.LastIndexOf('`');
        if (tickIndex <= 0 || tickIndex == typeName.Length - 1)
            return typeName;

        return int.TryParse(typeName[(tickIndex + 1)..], out _)
            ? typeName[..tickIndex]
            : typeName;
    }

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

    private (TypeRelationships Relationships,
        IReadOnlyList<ResolvedFieldModel> Fields,
        IReadOnlyList<ResolvedPropertyModel> Properties,
        IReadOnlyList<ResolvedEventModel> Events,
        IReadOnlyList<ResolvedMethodModel> Methods) ApplyMxFieldFamilyAdjustments(
        TypeDefinition type,
        TypeRelationships relationships,
        IReadOnlyList<ResolvedFieldModel> fields,
        IReadOnlyList<ResolvedPropertyModel> properties,
        IReadOnlyList<ResolvedEventModel> events,
        IReadOnlyList<ResolvedMethodModel> methods)
    {
        var campaignStageHistoryListType = BuildListType(_campaignStageHistoryDbTypeName);
        var fieldDateHistoryListType = BuildListType(_fieldDateHistoryDbTypeName);
        var fieldInteractionListType = BuildListType(_fieldInteractionDbTypeName);
        var fieldQuestListType = BuildListType(_fieldQuestDbTypeName);
        var fieldQuestInfoListType = BuildListType(_fieldQuestInfoTypeName);
        var fieldQuestInfoEnumerableType = BuildEnumerableType(_fieldQuestInfoTypeName);
        var characterDbListType = BuildListType(_gameCharacterDbTypeName);
        var parcelInfoListType = BuildListType(_parcelInfoTypeName);
        var fieldDateHistoryIListType = BuildIListType(_fieldDateHistoryDbTypeName);
        var fieldInteractionIListType = BuildIListType(_fieldInteractionDbTypeName);
        var fieldQuestIListType = BuildIListType(_fieldQuestDbTypeName);
        var rewardInfoListType = BuildListType(_fieldRewardInfoTypeName);
        var rewardInfoEnumerableType = BuildEnumerableType(_fieldRewardInfoTypeName);
        var rewardInfoDictionaryType = BuildDictionaryType("System.Int64", _fieldRewardInfoTypeName);
        var questInfoDictionaryType = BuildDictionaryType("System.Int64", fieldQuestInfoListType);
        var originalQuestInfoDictionaryType = BuildDictionaryType("System.Int64", _fieldQuestInfoTypeName);
        var int64EnumerableType = "System.Collections.Generic.IEnumerable<System.Int64>";
        var preloadRequiredListType = BuildListType(_iPreloadRequiredTypeName);
        var intStringPairArrayType = BuildArrayType(_intStringPairTypeName);
        const string DateTimeType = "System.DateTime";

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

        string? DesiredFieldType(string identifier)
        {
            return type.FullName switch
            {
                "MXField.Shared.NetworkProtocol.FieldSyncRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldSyncResponse" => identifier switch
                {
                    "<FieldSnapshot>k__BackingField" or "_FieldSnapshot_k__BackingField" => _fieldSnapshotTypeName,
                    "<PlayableDateId>k__BackingField" or "_PlayableDateId_k__BackingField" => "System.Int64",
                    "<StageHistoryDBs>k__BackingField" or "_StageHistoryDBs_k__BackingField" => campaignStageHistoryListType,
                    _ => null,
                },
                "MXField.Network.Task.FieldSyncResponseMessage" => identifier switch
                {
                    "<Snapshot>k__BackingField" or "_Snapshot_k__BackingField" => _fieldSnapshotTypeName,
                    "<StageHistoryDBs>k__BackingField" or "_StageHistoryDBs_k__BackingField" => campaignStageHistoryListType,
                    "<PlayableDateId>k__BackingField" or "_PlayableDateId_k__BackingField" => "System.Int64",
                    _ => null,
                },
                "MXField.Shared.NetworkProtocol.FieldInteractionRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<UniqueId>k__BackingField" or "_UniqueId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldInteractionResponse" => identifier switch
                {
                    "<InteractionDB>k__BackingField" or "_InteractionDB_k__BackingField" => _fieldInteractionDbTypeName,
                    "<CharacterDB>k__BackingField" or "_CharacterDB_k__BackingField" => _fieldCharacterDbTypeName,
                    "<MasteryDB>k__BackingField" or "_MasteryDB_k__BackingField" => _fieldMasteryDbTypeName,
                    "<ParcelResultDB>k__BackingField" or "_ParcelResultDB_k__BackingField" => _parcelResultDbTypeName,
                    _ => null,
                },
                "MXField.Shared.NetworkProtocol.FieldQuestClearRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<UniqueId>k__BackingField" or "_UniqueId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldQuestClearResponse" => identifier is "<Quest>k__BackingField" or "_Quest_k__BackingField" ? _fieldQuestDbTypeName : null,
                "MXField.Shared.NetworkProtocol.FieldSceneChangedRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<DateId>k__BackingField" or "_DateId_k__BackingField" or "<SceneId>k__BackingField" or "_SceneId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldEndDateRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<DateId>k__BackingField" or "_DateId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldEndDateResponse" => identifier is "<DateHistoryDB>k__BackingField" or "_DateHistoryDB_k__BackingField" ? _fieldDateHistoryDbTypeName : null,
                "MXField.Shared.NetworkProtocol.FieldEnterStageRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" or "<StageUniqueId>k__BackingField" or "_StageUniqueId_k__BackingField" or "<LastEnterStageEchelonNumber>k__BackingField" or "_LastEnterStageEchelonNumber_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldStageResultRequest" => identifier is "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldStageResultResponse" => identifier switch
                {
                    "<CampaignStageHistoryDB>k__BackingField" or "_CampaignStageHistoryDB_k__BackingField" => _campaignStageHistoryDbTypeName,
                    "<LevelUpCharacterDBs>k__BackingField" or "_LevelUpCharacterDBs_k__BackingField" => characterDbListType,
                    "<FirstClearReward>k__BackingField" or "_FirstClearReward_k__BackingField" => parcelInfoListType,
                    "<ThreeStarReward>k__BackingField" or "_ThreeStarReward_k__BackingField" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldDateHistoryDB" => identifier switch
                {
                    "<DateId>k__BackingField" or "_DateId_k__BackingField" => "System.Int64",
                    "<ClearDate>k__BackingField" or "_ClearDate_k__BackingField" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldInteractionDB" => identifier switch
                {
                    "<SeasonId>k__BackingField" or "_SeasonId_k__BackingField" => "System.Int64",
                    "<UniqueId>k__BackingField" or "_UniqueId_k__BackingField" => "System.Int64",
                    "<UpdateDate>k__BackingField" or "_UpdateDate_k__BackingField" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldQuestDB" => identifier switch
                {
                    "<SeasonId>k__BackingField" or "_SeasonId_k__BackingField" => "System.Int64",
                    "<UniqueId>k__BackingField" or "_UniqueId_k__BackingField" => "System.Int64",
                    "<UpdateDate>k__BackingField" or "_UpdateDate_k__BackingField" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldCharacterDB" => identifier is "<CurrentSceneId>k__BackingField" or "_CurrentSceneId_k__BackingField" or "<PreviousSceneId>k__BackingField" or "_PreviousSceneId_k__BackingField" or "<LastMasteryId>k__BackingField" or "_LastMasteryId_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.Model.FieldMasteryDB" => identifier is "<Exp>k__BackingField" or "_Exp_k__BackingField" ? "System.Int64" : null,
                "MXField.Shared.Model.FieldSnapshot" => identifier switch
                {
                    "<FieldSeasonId>k__BackingField" or "_FieldSeasonId_k__BackingField" => "System.Int64",
                    "<AccountId>k__BackingField" or "_AccountId_k__BackingField" => "System.Int64",
                    "<ServerTime>k__BackingField" or "_ServerTime_k__BackingField" => DateTimeType,
                    "<DateHistoryDBs>k__BackingField" or "_DateHistoryDBs_k__BackingField" => fieldDateHistoryListType,
                    "<Interactions>k__BackingField" or "_Interactions_k__BackingField" => fieldInteractionListType,
                    "<MainQuests>k__BackingField" or "_MainQuests_k__BackingField" => fieldQuestListType,
                    "<DailyQuests>k__BackingField" or "_DailyQuests_k__BackingField" => fieldQuestListType,
                    "_seasonInfoCache" => _fieldSeasonInfoTypeName,
                    _ => null,
                },
                "MXField.Shared.Data.FieldQuestInfo" => identifier switch
                {
                    "<SeasonId>k__BackingField" or "_SeasonId_k__BackingField" => "System.Int64",
                    "<Id>k__BackingField" or "_Id_k__BackingField" => "System.Int64",
                    "<DateId>k__BackingField" or "_DateId_k__BackingField" => "System.Int64",
                    "<RewardId>k__BackingField" or "_RewardId_k__BackingField" => "System.Int64",
                    "<Prob>k__BackingField" or "_Prob_k__BackingField" => "System.Int64",
                    "<OpenDate>k__BackingField" or "_OpenDate_k__BackingField" => "System.Int64",
                    _ => null,
                },
                "MXField.Shared.Data.FieldQuestData" => identifier switch
                {
                    "questInfoDict" => questInfoDictionaryType,
                    "originalQuestInfoDict" => originalQuestInfoDictionaryType,
                    _ => null,
                },
                "MXField.Shared.Data.FieldRewardInfo" => identifier switch
                {
                    "<Id>k__BackingField" or "_Id_k__BackingField" => "System.Int64",
                    "<ParcelInfos>k__BackingField" or "_ParcelInfos_k__BackingField" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Shared.Data.FieldRewardData" => identifier is "fieldRewardInfos" ? rewardInfoDictionaryType : null,
                "MXField.Network.Task.FieldInteractionResponseMessage" => identifier switch
                {
                    "<InteractionDB>k__BackingField" or "_InteractionDB_k__BackingField" => _fieldInteractionDbTypeName,
                    "<MasteryDB>k__BackingField" or "_MasteryDB_k__BackingField" => _fieldMasteryDbTypeName,
                    "<ParcelInfos>k__BackingField" or "_ParcelInfos_k__BackingField" => parcelInfoListType,
                    "<DisplaySequence>k__BackingField" or "_DisplaySequence_k__BackingField" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Level.FieldDesignLevelRoot" => identifier switch
                {
                    "<SceneInfo>k__BackingField" or "_SceneInfo_k__BackingField" => _fieldSceneInfoTypeName,
                    "<Preloaders>k__BackingField" or "_Preloaders_k__BackingField" => preloadRequiredListType,
                    _ => null,
                },
                "MXField.LUT.IntStringPair" => identifier switch
                {
                    "Key" => "System.Int32",
                    "Value" => "System.String",
                    _ => null,
                },
                "MXField.LUT.IntStringLUT" => identifier is "pairs" ? intStringPairArrayType : null,
                _ => null,
            };
        }

        string? DesiredPropertyType(string displayName)
        {
            return type.FullName switch
            {
                "MXField.Shared.NetworkProtocol.FieldSyncRequest" when displayName == "FieldSeasonId" => "System.Int64",
                "MXField.Shared.NetworkProtocol.FieldSyncResponse" => displayName switch
                {
                    "FieldSnapshot" => _fieldSnapshotTypeName,
                    "PlayableDateId" => "System.Int64",
                    "StageHistoryDBs" => campaignStageHistoryListType,
                    _ => null,
                },
                "MXField.Network.Task.FieldSyncResponseMessage" => displayName switch
                {
                    "Snapshot" => _fieldSnapshotTypeName,
                    "StageHistoryDBs" => campaignStageHistoryListType,
                    "PlayableDateId" => "System.Int64",
                    _ => null,
                },
                "MXField.Shared.NetworkProtocol.FieldInteractionRequest" => displayName is "FieldSeasonId" or "UniqueId" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldInteractionResponse" => displayName switch
                {
                    "InteractionDB" => _fieldInteractionDbTypeName,
                    "CharacterDB" => _fieldCharacterDbTypeName,
                    "MasteryDB" => _fieldMasteryDbTypeName,
                    "ParcelResultDB" => _parcelResultDbTypeName,
                    _ => null,
                },
                "MXField.Shared.NetworkProtocol.FieldQuestClearRequest" => displayName is "FieldSeasonId" or "UniqueId" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldQuestClearResponse" when displayName == "Quest" => _fieldQuestDbTypeName,
                "MXField.Shared.NetworkProtocol.FieldSceneChangedRequest" => displayName is "FieldSeasonId" or "DateId" or "SceneId" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldEndDateRequest" => displayName is "FieldSeasonId" or "DateId" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldEndDateResponse" when displayName == "DateHistoryDB" => _fieldDateHistoryDbTypeName,
                "MXField.Shared.NetworkProtocol.FieldEnterStageRequest" => displayName is "FieldSeasonId" or "StageUniqueId" or "LastEnterStageEchelonNumber" ? "System.Int64" : null,
                "MXField.Shared.NetworkProtocol.FieldStageResultRequest" when displayName == "FieldSeasonId" => "System.Int64",
                "MXField.Shared.NetworkProtocol.FieldStageResultResponse" => displayName switch
                {
                    "CampaignStageHistoryDB" => _campaignStageHistoryDbTypeName,
                    "LevelUpCharacterDBs" => characterDbListType,
                    "FirstClearReward" => parcelInfoListType,
                    "ThreeStarReward" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldDateHistoryDB" => displayName switch
                {
                    "DateId" => "System.Int64",
                    "ClearDate" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldInteractionDB" => displayName switch
                {
                    "SeasonId" or "UniqueId" or "DateId" => "System.Int64",
                    "UpdateDate" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldQuestDB" => displayName switch
                {
                    "SeasonId" or "UniqueId" or "DateId" => "System.Int64",
                    "UpdateDate" => DateTimeType,
                    _ => null,
                },
                "MXField.Shared.Model.FieldCharacterDB" => displayName is "CurrentSceneId" or "PreviousSceneId" or "LastMasteryId" ? "System.Int64" : null,
                "MXField.Shared.Model.FieldMasteryDB" when displayName == "Exp" => "System.Int64",
                "MXField.Shared.Model.FieldSnapshot" => displayName switch
                {
                    "FieldSeasonId" or "AccountId" or "CurrentDateId" or "StartDaysSince" => "System.Int64",
                    "ServerTime" => DateTimeType,
                    "DateHistoryDBs" => fieldDateHistoryListType,
                    "Interactions" => fieldInteractionListType,
                    "MainQuests" => fieldQuestListType,
                    "DailyQuests" => fieldQuestListType,
                    "ClearDateIds" or "MainQuestIds" or "InteractionIds" or "EvidenceUniqueIds" => int64EnumerableType,
                    "SeasonInfo" => _fieldSeasonInfoTypeName,
                    _ => null,
                },
                "MXField.Shared.Data.FieldQuestInfo" => displayName is "SeasonId" or "Id" or "DateId" or "RewardId" or "Prob" or "OpenDate" ? "System.Int64" : null,
                "MXField.Shared.Data.FieldRewardInfo" => displayName switch
                {
                    "Id" => "System.Int64",
                    "ParcelInfos" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Shared.Data.FieldRewardData" => displayName switch
                {
                    _ => null,
                },
                "MXField.Network.Task.FieldInteractionResponseMessage" => displayName switch
                {
                    "InteractionDB" => _fieldInteractionDbTypeName,
                    "MasteryDB" => _fieldMasteryDbTypeName,
                    "ParcelInfos" => parcelInfoListType,
                    "DisplaySequence" => parcelInfoListType,
                    _ => null,
                },
                "MXField.Level.FieldDesignLevelRoot" => displayName switch
                {
                    "SceneInfo" => _fieldSceneInfoTypeName,
                    "Preloaders" => preloadRequiredListType,
                    _ => null,
                },
                _ => null,
            };
        }

        var adjustedFields = fields.Select(field =>
        {
            var desiredType = DesiredFieldType(field.Identifier);
            return desiredType is null ? field : field with { TypeName = PreferFieldFamilyType(field.TypeName, desiredType) };
        }).ToArray();

        var adjustedProperties = properties.Select(property =>
        {
            var desiredType = DesiredPropertyType(property.DisplayName);
            return desiredType is null ? property : property with { TypeName = PreferFieldFamilyType(property.TypeName, desiredType) };
        }).ToArray();

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

        return (relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }

    private static string? BuildListType(string? elementType)
        => string.IsNullOrWhiteSpace(elementType) ? null : $"System.Collections.Generic.List<{elementType}>";

    private static string? BuildEnumerableType(string? elementType)
        => string.IsNullOrWhiteSpace(elementType) ? null : $"System.Collections.Generic.IEnumerable<{elementType}>";

    private static string? BuildIListType(string? elementType)
        => string.IsNullOrWhiteSpace(elementType) ? null : $"System.Collections.Generic.IList<{elementType}>";

    private static string? BuildArrayType(string? elementType)
        => string.IsNullOrWhiteSpace(elementType) ? null : $"{elementType}[]";

    private static string? BuildDictionaryType(string keyType, string? valueType)
        => string.IsNullOrWhiteSpace(valueType) ? null : $"System.Collections.Generic.Dictionary<{keyType}, {valueType}>";

    private static string? BuildClosedGenericType(string? genericTypeName, params string?[] argumentTypeNames)
    {
        if (string.IsNullOrWhiteSpace(genericTypeName) ||
            argumentTypeNames is null ||
            argumentTypeNames.Length == 0 ||
            argumentTypeNames.Any(string.IsNullOrWhiteSpace))
            return null;

        var tickIndex = genericTypeName!.LastIndexOf('`');
        var baseName = tickIndex > 0 ? genericTypeName[..tickIndex] : genericTypeName;
        return $"{baseName}<{string.Join(", ", argumentTypeNames!)}>";
    }

    private (TypeRelationships Relationships,
        IReadOnlyList<ResolvedFieldModel> Fields,
        IReadOnlyList<ResolvedPropertyModel> Properties,
        IReadOnlyList<ResolvedEventModel> Events,
        IReadOnlyList<ResolvedMethodModel> Methods) ApplyFlatBufferTableAdjustments(
        TypeDefinition type,
        TypeRelationships relationships,
        IReadOnlyList<ResolvedFieldModel> fields,
        IReadOnlyList<ResolvedPropertyModel> properties,
        IReadOnlyList<ResolvedEventModel> events,
        IReadOnlyList<ResolvedMethodModel> methods)
    {
        var methodNames = methods.Select(method => method.DisplayName).ToHashSet(StringComparer.Ordinal);
        if (!methodNames.Contains("__assign") &&
            !methodNames.Any(name => name.StartsWith("GetRootAs", StringComparison.Ordinal)))
        {
            return (relationships, fields, properties, events, methods);
        }

        var offsetType = $"FlatBuffers.Offset<{type.FullName}>";
        var nullableByteSegmentType = "System.Nullable<System.ArraySegment<System.Byte>>";
        var byteArrayType = "System.Byte[]";
        var elementType = type.Name.EndsWith("Table", StringComparison.Ordinal) && !string.IsNullOrWhiteSpace(type.Namespace)
            ? $"{type.Namespace}.{type.Name[..^"Table".Length]}"
            : null;

        static bool IsWeakFlatBufferType(string typeName)
            => string.IsNullOrWhiteSpace(typeName) ||
               typeName.StartsWith("Type_0x", StringComparison.Ordinal) ||
               string.Equals(typeName, "int", StringComparison.Ordinal) ||
               string.Equals(typeName, "long", StringComparison.Ordinal) ||
               string.Equals(typeName, "float", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Int32", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Int64", StringComparison.Ordinal) ||
               string.Equals(typeName, "System.Single", StringComparison.Ordinal);

        static string PreferFlatBufferType(string currentType, string desiredType)
            => IsWeakFlatBufferType(currentType) ? desiredType : currentType;

        static HashSet<string> BuildOrdinalIgnoreCaseSet(params string[] values)
            => new(values, StringComparer.OrdinalIgnoreCase);

        var scalarLongMembers = type.FullName switch
        {
            "FlatData.FieldRewardExcel" => BuildOrdinalIgnoreCaseSet("groupId", "GroupId", "rewardId", "RewardId"),
            "FlatData.FieldSceneExcel" => BuildOrdinalIgnoreCaseSet("uniqueId", "UniqueId", "dateId", "DateId", "groupId", "GroupId", "bGMId", "BGMId"),
            "FlatData.FieldInteractionExcel" => BuildOrdinalIgnoreCaseSet("fieldSeasonId", "FieldSeasonId", "uniqueId", "UniqueId", "fieldDateId", "FieldDateId"),
            _ => BuildOrdinalIgnoreCaseSet(),
        };

        var vectorLongMembers = type.FullName switch
        {
            "FlatData.FieldSceneExcel" => BuildOrdinalIgnoreCaseSet(
                "conditionalBGMQuestId", "ConditionalBGMQuestId",
                "beginConditionalBGMScenarioGroupId", "BeginConditionalBGMScenarioGroupId",
                "beginConditionalBGMInteractionId", "BeginConditionalBGMInteractionId",
                "endConditionalBGMScenarioGroupId", "EndConditionalBGMScenarioGroupId",
                "endConditionalBGMInteractionId", "EndConditionalBGMInteractionId",
                "conditionalBGMId", "ConditionalBGMId"),
            "FlatData.FieldInteractionExcel" => BuildOrdinalIgnoreCaseSet(
                "interactionId", "InteractionId",
                "conditionClassParameters", "ConditionClassParameters",
                "conditionIndex", "ConditionIndex",
                "conditionId", "ConditionId"),
            _ => BuildOrdinalIgnoreCaseSet(),
        };

        static string? StripGetPrefix(string methodName)
            => methodName.StartsWith("get_", StringComparison.Ordinal) ? methodName[4..] : null;

        string? DesiredFlatBufferParameterType(string methodName, string parameterName)
        {
            if (string.Equals(methodName, "InitKey", StringComparison.Ordinal) &&
                string.Equals(parameterName, "key", StringComparison.Ordinal))
            {
                return byteArrayType;
            }

            if ((string.Equals(methodName, $"Finish{type.Name}Buffer", StringComparison.Ordinal) ||
                 string.Equals(methodName, $"FinishSizePrefixed{type.Name}Buffer", StringComparison.Ordinal)) &&
                string.Equals(parameterName, "offset", StringComparison.Ordinal))
            {
                return offsetType;
            }

            if (!string.IsNullOrWhiteSpace(elementType) &&
                string.Equals(methodName, "CreateDataListVector", StringComparison.Ordinal) &&
                string.Equals(parameterName, "data", StringComparison.Ordinal))
            {
                return $"FlatBuffers.Offset<{elementType}>[]";
            }

            if (methodName.EndsWith("Vector", StringComparison.Ordinal) &&
                string.Equals(parameterName, "data", StringComparison.Ordinal))
            {
                var memberStem = methodName["Create".Length..^"Vector".Length];
                if (vectorLongMembers.Contains(memberStem))
                    return "System.Int64[]";
            }

            if (methodName.StartsWith("Add", StringComparison.Ordinal) && parameterName.Length > 0)
            {
                var memberStem = methodName["Add".Length..];
                if (scalarLongMembers.Contains(memberStem))
                    return "System.Int64";
            }

            return type.FullName switch
            {
                "FlatData.FieldInteractionExcel" => methodName == "CreateFieldInteractionExcel" && parameterName is "FieldSeasonId" or "UniqueId" or "FieldDateId"
                    ? "System.Int64"
                    : null,
                "FlatData.FieldRewardExcel" => methodName == "CreateFieldRewardExcel" && parameterName is "GroupId" or "RewardId"
                    ? "System.Int64"
                    : null,
                "FlatData.FieldSceneExcel" => methodName == "CreateFieldSceneExcel" && parameterName is "UniqueId" or "DateId" or "GroupId" or "BGMId"
                    ? "System.Int64"
                    : null,
                _ => null,
            };
        }

        var adjustedFields = fields.Select(field =>
        {
            if (field.Identifier != "TableKey")
                return field;

            return field with
            {
                TypeName = PreferFlatBufferType(field.TypeName, byteArrayType),
                Modifiers = ["public", "static"],
                Accessibility = ExportMemberAccessibility.Public,
            };
        }).ToArray();

        var adjustedProperties = properties.Select(property =>
        {
            if (scalarLongMembers.Contains(property.DisplayName))
                return property with { TypeName = PreferFlatBufferType(property.TypeName, "System.Int64") };

            return property;
        }).ToArray();

        var adjustedMethods = methods.Select(method =>
        {
            string? desiredReturnType = null;
            if (string.Equals(method.DisplayName, $"Create{type.Name}", StringComparison.Ordinal) ||
                string.Equals(method.DisplayName, $"End{type.Name}", StringComparison.Ordinal))
            {
                desiredReturnType = offsetType;
            }
            else if (!string.IsNullOrWhiteSpace(elementType) &&
                     string.Equals(method.DisplayName, "DataList", StringComparison.Ordinal))
            {
                desiredReturnType = $"System.Nullable<{elementType}>";
            }
            else if (method.DisplayName.StartsWith("Get", StringComparison.Ordinal) &&
                     method.DisplayName.EndsWith("Bytes", StringComparison.Ordinal))
            {
                desiredReturnType = nullableByteSegmentType;
            }
            else if (scalarLongMembers.Contains(method.DisplayName) ||
                     vectorLongMembers.Contains(method.DisplayName) ||
                     (StripGetPrefix(method.DisplayName) is { } getterTarget &&
                      (scalarLongMembers.Contains(getterTarget) || vectorLongMembers.Contains(getterTarget))))
            {
                desiredReturnType = "System.Int64";
            }

            var adjustedParameters = method.Parameters.Select(parameter =>
            {
                var desiredType = DesiredFlatBufferParameterType(method.DisplayName, parameter.Identifier);

                return desiredType is null
                    ? parameter
                    : parameter with { TypeName = PreferFlatBufferType(parameter.TypeName, desiredType) };
            }).ToArray();

            return method with
            {
                ReturnTypeName = desiredReturnType is null ? method.ReturnTypeName : PreferFlatBufferType(method.ReturnTypeName, desiredReturnType),
                Parameters = adjustedParameters,
            };
        }).ToArray();

        return (relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }

    private (TypeRelationships Relationships,
        IReadOnlyList<ResolvedFieldModel> Fields,
        IReadOnlyList<ResolvedPropertyModel> Properties,
        IReadOnlyList<ResolvedEventModel> Events,
        IReadOnlyList<ResolvedMethodModel> Methods) ApplyMemoryPackAdjustments(
        TypeDefinition type,
        string safeTypeName,
        string? declaringType,
        TypeRelationships relationships,
        IReadOnlyList<ResolvedFieldModel> fields,
        IReadOnlyList<ResolvedPropertyModel> properties,
        IReadOnlyList<ResolvedEventModel> events,
        IReadOnlyList<ResolvedMethodModel> methods)
    {
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
            return (relationships, fields, properties, events, methods);
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

        return (relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }

    private (TypeRelationships Relationships,
        IReadOnlyList<ResolvedFieldModel> Fields,
        IReadOnlyList<ResolvedPropertyModel> Properties,
        IReadOnlyList<ResolvedEventModel> Events,
        IReadOnlyList<ResolvedMethodModel> Methods) ApplyFutureLikeAdjustments(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyList<string> genericParameterNames,
        TypeRelationships relationships,
        IReadOnlyList<ResolvedFieldModel> fields,
        IReadOnlyList<ResolvedPropertyModel> properties,
        IReadOnlyList<ResolvedEventModel> events,
        IReadOnlyList<ResolvedMethodModel> methods)
    {
        if (!IsFutureLikeType(type, methodRows) || genericParameterNames.Count != 1)
            return (relationships, fields, properties, events, methods);

        var genericArg = genericParameterNames[0];
        var futureInterface = ApplyGenericContext(_futureInterfaceTypeName, genericParameterNames);
        var futureValueCallback = ApplyGenericContext(_futureValueCallbackTypeName, genericParameterNames);
        var futureCallback = ApplyGenericContext(_futureCallbackTypeName, genericParameterNames);
        var futureErrorCallback = _futureErrorCallbackTypeName;
        var hubConnection = _hubConnectionTypeName;

        if (!string.IsNullOrWhiteSpace(futureInterface) &&
            TypeKind(type) != "interface" &&
            !relationships.Interfaces.Contains(futureInterface, StringComparer.Ordinal))
        {
            relationships = new TypeRelationships(
                relationships.BaseType,
                [futureInterface, .. relationships.Interfaces],
                relationships.Comments);
        }

        var adjustedFields = fields.Select(field =>
        {
            var desiredType = field.Identifier switch
            {
                "future" => futureInterface,
                "hubConnection" => hubConnection,
                "invocationId" => "System.Int64",
                _ => null,
            };
            return desiredType is null ? field : field with { TypeName = PreferSpecificType(field.TypeName, desiredType) };
        }).ToArray();

        var adjustedProperties = properties.Select(property =>
        {
            var desiredType = property.DisplayName switch
            {
                "value" => genericArg,
                _ => null,
            };
            return desiredType is null ? property : property with { TypeName = PreferSpecificType(property.TypeName, desiredType) };
        }).ToArray();

        var adjustedMethods = methods.Select(method =>
        {
            var adjustedReturnType = method.DisplayName switch
            {
                "get_value" => PreferSpecificType(method.ReturnTypeName, genericArg),
                "OnItem" or "OnSuccess" or "OnError" or "OnComplete" when !string.IsNullOrWhiteSpace(futureInterface) => PreferSpecificType(method.ReturnTypeName, futureInterface!),
                _ => method.ReturnTypeName,
            };

            var adjustedParameters = method.Parameters.Select(parameter =>
            {
                string? desiredType = null;
                if (method.DisplayName == ".ctor")
                {
                    if ((parameter.Identifier == "hub" || parameter.Identifier == "connection") && !string.IsNullOrWhiteSpace(hubConnection))
                        desiredType = hubConnection;
                    else if (parameter.Identifier == "future" && !string.IsNullOrWhiteSpace(futureInterface))
                        desiredType = futureInterface;
                    else if (parameter.Identifier is "iId" or "invocationId")
                        desiredType = "System.Int64";
                }
                else if (parameter.Identifier == "callback")
                {
                    desiredType = method.DisplayName switch
                    {
                        "OnItem" or "OnSuccess" => futureValueCallback,
                        "OnComplete" => futureCallback,
                        "OnError" => futureErrorCallback,
                        _ => null,
                    };
                }

                return desiredType is null
                    ? parameter
                    : parameter with
                    {
                        TypeName = parameter.Identifier == "callback" && method.DisplayName is "OnItem" or "OnSuccess" or "OnComplete"
                            ? desiredType
                            : PreferSpecificType(parameter.TypeName, desiredType),
                    };
            }).ToArray();

            return method with
            {
                ReturnTypeName = adjustedReturnType,
                Parameters = adjustedParameters,
            };
        }).ToArray();

        return (relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }

    private (TypeRelationships Relationships,
        IReadOnlyList<ResolvedFieldModel> Fields,
        IReadOnlyList<ResolvedPropertyModel> Properties,
        IReadOnlyList<ResolvedEventModel> Events,
        IReadOnlyList<ResolvedMethodModel> Methods) ApplyFieldBridgeAdjustments(
        TypeDefinition type,
        string? declaringType,
        TypeRelationships relationships,
        IReadOnlyList<ResolvedFieldModel> fields,
        IReadOnlyList<ResolvedPropertyModel> properties,
        IReadOnlyList<ResolvedEventModel> events,
        IReadOnlyList<ResolvedMethodModel> methods)
    {
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
            return (relationships, fields, properties, events, methods);

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

        return (relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }

    private (TypeRelationships Relationships,
        IReadOnlyList<ResolvedFieldModel> Fields,
        IReadOnlyList<ResolvedPropertyModel> Properties,
        IReadOnlyList<ResolvedEventModel> Events,
        IReadOnlyList<ResolvedMethodModel> Methods) ApplyReferenceModelAdjustments(
        TypeDefinition type,
        string safeTypeName,
        string? declaringType,
        TypeRelationships relationships,
        IReadOnlyList<ResolvedFieldModel> fields,
        IReadOnlyList<ResolvedPropertyModel> properties,
        IReadOnlyList<ResolvedEventModel> events,
        IReadOnlyList<ResolvedMethodModel> methods)
    {
        var isAutoUseRuleDao = string.Equals(type.FullName, "AutoUseRuleDAO", StringComparison.Ordinal);
        var isGroundObstacleData = string.Equals(type.FullName, "MX.Data.GroundObstacleData", StringComparison.Ordinal);
        var isGroundObstacleDataCollection = string.Equals(type.FullName, "MX.Data.GroundObstacleDataCollection", StringComparison.Ordinal);
        var isGroundObstacleDataHashComparer = string.Equals(type.FullName, "MX.Data.GroundObstacleDataHashComparer", StringComparison.Ordinal);
        var isPositionSetting = string.Equals(type.FullName, "MX.Visual.Data.PositionSetting", StringComparison.Ordinal);
        var isAreaCollisionProperty = string.Equals(type.FullName, "MX.Logic.Data.AreaCollisionProperty", StringComparison.Ordinal);
        var isAccountBillingInfo = string.Equals(type.FullName, "AccountBillingInfo", StringComparison.Ordinal);
        var isByteReader =
            string.Equals(type.FullName, "ByteReader", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ByteReader", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isBmFont =
            string.Equals(type.FullName, "BMFont", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "BMFont", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isBmGlyph =
            string.Equals(type.FullName, "BMGlyph", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "BMGlyph", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isBmSymbol =
            string.Equals(type.FullName, "BMSymbol", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "BMSymbol", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isRuntimeInspectorUtils =
            string.Equals(type.FullName, "RuntimeInspectorNamespace.RuntimeInspectorUtils", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "RuntimeInspectorUtils", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isHubConnectionExtensions =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.HubConnectionExtensions", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "HubConnectionExtensions", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isUploadItemControllerExtensions =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.UploadItemControllerExtensions", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "UploadItemControllerExtensions", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isBitPackFormatter =
            string.Equals(type.FullName, "MemoryPack.Compression.BitPackFormatter", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "BitPackFormatter", StringComparison.Ordinal) && string.Equals(type.Namespace, "MemoryPack.Compression", StringComparison.Ordinal));
        var isSystemRuntimeUnsafe =
            string.Equals(type.FullName, "System.Runtime.CompilerServices.Unsafe", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "Unsafe", StringComparison.Ordinal) && string.Equals(type.Namespace, "System.Runtime.CompilerServices", StringComparison.Ordinal));
        var isCommunityToolkitArrayExtensions =
            string.Equals(type.FullName, "CommunityToolkit.HighPerformance.ArrayExtensions", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ArrayExtensions", StringComparison.Ordinal) && string.Equals(type.Namespace, "CommunityToolkit.HighPerformance", StringComparison.Ordinal));
        var isTimelineExtensions =
            string.Equals(type.FullName, "Spine.Unity.AnimationTools.TimelineExtensions", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "TimelineExtensions", StringComparison.Ordinal) && string.Equals(type.Namespace, "Spine.Unity.AnimationTools", StringComparison.Ordinal));
        var isWebRequestUtils =
            string.Equals(type.FullName, "UnityEngineInternal.WebRequestUtils", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "WebRequestUtils", StringComparison.Ordinal) && string.Equals(type.Namespace, "UnityEngineInternal", StringComparison.Ordinal));
        var isJsonUtility =
            string.Equals(type.FullName, "UnityEngine.JsonUtility", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "JsonUtility", StringComparison.Ordinal) && string.Equals(type.Namespace, "UnityEngine", StringComparison.Ordinal));
        var isFlatBuffersByteBuffer =
            string.Equals(type.FullName, "FlatBuffers.ByteBuffer", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ByteBuffer", StringComparison.Ordinal) && string.Equals(type.Namespace, "FlatBuffers", StringComparison.Ordinal));
        var isSocketIoTransportInterface =
            string.Equals(type.FullName, "BestHTTP.SocketIO.Transports.ITransport", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ITransport", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SocketIO.Transports", StringComparison.Ordinal));
        var isSocketIoJsonEncoder =
            string.Equals(type.FullName, "BestHTTP.SocketIO.JsonEncoders.IJsonEncoder", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "IJsonEncoder", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SocketIO.JsonEncoders", StringComparison.Ordinal));
        var isSocketIoDefaultJsonEncoder =
            string.Equals(type.FullName, "BestHTTP.SocketIO.JsonEncoders.DefaultJSonEncoder", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "DefaultJSonEncoder", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SocketIO.JsonEncoders", StringComparison.Ordinal));
        var isSignalRCoreEncoder =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.IEncoder", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "IEncoder", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isSignalRCoreProtocol =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.IProtocol", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "IProtocol", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isSignalRCoreUploadItemController =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.IUPloadItemController`1", StringComparison.Ordinal) ||
            (string.Equals(type.Name, "IUPloadItemController`1", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isSignalRCoreStreamItemContainer =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.StreamItemContainer`1", StringComparison.Ordinal) ||
            (string.Equals(type.Name, "StreamItemContainer`1", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isSignalRCoreCallbackDescriptor =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.CallbackDescriptor", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "CallbackDescriptor", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isSocketIO3EventsCallbackDescriptor =
            string.Equals(type.FullName, "BestHTTP.SocketIO3.Events.CallbackDescriptor", StringComparison.Ordinal);
        var isSocketIO3EventsSubscription =
            string.Equals(type.FullName, "BestHTTP.SocketIO3.Events.Subscription", StringComparison.Ordinal);
        var isSocketIO3EventsTypedEventTable =
            string.Equals(type.FullName, "BestHTTP.SocketIO3.Events.TypedEventTable", StringComparison.Ordinal);
        var isBestHttpCorePluginEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.PluginEventInfo", StringComparison.Ordinal);
        var isBestHttpCorePluginEventHelper =
            string.Equals(type.FullName, "BestHTTP.Core.PluginEventHelper", StringComparison.Ordinal);
        var isBestHttpCoreConnectionEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.ConnectionEventInfo", StringComparison.Ordinal);
        var isBestHttpCoreConnectionEventHelper =
            string.Equals(type.FullName, "BestHTTP.Core.ConnectionEventHelper", StringComparison.Ordinal);
        var isBestHttpCoreHostProtocolSupport =
            string.Equals(type.FullName, "BestHTTP.Core.HostProtocolSupport", StringComparison.Ordinal);
        var isBestHttpCoreHostConnection =
            string.Equals(type.FullName, "BestHTTP.Core.HostConnection", StringComparison.Ordinal);
        var isBestHttpCoreHostDefinition =
            string.Equals(type.FullName, "BestHTTP.Core.HostDefinition", StringComparison.Ordinal);
        var isBestHttpCoreHostConnectionKey =
            string.Equals(type.FullName, "BestHTTP.Core.HostConnectionKey", StringComparison.Ordinal);
        var isBestHttpCoreAltSvcEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.AltSvcEventInfo", StringComparison.Ordinal);
        var isBestHttpCoreHttp2ConnectProtocolInfo =
            string.Equals(type.FullName, "BestHTTP.Core.HTTP2ConnectProtocolInfo", StringComparison.Ordinal);
        var isBestHttpCoreProtocolEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.ProtocolEventInfo", StringComparison.Ordinal);
        var isBestHttpCoreProtocolEventHelper =
            string.Equals(type.FullName, "BestHTTP.Core.ProtocolEventHelper", StringComparison.Ordinal);
        var isBestHttpCoreRequestEventInfo =
            string.Equals(type.FullName, "BestHTTP.Core.RequestEventInfo", StringComparison.Ordinal);
        var isBestHttpCoreRequestEventHelper =
            string.Equals(type.FullName, "BestHTTP.Core.RequestEventHelper", StringComparison.Ordinal);
        var isSignalRCoreInvocationDefinition =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.InvocationDefinition", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "InvocationDefinition", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isSignalRCoreTransportInterface =
            string.Equals(type.FullName, "BestHTTP.SignalRCore.ITransport", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "ITransport", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.SignalRCore", StringComparison.Ordinal));
        var isFutureCallback =
            string.Equals(type.FullName, "BestHTTP.Futures.FutureCallback`1", StringComparison.Ordinal) ||
            (string.Equals(type.Name, "FutureCallback`1", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.Futures", StringComparison.Ordinal));
        var isFutureValueCallback =
            string.Equals(type.FullName, "BestHTTP.Futures.FutureValueCallback`1", StringComparison.Ordinal) ||
            (string.Equals(type.Name, "FutureValueCallback`1", StringComparison.Ordinal) && string.Equals(type.Namespace, "BestHTTP.Futures", StringComparison.Ordinal));
        var isAddTypeMenuAttribute =
            string.Equals(type.FullName, "AddTypeMenuAttribute", StringComparison.Ordinal) &&
            string.IsNullOrWhiteSpace(type.Namespace);
        var isGenericGraphNodeMetadata =
            string.Equals(type.FullName, "MXGenericGraph.GenericGraphNodeMetadata", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "GenericGraphNodeMetadata", StringComparison.Ordinal) && string.Equals(type.Namespace, "MXGenericGraph", StringComparison.Ordinal));
        var isSkeletonAnimationPlayableHandle =
            string.Equals(type.FullName, "Spine.Unity.Playables.SkeletonAnimationPlayableHandle", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "SkeletonAnimationPlayableHandle", StringComparison.Ordinal) && string.Equals(type.Namespace, "Spine.Unity.Playables", StringComparison.Ordinal));
        var isWwwForm =
            string.Equals(type.FullName, "UnityEngine.WWWForm", StringComparison.Ordinal) ||
            string.Equals(type.FullName, "WWWForm", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "WWWForm", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var parsedSafeGeneric = YldaResolutionUtilities.ParseGenericType(safeTypeName);
        var isSystemActionDelegate =
            string.Equals(type.Namespace, "System", StringComparison.Ordinal) &&
            parsedSafeGeneric is { BaseName: "Action" };
        var isSystemFuncDelegate =
            string.Equals(type.Namespace, "System", StringComparison.Ordinal) &&
            parsedSafeGeneric is { BaseName: "Func" };
        var isNguiText =
            string.Equals(type.FullName, "NGUIText", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "NGUIText", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isUiDrawCall =
            string.Equals(type.FullName, "UIDrawCall", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "UIDrawCall", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isBetterList =
            string.Equals(type.Name, "BetterList`1", StringComparison.Ordinal) ||
            (safeTypeName.StartsWith("BetterList<", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isCachedGeometries =
            string.Equals(type.FullName, "CachedGeometries", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "CachedGeometries", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isEventDelegate =
            string.Equals(type.FullName, "EventDelegate", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "EventDelegate", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isEventDelegateParameter =
            string.Equals(safeTypeName, "Parameter", StringComparison.Ordinal) &&
            string.Equals(declaringType, "EventDelegate", StringComparison.Ordinal);
        var isPropertyReference =
            string.Equals(type.FullName, "PropertyReference", StringComparison.Ordinal) ||
            (string.Equals(safeTypeName, "PropertyReference", StringComparison.Ordinal) && string.IsNullOrWhiteSpace(declaringType));
        var isFurnitureInventoryObject = string.Equals(type.FullName, "FurnitureInventoryObject", StringComparison.Ordinal);
        var isFurnitureObject = string.Equals(type.FullName, "FurnitureObject", StringComparison.Ordinal);
        var isFurnitureFilter =
            string.Equals(safeTypeName, "FurnitureFilter", StringComparison.Ordinal) &&
            string.Equals(declaringType, "FurnitureInventoryObject", StringComparison.Ordinal);
        var isConstraintStruct =
            string.Equals(type.FullName, "MX.Logic.Data.TacticEntityConstraint", StringComparison.Ordinal) ||
            string.Equals(type.FullName, "MX.Logic.Data.TacticRangeConstraint", StringComparison.Ordinal) ||
            string.Equals(type.FullName, "MX.Logic.Data.TacticRoleConstraint", StringComparison.Ordinal) ||
            string.Equals(type.FullName, "MX.Logic.Data.TagConstraint", StringComparison.Ordinal);
        var isGroundObstacleRepository = string.Equals(type.FullName, "GroundObstacleDataRepository", StringComparison.Ordinal);

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
            return (relationships, fields, properties, events, methods);
        }

        if (Environment.GetEnvironmentVariable("YLDA_DEBUG_REFERENCE_TYPES") == "1" &&
            (isNguiText || isUiDrawCall || isRuntimeInspectorUtils))
        {
            Console.Error.WriteLine($"[refdbg] type={type.FullName} safe={safeTypeName} decl={declaringType ?? "<null>"} runtimeInspector={isRuntimeInspectorUtils} ngui={isNguiText} draw={isUiDrawCall}");
        }

        string? equatableInterface = BuildClosedGenericType(_equatableTypeName, !string.IsNullOrWhiteSpace(type.Namespace) ? $"{type.Namespace}.{safeTypeName}" : safeTypeName);
        var vector2ListType = BuildListType(_unityVector2TypeName);
        var skillAbilityModifierListType = BuildListType(_skillAbilityModifierDaoTypeName);
        var tacticRangeArrayType = BuildArrayType("FlatData.TacticRange");
        var tacticRoleArrayType = BuildArrayType("FlatData.TacticRole");
        var keyedCollectionGroundObstacleType = !string.IsNullOrWhiteSpace(_groundObstacleDataTypeName)
            ? $"System.Collections.ObjectModel.KeyedCollection<System.UInt32, {_groundObstacleDataTypeName}>"
            : null;
        var equalityComparerGroundObstacleType = BuildClosedGenericType("System.Collections.Generic.IEqualityComparer`1", _groundObstacleDataTypeName);
        var comparerGroundObstacleType = BuildClosedGenericType("System.Collections.Generic.IComparer`1", _groundObstacleDataTypeName);
        var furnitureObjectListType = BuildListType("FurnitureObject");
        var furnitureObjectEnumerableType = BuildEnumerableType("FurnitureObject");
        var furnitureDbListType = BuildListType("MX.GameLogic.DBModel.FurnitureDB");
        var furnitureDbDictionaryType = BuildDictionaryType("System.Int64", "MX.GameLogic.DBModel.FurnitureDB");
        var furnitureCategoryListType = BuildListType("FlatData.FurnitureCategory");
        var furnitureSubCategoryListType = BuildListType("FlatData.FurnitureSubCategory");
        var secureLongListType = BuildListType("SecureLong");
        var furnitureTagsDictionaryType = BuildDictionaryType("FlatData.Tag", "System.Int32");
        var purchaseCountDbListType = BuildListType("MX.GameLogic.DBModel.PurchaseCountDB");
        var blockedProductDbListType = BuildListType("MX.GameLogic.DBModel.BlockedProductDB");
        var bmGlyphListType = BuildListType("BMGlyph");
        var bmGlyphDictionaryType = BuildDictionaryType("System.Int32", "BMGlyph");
        var intListType = BuildListType("System.Int32");
        var memberInfoArrayType = BuildArrayType("System.Reflection.MemberInfo");
        var exposedMethodArrayType = BuildArrayType("RuntimeInspectorNamespace.ExposedMethod");
        var byteArrayType = BuildArrayType("System.Byte");
        var byteArrayListType = BuildListType(byteArrayType!);
        var typeHashSetType = BuildClosedGenericType("System.Collections.Generic.HashSet`1", "System.Type");
        var transformHashSetType = BuildClosedGenericType("System.Collections.Generic.HashSet`1", "UnityEngine.Transform");
        var typeListType = BuildListType("System.Type");
        var stringListType = BuildListType("System.String");
        var exposedMethodListType = BuildListType("RuntimeInspectorNamespace.ExposedMethod");
        var exposedExtensionMethodHolderListType = BuildListType("RuntimeInspectorNamespace.ExposedExtensionMethodHolder");
        var customEditorAttributeListType = BuildListType("RuntimeInspectorNamespace.RuntimeInspectorCustomEditorAttribute");
        var draggedReferenceItemStackType = BuildClosedGenericType("System.Collections.Generic.Stack`1", "RuntimeInspectorNamespace.DraggedReferenceItem");
        var typeToVariablesDictionaryType = BuildDictionaryType("System.Type", memberInfoArrayType);
        var typeToExposedMethodsDictionaryType = BuildDictionaryType("System.Type", exposedMethodArrayType);
        var typeToTypeDictionaryType = BuildDictionaryType("System.Type", "System.Type");
        var unityObjectArrayType = BuildArrayType("UnityEngine.Object");
        var betterListColorType = BuildClosedGenericType("BetterList`1", "UnityEngine.Color");
        var betterListSingleType = BuildClosedGenericType("BetterList`1", "System.Single");
        var uiDrawCallListType = BuildClosedGenericType("BetterList`1", "UIDrawCall");
        var vector3ListType = BuildListType(_unityVector3TypeName);
        var vector4ListType = BuildListType("UnityEngine.Vector4");
        var intArrayType = BuildArrayType("System.Int32");
        var singleArrayType = BuildArrayType("System.Single");
        const string glyphInfoType = "NGUIText.GlyphInfo";
        const string fontType = "UnityEngine.Font";
        const string fontStyleType = "UnityEngine.FontStyle";
        const string alignmentType = "NGUIText.Alignment";
        const string symbolStyleType = "NGUIText.SymbolStyle";
        const string colorType = "UnityEngine.Color";
        const string stringBuilderType = "System.Text.StringBuilder";
        const string texture2DType = "UnityEngine.Texture2D";
        const string materialType = "UnityEngine.Material";
        const string textureType = "UnityEngine.Texture";
        const string transformType = "UnityEngine.Transform";
        const string meshType = "UnityEngine.Mesh";
        const string meshFilterType = "UnityEngine.MeshFilter";
        const string meshRendererType = "UnityEngine.MeshRenderer";
        const string materialPropertyBlockType = "UnityEngine.MaterialPropertyBlock";
        const string uiSkinType = "RuntimeInspectorNamespace.UISkin";
        const string draggedReferenceItemType = "RuntimeInspectorNamespace.DraggedReferenceItem";
        const string numberFormatInfoType = "System.Globalization.NumberFormatInfo";
        var monthlyProductRewardsType = !string.IsNullOrWhiteSpace(_parcelInfoTypeName)
            ? BuildDictionaryType("FlatData.RewardTag", BuildListType(_parcelInfoTypeName))
            : null;
        var betterListStringType = BuildClosedGenericType("BetterList`1", "System.String");
        var stringDictionaryType = BuildDictionaryType("System.String", "System.String");
        var eventDelegateParameterArrayType = BuildArrayType("EventDelegate.Parameter");
        var eventDelegateListType = BuildListType("EventDelegate");
        var parameterInfoArrayType = BuildArrayType("System.Reflection.ParameterInfo");
        var objectArrayType = BuildArrayType("System.Object");
        var boolArrayType = BuildArrayType("System.Boolean");
        var stringArrayType = BuildArrayType("System.String");
        var typeArrayType = BuildArrayType("System.Type");
        var colorListType = BuildListType("UnityEngine.Color");
        var listObjectType = BuildListType("System.Object");
        var socketIoPacketListType = BuildListType("BestHTTP.SocketIO.Packet");
        var signalRMessageListType = BuildListType("BestHTTP.SignalRCore.Messages.Message");
        var actionObjectArrayType = BuildClosedGenericType("System.Action`1", objectArrayType);
        var actionSignalRMessageType = BuildClosedGenericType("System.Action`1", "BestHTTP.SignalRCore.Messages.Message");
        var actionTransportStatesPairType = BuildClosedGenericType("System.Action`2", "BestHTTP.SignalRCore.TransportStates", "BestHTTP.SignalRCore.TransportStates");
        const string bufferSegmentType = "BestHTTP.PlatformSupport.Memory.BufferSegment";
        var stackVector2ListArrayType = string.IsNullOrWhiteSpace(vector2ListType) ? null : $"System.Collections.Generic.Stack<{vector2ListType}>[]";
        var stackVector3ListArrayType = string.IsNullOrWhiteSpace(_unityVector3TypeName) ? null : $"System.Collections.Generic.Stack<{BuildListType(_unityVector3TypeName)!}>[]";
        var stackColorListArrayType = string.IsNullOrWhiteSpace(colorListType) ? null : $"System.Collections.Generic.Stack<{colorListType}>[]";
        var linkedVector2ListType = string.IsNullOrWhiteSpace(vector2ListType) ? null : $"System.Collections.Generic.LinkedList<{vector2ListType}>";
        var linkedVector3ListType = string.IsNullOrWhiteSpace(_unityVector3TypeName) ? null : $"System.Collections.Generic.LinkedList<{BuildListType(_unityVector3TypeName)!}>";
        var linkedColorListType = string.IsNullOrWhiteSpace(colorListType) ? null : $"System.Collections.Generic.LinkedList<{colorListType}>";
        const string genericStackListArrayType = "System.Collections.Generic.Stack<System.Collections.Generic.List<T>>[]";
        const string genericLinkedListType = "System.Collections.Generic.LinkedList<System.Collections.Generic.List<T>>";
        const string genericListType = "System.Collections.Generic.List<T>";
        const string repurchasableProductListType = "System.Collections.Generic.List<System.ValueTuple<MX.GameLogic.DBModel.PurchaseCountDB, MX.GameLogic.DBModel.MonthlyProductPurchaseDB>>";
        const string furnitureTimelineStateListType = "System.Collections.Generic.List<System.ValueTuple<FurnitureObject.FurnitureTimelineType, System.String>>";
        const string furnitureExcelType = "MX.Data.Excel.FurnitureExcel";
        const string inventoryObjectBaseFurnitureType = "InventoryObjectBase<FurnitureObject>";
        const string assetObjectBaseType = "AssetObjectBase";
        const string genericItemType = "T";
        const string genericItemArrayType = "T[]";
        const string genericEnumeratorType = "System.Collections.Generic.IEnumerator<T>";
        const string compareFuncType = "CompareFunc<T>";
        var forceReferenceTypes =
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

        string? DesiredFieldType(string identifier) => type.FullName switch
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

        var adjustedFields = fields.Select(field =>
        {
            var desiredType = DesiredFieldType(field.Identifier);
            var adjustedField = desiredType is null
                ? field
                : field with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(field.TypeName, desiredType) };

            if ((isAutoUseRuleDao || isConstraintStruct || isAreaCollisionProperty || isPositionSetting) &&
                string.Equals(field.Identifier, "Empty", StringComparison.Ordinal))
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "static", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            if (isFurnitureFilter &&
                (string.Equals(field.Identifier, "CategoryList", StringComparison.Ordinal) ||
                 string.Equals(field.Identifier, "SubCategoryList", StringComparison.Ordinal)))
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            if (isBitPackFormatter && field.Identifier == "Default")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "static", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isWebRequestUtils && field.Identifier == "domainRegex")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["private", "static"],
                    Accessibility = ExportMemberAccessibility.Private,
                };
            }
            else if (isFlatBuffersByteBuffer)
            {
                adjustedField = field.Identifier switch
                {
                    "_buffer" => adjustedField with { Modifiers = ["protected"], Accessibility = ExportMemberAccessibility.Protected },
                    "_pos" or "floathelper" or "inthelper" or "doublehelper" or "ulonghelper"
                        => adjustedField with { Modifiers = ["private"], Accessibility = ExportMemberAccessibility.Private },
                    _ => adjustedField,
                };
            }
            else if (isAddTypeMenuAttribute)
            {
                adjustedField = field.Identifier switch
                {
                    "_MenuName_k__BackingField" or "_Order_k__BackingField" => adjustedField with
                    {
                        Modifiers = ["private", "readonly"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "k_Separeters" => adjustedField with
                    {
                        Modifiers = ["private", "static", "readonly"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    _ => adjustedField,
                };
            }
            else if (isGenericGraphNodeMetadata)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isSkeletonAnimationPlayableHandle && field.Identifier == "skeletonAnimation")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isSignalRCoreStreamItemContainer)
            {
                adjustedField = field.Identifier switch
                {
                    "id" => adjustedField with
                    {
                        Modifiers = ["public", "readonly"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    "_Items_k__BackingField" or "<Items>k__BackingField" or "_LastAdded_k__BackingField" or "<LastAdded>k__BackingField" => adjustedField with
                    {
                        Modifiers = ["private"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "IsCanceled" => adjustedField with
                    {
                        Modifiers = ["public"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    _ => adjustedField,
                };
            }
            else if (isSignalRCoreCallbackDescriptor || isSignalRCoreInvocationDefinition)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isSocketIO3EventsCallbackDescriptor)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isSocketIO3EventsSubscription && field.Identifier == "callbacks")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isBestHttpCoreConnectionEventInfo || isBestHttpCoreRequestEventInfo)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isBestHttpCoreConnectionEventHelper || isBestHttpCoreRequestEventHelper)
            {
                adjustedField = field.Identifier switch
                {
                    "connectionEventQueue" or "requestEventQueue" => adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "OnEvent" => adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    _ => adjustedField,
                };
            }
            else if (isBestHttpCoreHostConnection)
            {
                adjustedField = field.Identifier switch
                {
                    "Connections" or "Queue" => adjustedField with
                    {
                        Modifiers = ["private"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    _ => adjustedField,
                };
            }
            else if (isBestHttpCoreHostDefinition)
            {
                adjustedField = field.Identifier switch
                {
                    "Alternates" or "hostConnectionVariant" => adjustedField with
                    {
                        Modifiers = ["public"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    "keyBuilder" or "keyBuilderLock" => adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    _ => adjustedField,
                };
            }
            else if (isBestHttpCoreHostConnectionKey)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isBestHttpCorePluginEventInfo ||
                     isBestHttpCoreAltSvcEventInfo ||
                     isBestHttpCoreHttp2ConnectProtocolInfo ||
                     isBestHttpCoreProtocolEventInfo)
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public", "readonly"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }
            else if (isBestHttpCorePluginEventHelper)
            {
                adjustedField = field.Identifier switch
                {
                    "pluginEvents" => adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "OnEvent" => adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    _ => adjustedField,
                };
            }
            else if (isBestHttpCoreProtocolEventHelper)
            {
                adjustedField = field.Identifier switch
                {
                    "protocolEvents" or "ActiveProtocols" => adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    },
                    "OnEvent" => adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    },
                    _ => adjustedField,
                };
            }

            if (isFurnitureInventoryObject &&
                string.Equals(field.Identifier, "filterOption", StringComparison.Ordinal))
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["protected"],
                    Accessibility = ExportMemberAccessibility.Protected,
                };
            }

            if (isFurnitureObject)
            {
                if (field.Identifier is "Category" or "SubCategory")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["public"],
                        Accessibility = ExportMemberAccessibility.Public,
                    };
                }
                else if (field.Identifier is "_InvalidId_k__BackingField" or "<InvalidId>k__BackingField")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static", "readonly"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
                else if (field.Identifier is
                    "_CafeDBId_k__BackingField" or
                    "<CafeDBId>k__BackingField" or
                    "_Location_k__BackingField" or
                    "<Location>k__BackingField" or
                    "_Tags_k__BackingField" or
                    "<Tags>k__BackingField" or
                    "_DB_k__BackingField" or
                    "<DB>k__BackingField" or
                    "_LeftTop_k__BackingField" or
                    "<LeftTop>k__BackingField" or
                    "_RightBottom_k__BackingField" or
                    "<RightBottom>k__BackingField" or
                    "availableCharacterStates" or
                    "furnitureExcel" or
                    "rotationDegree" or
                    "position")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
            }

            if (isByteReader && field.Identifier == "mTemp")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["private", "static"],
                    Accessibility = ExportMemberAccessibility.Private,
                };
            }

            if (isBetterList && field.Identifier is "buffer" or "size")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            if (isBmGlyph &&
                field.Identifier is "index" or "x" or "y" or "width" or "height" or "offsetX" or "offsetY" or "advance" or "channel" or "kerning")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            if (isBmSymbol && field.Identifier is "sequence" or "spriteName")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["public"],
                    Accessibility = ExportMemberAccessibility.Public,
                };
            }

            if (isNguiText)
            {
                if (field.Identifier is
                    "bitmapFont" or "dynamicFont" or "glyph" or "fontSize" or "fontScale" or "pixelDensity" or "fontStyle" or
                    "alignment" or "tint" or "rectWidth" or "rectHeight" or "regionWidth" or "regionHeight" or "maxLines" or
                    "gradient" or "gradientBottom" or "gradientTop" or "encoding" or "spacingX" or "spacingY" or "premultiply" or
                    "symbolStyle" or "finalSize" or "finalSpacingX" or "finalLineHeight" or "baseline" or "useSymbols")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    };
                }
                else if (field.Identifier is "mInvisible" or "mColors" or "mAlpha" or "mTempChar" or "mSizes" or "s_c0" or "s_c1" or "sizeShrinkage" or "mBoldOffset")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
            }

            if (isUiDrawCall)
            {
                if (field.Identifier is "mActiveList" or "mInactiveList" or "mColorSpace" or "ClipRange" or "ClipArgs" or "ClipParams" or "dx9BugWorkaround")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
                else if (field.Identifier == "maxIndexBufferCache")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static", "const"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
                else if (field.Identifier == "mCache")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    };
                }
                else if (field.Identifier == "mBlock")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["protected"],
                        Accessibility = ExportMemberAccessibility.Protected,
                    };
                }
                else if (field.Identifier is "widgetCount" or "depthStart" or "depthEnd" or "manager" or "panel" or "clipTexture" or "alwaysOnScreen" or "verts" or "norms" or "tans" or "uvs" or "clipUVs" or "uv2" or "cols" or "isDirty" or "onRender" or "onCreateDrawCall")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["public"],
                        Accessibility = ExportMemberAccessibility.Public,
                    };
                }
                else
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
            }

            if (isEventDelegate)
            {
                if (field.Identifier == "oneShot")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["public"],
                        Accessibility = ExportMemberAccessibility.Public,
                    };
                }
                else if (field.Identifier == "s_Hash")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
            }

            if (isPropertyReference && field.Identifier == "s_Hash")
            {
                adjustedField = adjustedField with
                {
                    Modifiers = ["private", "static"],
                    Accessibility = ExportMemberAccessibility.Private,
                };
            }

            if (isCachedGeometries)
            {
                if (field.Identifier is "SMALL_LIST_COUNT" or "smallListCapacityLimit")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static", "const"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
                else if (field.Identifier is
                    "cachedListsOfVector2List" or
                    "cachedBigListsOfVector2List" or
                    "cachedListsOfVector3List" or
                    "cachedBigListsOfVector3List" or
                    "cachedListsOfColorList" or
                    "cachedBigListsOfColorList")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["public", "static"],
                        Accessibility = ExportMemberAccessibility.Public,
                    };
                }
            }

            if (isEventDelegateParameter)
            {
                if (field.Identifier is "obj" or "field" or "expectedType" or "cached" or "propInfo" or "fieldInfo")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["public"],
                        Accessibility = ExportMemberAccessibility.Public,
                    };
                }
            }

            if (isRuntimeInspectorUtils)
            {
                if (field.Identifier is
                    "typeToVariables" or
                    "typeToExposedMethods" or
                    "commonSerializableTypes" or
                    "validVariablesList" or
                    "typesToSearchForVariablesList" or
                    "propertyNamesInVariablesList" or
                    "exposedMethodsList" or
                    "exposedExtensionMethods" or
                    "customEditorAttributes" or
                    "draggedReferenceItemsPool")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static", "readonly"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
                else if (field.Identifier == "customEditors")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
                else if (field.Identifier == "IgnoredTransformsInHierarchy")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["public", "static", "readonly"],
                        Accessibility = ExportMemberAccessibility.Public,
                    };
                }
                else if (field.Identifier is "popupCanvas" or "popupReferenceCanvas" or "tooltipPopup")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
                else if (field.Identifier is "numberFormat" or "stringBuilder")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["internal", "static", "readonly"],
                        Accessibility = ExportMemberAccessibility.Internal,
                    };
                }
            }

            if (isWwwForm)
            {
                if (field.Identifier is "dDash" or "crlf" or "contentTypeHeader" or "dispositionHeader" or "endQuote" or "fileNameField" or "ampersand" or "equal")
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private", "static"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
                else
                {
                    adjustedField = adjustedField with
                    {
                        Modifiers = ["private"],
                        Accessibility = ExportMemberAccessibility.Private,
                    };
                }
            }

            return adjustedField;
        }).ToArray();

        string? DesiredPropertyType(string identifier) => type.FullName switch
        {
            "AccountBillingInfo" => identifier switch
            {
                "MonthlyProductRewards" => monthlyProductRewardsType,
                "RepurchasableProductPurchaseCountDBList" => purchaseCountDbListType,
                "RepurchasableProductList" => repurchasableProductListType,
                "NewProductList" => purchaseCountDbListType,
                "PurchaseCountList" => purchaseCountDbListType,
                "BlockedProductList" => blockedProductDbListType,
                _ => null,
            },
            "ByteReader" => identifier switch
            {
                _ => null,
            },
            "BMFont" => identifier switch
            {
                "glyphs" => bmGlyphListType,
                _ => null,
            },
            "UIDrawCall" => identifier switch
            {
                "list" or "activeList" or "inactiveList" => uiDrawCallListType,
                "cachedTransform" => transformType,
                "baseMaterial" or "dynamicMaterial" => materialType,
                _ => null,
            },
            _ when isBetterList => identifier switch
            {
                "Item" => genericItemType,
                _ => null,
            },
            "EventDelegate" => identifier switch
            {
                "target" => "UnityEngine.MonoBehaviour",
                "methodName" => "System.String",
                "parameters" => eventDelegateParameterArrayType,
                _ => null,
            },
            "FurnitureObject" => identifier switch
            {
                "CafeDBId" => "System.Int64",
                "LevelUpFeedCostAmount" => "System.Int64",
                "LevelUpFeedExp" => "System.Int64",
                "SetGroupId" => "System.Int64",
                "Tags" => furnitureTagsDictionaryType,
                "AvailableCharacterStates" => furnitureTimelineStateListType,
                "FurnitureExcel" => furnitureExcelType,
                "InvalidId" => "System.Int64",
                _ => null,
            },
            _ when isFurnitureFilter => identifier switch
            {
                _ => null,
            },
            _ when isWwwForm => identifier switch
            {
                "headers" => BuildDictionaryType("System.String", "System.String"),
                "data" => byteArrayType,
                _ => null,
            },
            _ when isSignalRCoreUploadItemController => identifier switch
            {
                "StreamingIDs" => stringArrayType,
                "Hub" => _hubConnectionTypeName,
                _ => null,
            },
            _ when isBestHttpCoreHostConnection => identifier switch
            {
                "LastProtocolSupportUpdate" => "System.DateTime",
                _ => null,
            },
            _ when isSignalRCoreStreamItemContainer => identifier switch
            {
                "Items" => genericListType,
                "LastAdded" => genericItemType,
                _ => null,
            },
            _ when isSocketIO3EventsTypedEventTable => identifier switch
            {
                _ => null,
            },
            _ => null,
        };

        var adjustedProperties = properties.Select(property =>
        {
            var desiredType = DesiredPropertyType(property.DisplayName);
            return desiredType is null
                ? property
                : property with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(property.TypeName, desiredType) };
        }).ToArray();

        var adjustedMethods = methods.Select(method =>
        {
            var adjustedParameters = method.Parameters.Select(parameter =>
            {
                string? desiredType = null;
                var modifierPrefix = parameter.ModifierPrefix;

                switch (type.FullName)
                {
                    case "AccountBillingInfo":
                        if (method.DisplayName is "set_MonthlyProductRewards" && parameter.Identifier == "value")
                        {
                            desiredType = monthlyProductRewardsType;
                        }
                        else if (method.DisplayName is "set_RepurchasableProductPurchaseCountDBList" && parameter.Identifier == "value")
                        {
                            desiredType = purchaseCountDbListType;
                        }
                        else if (method.DisplayName is "set_RepurchasableProductList" && parameter.Identifier == "value")
                        {
                            desiredType = repurchasableProductListType;
                        }
                        else if (method.DisplayName is "set_NewProductList" or "set_PurchaseCountList" && parameter.Identifier == "value")
                        {
                            desiredType = purchaseCountDbListType;
                        }
                        else if (method.DisplayName is "set_BlockedProductList" && parameter.Identifier == "value")
                        {
                            desiredType = blockedProductDbListType;
                        }
                        break;
                    case "EventDelegate":
                        if ((method.DisplayName is "get_target" or "set_target") && parameter.Identifier == "value")
                        {
                            desiredType = "UnityEngine.MonoBehaviour";
                        }
                        else if ((method.DisplayName is "get_methodName" or "set_methodName") && parameter.Identifier == "value")
                        {
                            desiredType = "System.String";
                        }
                        if ((method.DisplayName is "Execute" or "IsValid" or "Set" or "Add" or "Remove") &&
                            parameter.Identifier == "list")
                        {
                            desiredType = eventDelegateListType;
                        }
                        break;
                    case "BMSymbol":
                        if (method.DisplayName == "Validate" && parameter.Identifier == "atlas")
                        {
                            desiredType = "INGUIAtlas";
                        }
                        break;
                    case var _ when isRuntimeInspectorUtils:
                        if (method.DisplayName == "GetTexture" && parameter.Identifier == "obj")
                        {
                            desiredType = "UnityEngine.Object";
                        }
                        else if (method.DisplayName == "Tint" && parameter.Identifier == "color")
                        {
                            desiredType = colorType;
                        }
                        else if ((method.DisplayName == "ShowTooltip" || method.DisplayName == "CreateDraggedReferenceItem") &&
                                 parameter.Identifier == "skin")
                        {
                            desiredType = uiSkinType;
                        }
                        else if (method.DisplayName == "CreateDraggedReferenceItem" && parameter.Identifier == "reference")
                        {
                            desiredType = "UnityEngine.Object";
                        }
                        else if (method.DisplayName == "CreateDraggedReferenceItem" && parameter.Identifier == "references")
                        {
                            desiredType = unityObjectArrayType;
                        }
                        else if ((method.DisplayName == "GetAllVariables" || method.DisplayName == "HasAttribute" || method.DisplayName == "HasAttribute<T>" || method.DisplayName == "GetAttribute" || method.DisplayName == "GetAttribute<T>" || method.DisplayName == "GetAttributes" || method.DisplayName == "GetAttributes<T>") &&
                                 parameter.Identifier == "variable")
                        {
                            desiredType = "System.Reflection.MemberInfo";
                        }
                        else if ((method.DisplayName == "IsEmptyForDev" || method.DisplayName == "IsEmptyForDev<T>") && parameter.Identifier == "objects")
                        {
                            desiredType = "System.Collections.Generic.IList<T>";
                        }
                        break;
                    case var _ when isHubConnectionExtensions:
                        if (parameter.Identifier == "args")
                        {
                            desiredType = objectArrayType;
                        }
                        break;
                    case var _ when isUploadItemControllerExtensions:
                        desiredType = parameter.Identifier switch
                        {
                            "controller" => "BestHTTP.SignalRCore.UpStreamItemController<TResult>",
                            "item" or "param1" => "P1",
                            "param2" => "P2",
                            "param3" => "P3",
                            "param4" => "P4",
                            "param5" => "P5",
                            _ => desiredType,
                        };
                        break;
                    case var _ when (isSystemActionDelegate || isSystemFuncDelegate):
                        if (method.DisplayName == "Invoke" &&
                            parsedSafeGeneric is { Args: var genericArgs } &&
                            int.TryParse(parameter.Identifier.TrimStart('a', 'r', 'g'), out var argOrdinal) &&
                            argOrdinal >= 1)
                        {
                            var desiredIndex = argOrdinal - 1;
                            var availableCount = isSystemFuncDelegate ? genericArgs.Count - 1 : genericArgs.Count;
                            if (desiredIndex >= 0 && desiredIndex < availableCount)
                                desiredType = genericArgs[desiredIndex];
                        }
                        break;
                    case "NGUIText":
                        if (method.DisplayName is "EncodeColor" or "EncodeColor24" or "EncodeColor32")
                        {
                            if (parameter.Identifier == "c")
                                desiredType = colorType;
                        }
                        else if (method.DisplayName == "ParseSymbol" && parameter.Identifier == "colors")
                        {
                            desiredType = betterListColorType;
                        }
                        else if (method.DisplayName == "Align" && parameter.Identifier == "verts")
                        {
                            desiredType = vector3ListType;
                        }
                        else if ((method.DisplayName == "GetExactCharacterIndex" || method.DisplayName == "GetApproximateCharacterIndex") &&
                                 parameter.Identifier == "verts")
                        {
                            desiredType = vector3ListType;
                        }
                        else if ((method.DisplayName == "GetExactCharacterIndex" || method.DisplayName == "GetApproximateCharacterIndex") &&
                                 parameter.Identifier == "indices")
                        {
                            desiredType = intListType;
                        }
                        else if ((method.DisplayName == "GetExactCharacterIndex" || method.DisplayName == "GetApproximateCharacterIndex") &&
                                 parameter.Identifier == "pos")
                        {
                            desiredType = _unityVector2TypeName;
                        }
                        else if ((method.DisplayName == "EndLine" || method.DisplayName == "ReplaceSpaceWithNewline") &&
                                 parameter.Identifier == "s")
                        {
                            desiredType = stringBuilderType;
                        }
                        else if (method.DisplayName == "SplitTextChunk" && parameter.Identifier == "extracted")
                        {
                            desiredType = "System.String";
                            modifierPrefix = "out";
                        }
                        else if (method.DisplayName == "WrapText" && parameter.Identifier == "finalText")
                        {
                            desiredType = "System.String";
                            modifierPrefix = "out";
                        }
                        else if (method.DisplayName == "Print")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "verts" => vector3ListType,
                                "uvs" => vector2ListType,
                                "cols" => colorListType,
                                _ => desiredType,
                            };
                        }
                        else if ((method.DisplayName == "PrintApproximateCharacterPositions" || method.DisplayName == "PrintExactCharacterPositions") &&
                                 parameter.Identifier == "verts")
                        {
                            desiredType = vector3ListType;
                        }
                        else if ((method.DisplayName == "PrintApproximateCharacterPositions" || method.DisplayName == "PrintExactCharacterPositions") &&
                                 parameter.Identifier == "indices")
                        {
                            desiredType = intListType;
                        }
                        else if (method.DisplayName == "PrintCaretAndSelection")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "caret" or "highlight" => vector3ListType,
                                _ => desiredType,
                            };
                        }
                        break;
                    case "UIDrawCall":
                        if (method.DisplayName is "set_baseMaterial" && parameter.Identifier == "value")
                        {
                            desiredType = materialType;
                        }
                        else if (method.DisplayName is "set_mainTexture" && parameter.Identifier == "value")
                        {
                            desiredType = textureType;
                        }
                        else if (method.DisplayName is "set_shader" && parameter.Identifier == "value")
                        {
                            desiredType = "UnityEngine.Shader";
                        }
                        break;
                    case var _ when isBestHttpCoreConnectionEventInfo:
                        if (method.DisplayName == ".ctor")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "sourceConn" => "BestHTTP.Connections.ConnectionBase",
                                "event" => "BestHTTP.Core.ConnectionEvents",
                                "newState" => "BestHTTP.Connections.HTTPConnectionStates",
                                "protocolSupport" => "BestHTTP.Core.HostProtocolSupport",
                                "request" => "BestHTTP.HTTPRequest",
                                _ => desiredType,
                            };
                        }
                        break;
                    case var _ when isBestHttpCoreHostConnection:
                        if (method.DisplayName == "set_LastProtocolSupportUpdate" && parameter.Identifier == "value")
                        {
                            desiredType = "System.DateTime";
                        }
                        break;
                    case var _ when isBestHttpCoreHostConnectionKey:
                        if (method.DisplayName == ".ctor")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "host" or "connection" => "System.String",
                                _ => desiredType,
                            };
                        }
                        break;
                    case var _ when isBestHttpCoreRequestEventInfo:
                        if (method.DisplayName == ".ctor")
                        {
                            desiredType = parameter.Identifier switch
                            {
                                "request" => "BestHTTP.HTTPRequest",
                                "event" => "BestHTTP.Core.RequestEvents",
                                "newState" => "BestHTTP.HTTPRequestStates",
                                "progress" or "progressLength" => "System.Int64",
                                "data" => "System.Byte[]",
                                "dataLength" => "System.Int32",
                                _ => desiredType,
                            };
                        }
                        break;
                    case var _ when isBestHttpCoreRequestEventHelper:
                        if (method.DisplayName == "AbortRequestWhenTimedOut" && parameter.Identifier == "now")
                        {
                            desiredType = "System.DateTime";
                        }
                        else if (method.DisplayName == "AbortRequestWhenTimedOut" && parameter.Identifier == "context")
                        {
                            desiredType = "System.Object";
                        }
                        break;
                    default:
                        if (isBetterList)
                        {
                            if ((method.DisplayName is "get_Item" or "set_Item" or "Insert") &&
                                (parameter.Identifier == "i" || parameter.Identifier == "index"))
                            {
                                desiredType = "System.Int32";
                            }
                            else if (method.DisplayName is "set_Item" or "Add" or "Insert" or "Contains" or "IndexOf" or "Remove")
                            {
                                if (parameter.Identifier is "value" or "item")
                                    desiredType = genericItemType;
                            }
                            else if (method.DisplayName == "Sort" && parameter.Identifier == "comparer")
                            {
                                desiredType = compareFuncType;
                            }
                        }
                        else if (isPropertyReference)
                        {
                            if (((method.DisplayName == "set_target") && parameter.Identifier == "value") ||
                                ((method.DisplayName is ".ctor" or "Set") && parameter.Identifier == "target") ||
                                (method.DisplayName == "ToString" && parameter.Identifier == "comp"))
                            {
                                desiredType = "UnityEngine.Component";
                            }
                            else if (((method.DisplayName == "set_name") && parameter.Identifier == "value") ||
                                     (method.DisplayName == ".ctor" && parameter.Identifier == "fieldName") ||
                                     (method.DisplayName == "Set" && parameter.Identifier == "methodName") ||
                                     (method.DisplayName == "ToString" && parameter.Identifier == "property"))
                            {
                                desiredType = "System.String";
                            }
                            else if (method.DisplayName.StartsWith("Convert", StringComparison.Ordinal))
                            {
                                if (parameter.Identifier is "to" or "from")
                                    desiredType = "System.Type";
                                else if (parameter.Identifier == "value")
                                    desiredType = "System.Object";
                            }
                            else if (method.DisplayName == "Equals" && parameter.Identifier == "obj")
                            {
                                desiredType = "System.Object";
                            }
                        }
                        break;
                    case "CachedGeometries":
                        if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                            parameter.Identifier == "cache")
                        {
                            desiredType = genericStackListArrayType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "bigCache")
                        {
                            desiredType = genericLinkedListType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "source")
                        {
                            desiredType = genericListType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "verts")
                        {
                            desiredType = BuildListType(_unityVector3TypeName);
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 (parameter.Identifier == "uvs" || parameter.Identifier == "clipUVs"))
                        {
                            desiredType = vector2ListType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "cols")
                        {
                            desiredType = colorListType;
                        }
                        else if ((method.DisplayName == "PushToCachedGeometries" || method.DisplayName == "PullFromCachedGeometries") &&
                                 parameter.Identifier == "mRtpVerts")
                        {
                            desiredType = BuildListType(_unityVector3TypeName);
                        }
                        break;
                    case "ByteReader":
                        if (method.DisplayName == "ReadLine" && parameter.Identifier == "buffer")
                        {
                            desiredType = "System.Byte[]";
                        }
                        break;
                    case "MX.Logic.Data.TacticRoleConstraint":
                        if (method.DisplayName == "IsMatch" && parameter.Identifier == "tacticRole")
                            desiredType = "FlatData.TacticRole";
                        break;
                    case "MX.Data.GroundObstacleData":
                        if ((method.DisplayName == "Equals" && parameter.Identifier == "other") ||
                            ((method.DisplayName == "op_Equality" || method.DisplayName == "op_Inequality") && (parameter.Identifier == "left" || parameter.Identifier == "right")))
                        {
                            desiredType = _groundObstacleDataTypeName;
                        }
                        break;
                    case "MX.Data.GroundObstacleDataCollection":
                        if (method.DisplayName == "GetKeyForItem" && parameter.Identifier == "item")
                            desiredType = _groundObstacleDataTypeName;
                        break;
                    case "MX.Data.GroundObstacleDataHashComparer":
                        if ((method.DisplayName == "Equals" && (parameter.Identifier == "x" || parameter.Identifier == "y")) ||
                            (method.DisplayName == "Compare" && (parameter.Identifier == "x" || parameter.Identifier == "rhs")) ||
                            (method.DisplayName == "GetHashCode" && parameter.Identifier == "obj"))
                        {
                            desiredType = _groundObstacleDataTypeName;
                        }
                        break;
                    case "GroundObstacleDataRepository":
                        if (method.DisplayName == "TryGetValue" && parameter.Identifier == "value")
                        {
                            desiredType = _groundObstacleDataTypeName;
                            modifierPrefix = "out";
                        }
                        break;
                    case "FurnitureInventoryObject":
                        if (method.DisplayName == "Sync" && parameter.Identifier == "tables")
                        {
                            desiredType = furnitureDbDictionaryType;
                        }
                        else if (method.DisplayName == "Sync" && parameter.Identifier == "list")
                        {
                            desiredType = furnitureDbListType;
                        }
                        else if (method.DisplayName == "HasListFromTag" && parameter.Identifier == "furnitures")
                        {
                            desiredType = furnitureObjectListType;
                            modifierPrefix = "out";
                        }
                        else if ((method.DisplayName == "GetPlacedFurnitures" && parameter.Identifier == "dbId") ||
                                 (method.DisplayName == "FindFurniture" && parameter.Identifier == "uniqueId"))
                        {
                            desiredType = "System.Int64";
                        }
                        break;
                    case "FurnitureObject":
                        if (method.DisplayName == "set_CafeDBId" && parameter.Identifier == "value")
                        {
                            desiredType = "System.Int64";
                        }
                        else if (method.DisplayName == "set_Tags" && parameter.Identifier == "value")
                        {
                            desiredType = furnitureTagsDictionaryType;
                        }
                        else if (method.DisplayName == "set_FurnitureExcel" && parameter.Identifier == "value")
                        {
                            desiredType = furnitureExcelType;
                        }
                        else if (method.DisplayName == "set_Position" && parameter.Identifier == "value")
                        {
                            desiredType = _unityVector2TypeName;
                        }
                        else if ((method.DisplayName == "set_LeftTop" || method.DisplayName == "set_RightBottom") &&
                                 parameter.Identifier == "value")
                        {
                            desiredType = _unityVector2TypeName;
                        }
                        break;
                }

                if (isEventDelegateParameter && method.DisplayName == ".ctor")
                {
                    if (parameter.Identifier == "obj")
                    {
                        desiredType = "UnityEngine.Object";
                    }
                    else if (parameter.Identifier == "field")
                    {
                        desiredType = "System.String";
                    }
                }

                return desiredType is null
                    ? parameter
                    : parameter with
                    {
                        TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType),
                        ModifierPrefix = modifierPrefix,
                    };
            }).ToArray();

            string? desiredReturnType = null;

            switch (type.FullName)
            {
                case "AccountBillingInfo":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_MonthlyProductRewards" => monthlyProductRewardsType,
                        "get_RepurchasableProductPurchaseCountDBList" => purchaseCountDbListType,
                        "get_RepurchasableProductList" => repurchasableProductListType,
                        "get_NewProductList" => purchaseCountDbListType,
                        "get_PurchaseCountList" => purchaseCountDbListType,
                        "get_BlockedProductList" => blockedProductDbListType,
                        "set_MonthlyProductRewards" or
                        "set_RepurchasableProductPurchaseCountDBList" or
                        "set_RepurchasableProductList" or
                        "set_NewProductList" or
                        "set_PurchaseCountList" or
                        "set_BlockedProductList" => "System.Void",
                        _ => null,
                    };
                    break;
                case "ByteReader":
                    desiredReturnType = method.DisplayName switch
                    {
                        "ReadDictionary" => stringDictionaryType,
                        "ReadCSV" => betterListStringType,
                        _ => null,
                    };
                    break;
                case "BMFont":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_glyphs" => bmGlyphListType,
                        _ => null,
                    };
                    break;
                case var _ when isRuntimeInspectorUtils:
                    desiredReturnType = method.DisplayName switch
                    {
                        "GetTexture" => textureType,
                        "Tint" => colorType,
                        "CreateDraggedReferenceItem" => draggedReferenceItemType,
                        "GetAllVariables" => memberInfoArrayType,
                        "GetExposedMethods" => exposedMethodArrayType,
                        "GetAssignableObjectFromDraggedReferenceItem" or "GetAssignableObjectFromDraggedReferenceItem<T>" when adjustedParameters.Length == 1 => "T",
                        "GetAssignableObjectFromDraggedReferenceItem" when adjustedParameters.Length == 2 => "System.Object",
                        "GetAssignableObjectsFromDraggedReferenceItem" or "GetAssignableObjectsFromDraggedReferenceItem<T>" when adjustedParameters.Length == 1 => "T[]",
                        "GetAssignableObjectsFromDraggedReferenceItem" when adjustedParameters.Length == 2 => "System.Object[]",
                        "GetAttribute" or "GetAttribute<T>" => "T",
                        "GetAttributes" or "GetAttributes<T>" => "T[]",
                        _ => null,
                    };
                    break;
                case var _ when isHubConnectionExtensions:
                    desiredReturnType = "BestHTTP.SignalRCore.UpStreamItemController<TResult>";
                    break;
                case var _ when isUploadItemControllerExtensions:
                    desiredReturnType = "System.Void";
                    break;
                case var _ when isBitPackFormatter:
                    desiredReturnType = method.DisplayName switch
                    {
                        "Serialize" or "Deserialize" => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSystemRuntimeUnsafe:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "T",
                        0x06000002 => "System.Void",
                        0x06000003 => "System.Void*",
                        0x06000004 => "System.Int32",
                        0x06000005 => "System.Void",
                        0x06000006 => "T",
                        0x06000007 => "T",
                        0x06000008 => "T",
                        0x06000009 => "TTo",
                        0x0600000A => "T",
                        0x0600000B => "T",
                        0x0600000C => "T",
                        0x0600000D => "System.IntPtr",
                        0x0600000E => "System.Boolean",
                        0x0600000F => "System.Boolean",
                        0x06000010 => "System.Boolean",
                        _ => null,
                    };
                    break;
                case var _ when isCommunityToolkitArrayExtensions:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000008 => "T",
                        0x06000009 => "T",
                        _ => null,
                    };
                    break;
                case var _ when isTimelineExtensions:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000388 => _unityVector2TypeName,
                        0x06000389 => _unityVector2TypeName,
                        0x0600038A => "System.Single",
                        0x0600038B => _unityVector2TypeName,
                        0x0600038C => "System.Single",
                        0x0600038D => "Spine.TranslateTimeline",
                        0x0600038E => "T",
                        0x0600038F => "Spine.TransformConstraintTimeline",
                        _ => null,
                    };
                    break;
                case var _ when isWebRequestUtils:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "System.String",
                        0x06000002 => "System.String",
                        0x06000003 => "System.String",
                        0x06000004 => "System.String",
                        0x06000005 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isJsonUtility:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "System.String",
                        0x06000002 => "System.Object",
                        0x06000003 => "System.String",
                        0x06000004 => "System.String",
                        0x06000005 => "T",
                        0x06000006 => "System.Object",
                        _ => null,
                    };
                    break;
                case var _ when isSocketIoJsonEncoder || isSocketIoDefaultJsonEncoder:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000382 => listObjectType,
                        0x06000383 => "System.String",
                        0x06000385 => listObjectType,
                        0x06000386 => "System.String",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreEncoder:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000511 => bufferSegmentType,
                        0x06000512 => "T",
                        0x06000513 => "System.Object",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreProtocol:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060005A6 => "System.String",
                        0x060005A7 => "BestHTTP.SignalRCore.TransferModes",
                        0x060005A8 => "BestHTTP.SignalRCore.IEncoder",
                        0x060005A9 => _hubConnectionTypeName,
                        0x060005AA => "System.Void",
                        0x060005AB => "System.Void",
                        0x060005AC => bufferSegmentType,
                        0x060005AD => objectArrayType,
                        0x060005AE => "System.Object",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreTransportInterface:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000508 => "BestHTTP.SignalRCore.TransferModes",
                        0x06000509 => "BestHTTP.SignalRCore.TransportTypes",
                        0x0600050A => "BestHTTP.SignalRCore.TransportStates",
                        0x0600050B => "System.String",
                        0x0600050C => "System.Void",
                        0x0600050D => "System.Void",
                        0x0600050E => "System.Void",
                        0x0600050F => "System.Void",
                        0x06000510 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreUploadItemController:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060005BB => stringArrayType,
                        0x060005BC => _hubConnectionTypeName,
                        0x060005BD => "System.Void",
                        0x060005BE => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isBestHttpCoreHostConnection:
                    if (method.DisplayName == "get_LastProtocolSupportUpdate")
                    {
                        desiredReturnType = "System.DateTime";
                    }
                    else if (method.DisplayName == "set_LastProtocolSupportUpdate")
                    {
                        desiredReturnType = "System.Void";
                    }
                    break;
                case var _ when isSignalRCoreStreamItemContainer:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000514 => genericListType,
                        0x06000515 => "System.Void",
                        0x06000516 => genericItemType,
                        0x06000517 => "System.Void",
                        0x06000518 => "System.Void",
                        0x06000519 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSocketIO3EventsCallbackDescriptor:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060004E2 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSocketIO3EventsSubscription:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060004E3 => "System.Void",
                        0x060004E4 => "System.Void",
                        0x060004E5 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSocketIO3EventsTypedEventTable:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x060004E6 => "BestHTTP.SocketIO3.Socket",
                        0x060004E7 => "System.Void",
                        0x060004E8 => "System.Void",
                        0x060004E9 => "BestHTTP.SocketIO3.Events.Subscription",
                        0x060004EA => "System.Void",
                        0x060004EB => "System.Void",
                        0x060004EC => "System.Void",
                        0x060004ED => "System.Void",
                        0x060004EE => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isFlatBuffersByteBuffer:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "System.Int32",
                        0x06000002 => "System.Void",
                        0x06000003 => "System.Void",
                        0x06000004 => "System.Int32",
                        0x06000005 => "System.Void",
                        0x06000006 => "System.Void",
                        0x06000007 => "System.Byte[]",
                        0x06000008 => "System.Byte[]",
                        0x06000009 => "System.ArraySegment<System.Byte>",
                        0x0600000A => "System.Void",
                        0x0600000B => "System.UInt64",
                        0x0600000C => "System.Void",
                        0x0600000D => "System.Void",
                        0x0600000E => "System.Void",
                        0x0600000F => "System.Void",
                        0x06000010 => "System.Void",
                        0x06000011 => "System.Void",
                        0x06000012 => "System.Void",
                        0x06000013 => "System.Void",
                        0x06000014 => "System.Void",
                        0x06000015 => "System.SByte",
                        0x06000016 => "System.Byte",
                        0x06000017 => "System.String",
                        0x06000018 => "System.Int16",
                        0x06000019 => "System.Int32",
                        0x0600001A => "System.UInt32",
                        0x0600001B => "System.Int64",
                        0x0600001C => "System.Single",
                        _ => null,
                    };
                    break;
                case var _ when isAddTypeMenuAttribute:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x06000001 => "System.String",
                        0x06000002 => "System.Int32",
                        0x06000003 => "System.Void",
                        0x06000004 => "System.String[]",
                        0x06000005 => "System.String",
                        0x06000006 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSignalRCoreCallbackDescriptor:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x0600051A => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isFutureCallback:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x0600425A => "System.Void",
                        0x0600425B => "System.Void",
                        0x0600425C => "System.IAsyncResult",
                        0x0600425D => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isFutureValueCallback:
                    desiredReturnType = method.Definition.Token switch
                    {
                        0x0600425E => "System.Void",
                        0x0600425F => "System.Void",
                        0x06004260 => "System.IAsyncResult",
                        0x06004261 => "System.Void",
                        _ => null,
                    };
                    break;
                case var _ when isSystemActionDelegate:
                    if (method.DisplayName == "Invoke")
                        desiredReturnType = "System.Void";
                    break;
                case var _ when isSystemFuncDelegate:
                    if (method.DisplayName == "Invoke" &&
                        parsedSafeGeneric is { Args: var genericArgs } &&
                        genericArgs.Count > 0)
                    {
                        desiredReturnType = genericArgs[^1];
                    }
                    break;
                case var _ when isWwwForm:
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_headers" => BuildDictionaryType("System.String", "System.String"),
                        "get_data" => byteArrayType,
                        _ => null,
                    };
                    break;
                case "NGUIText":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_isDynamic" => "System.Boolean",
                        "GetGlyph" => glyphInfoType,
                        "ParseColor" or "ParseColor24" or "ParseColor32" => colorType,
                        "CalculatePrintedSize" => _unityVector2TypeName,
                        _ => null,
                    };
                    break;
                case "UIDrawCall":
                    desiredReturnType = method.DisplayName switch
                    {
                        "get_list" or "get_activeList" or "get_inactiveList" => uiDrawCallListType,
                        "get_cachedTransform" => transformType,
                        "get_baseMaterial" or "get_dynamicMaterial" or "RebuildMaterial" => materialType,
                        _ => null,
                    };
                    break;
                default:
                    if (isBetterList)
                    {
                        desiredReturnType = method.DisplayName switch
                        {
                            "GetEnumerator" => genericEnumeratorType,
                            "get_Item" => genericItemType,
                            "Pop" => genericItemType,
                            "ToArray" => genericItemArrayType,
                            "Add" or "Insert" or "set_Item" => "System.Void",
                            "Contains" or "Remove" => "System.Boolean",
                            "IndexOf" => "System.Int32",
                            _ => null,
                        };
                    }
                    else if (isEventDelegate)
                    {
                        desiredReturnType = method.DisplayName switch
                        {
                            "get_target" => "UnityEngine.MonoBehaviour",
                            "get_methodName" => "System.String",
                            "set_target" or "set_methodName" => "System.Void",
                            "get_parameters" => eventDelegateParameterArrayType,
                            _ => null,
                        };
                    }
                    else if (isPropertyReference)
                    {
                        desiredReturnType = method.DisplayName switch
                        {
                            "get_target" => "UnityEngine.Component",
                            "get_name" => "System.String",
                            "set_target" or "set_name" => "System.Void",
                            _ => null,
                        };
                    }
                    break;
                case "FurnitureInventoryObject":
                    if (method.DisplayName == "GetLevelExp")
                    {
                        desiredReturnType = "System.Int64";
                    }
                    else if (method.DisplayName == "GetPlacedFurnitures" || method.DisplayName == "GetAllPlacedFurnitures")
                    {
                        desiredReturnType = furnitureObjectEnumerableType;
                    }
                    else if (method.DisplayName == "FindFurniture")
                    {
                        desiredReturnType = "FurnitureObject";
                    }
                    break;
                case "FurnitureObject":
                    if (method.DisplayName is "get_CafeDBId" or "get_LevelUpFeedCostAmount" or "get_LevelUpFeedExp" or "get_SetGroupId" or "get_InvalidId")
                    {
                        desiredReturnType = "System.Int64";
                    }
                    else if (method.DisplayName is "get_Tags")
                    {
                        desiredReturnType = furnitureTagsDictionaryType;
                    }
                    else if (method.DisplayName is "get_AvailableCharacterStates")
                    {
                        desiredReturnType = furnitureTimelineStateListType;
                    }
                    else if (method.DisplayName is "get_FurnitureExcel")
                    {
                        desiredReturnType = furnitureExcelType;
                    }
                    else if (method.DisplayName is "set_CafeDBId" or "set_Tags" or "set_FurnitureExcel" or "set_Position")
                    {
                        desiredReturnType = "System.Void";
                    }
                    break;
            }

            if (isEventDelegateParameter && method.DisplayName == ".ctor")
            {
                desiredReturnType = "System.Void";
            }

            if (isRuntimeInspectorUtils)
            {
                adjustedParameters = adjustedParameters.Select(parameter =>
                {
                    if (method.DisplayName is "GetAssignableObjectsFromDraggedReferenceItem" && parameter.Identifier == "assignableType")
                    {
                        return parameter with { TypeName = "System.Type" };
                    }

                    return parameter;
                }).ToArray();
            }

            if (isHubConnectionExtensions)
            {
                adjustedParameters = adjustedParameters.Select(parameter =>
                    parameter.Identifier == "args"
                        ? parameter with { TypeName = objectArrayType }
                        : parameter).ToArray();
            }
            else if (isUploadItemControllerExtensions)
            {
                adjustedParameters = adjustedParameters.Select(parameter =>
                {
                    var desiredType = parameter.Identifier switch
                    {
                        "controller" => "BestHTTP.SignalRCore.UpStreamItemController<TResult>",
                        "item" or "param1" => "P1",
                        "param2" => "P2",
                        "param3" => "P3",
                        "param4" => "P4",
                        "param5" => "P5",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = desiredType };
                }).ToArray();
            }
            else if (isBitPackFormatter)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.DisplayName switch
                    {
                        "Serialize" when index == 0 => _memoryPackWriterTypeName,
                        "Serialize" when parameter.Identifier == "value" => boolArrayType,
                        "Deserialize" when index == 0 => _memoryPackReaderTypeName,
                        "Deserialize" when parameter.Identifier == "value" => boolArrayType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSystemRuntimeUnsafe)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000001 when index == 0 => "System.Byte",
                        0x06000002 when index == 0 => "System.Byte",
                        0x06000002 when index == 1 => "T",
                        0x06000003 when index == 0 => "T",
                        0x06000005 when index == 0 => "System.Byte",
                        0x06000005 when index == 1 => "System.Byte",
                        0x06000005 when index == 2 => "System.UInt32",
                        0x06000006 when index == 0 => "System.Object",
                        0x06000007 when index == 0 => "System.Void*",
                        0x06000008 when index == 0 => "T",
                        0x06000009 when index == 0 => "TFrom",
                        0x0600000A when index == 0 => "T",
                        0x0600000A when index == 1 => "System.Int32",
                        0x0600000B when index == 0 => "T",
                        0x0600000B when index == 1 => "System.IntPtr",
                        0x0600000C when index == 0 => "T",
                        0x0600000C when index == 1 => "System.IntPtr",
                        0x0600000D when index == 0 => "T",
                        0x0600000D when index == 1 => "T",
                        0x0600000E when index <= 1 => "T",
                        0x0600000F when index <= 1 => "T",
                        0x06000010 when index == 0 => "T",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isCommunityToolkitArrayExtensions)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000008 when index == 0 => "T[]",
                        0x06000009 when index == 0 => "T[]",
                        0x06000009 when index == 1 => "System.Int32",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isTimelineExtensions)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000388 when index == 0 => "Spine.TranslateTimeline",
                        0x06000388 when index == 1 => "System.Single",
                        0x06000388 when index == 2 => "Spine.SkeletonData",
                        0x06000389 when index == 0 => "Spine.TranslateXTimeline",
                        0x06000389 when index == 1 => "Spine.TranslateYTimeline",
                        0x06000389 when index == 2 => "System.Single",
                        0x06000389 when index == 3 => "Spine.SkeletonData",
                        0x0600038A when index == 0 => "Spine.RotateTimeline",
                        0x0600038A when index == 1 => "System.Single",
                        0x0600038A when index == 2 => "Spine.SkeletonData",
                        0x0600038B when index == 0 => "Spine.TransformConstraintTimeline",
                        0x0600038B when index == 1 => "System.Single",
                        0x0600038C when index == 0 => "Spine.TransformConstraintTimeline",
                        0x0600038C when index == 1 => "System.Single",
                        0x0600038D when index == 0 => "Spine.Animation",
                        0x0600038D when index == 1 => "System.Int32",
                        0x0600038E when index == 0 => "Spine.Animation",
                        0x0600038E when index == 1 => "System.Int32",
                        0x0600038F when index == 0 => "Spine.Animation",
                        0x0600038F when index == 1 => "System.Int32",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isWebRequestUtils)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000001 when index <= 1 => "System.String",
                        0x06000002 when index <= 1 => "System.String",
                        0x06000003 when index == 0 => "System.Uri",
                        0x06000003 when index == 1 => "System.String",
                        0x06000003 when index == 2 => "System.Boolean",
                        0x06000004 when index == 0 => "System.String",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isJsonUtility)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000001 when index == 0 => "System.Object",
                        0x06000001 when index == 1 => "System.Boolean",
                        0x06000002 when index == 0 => "System.String",
                        0x06000002 when index == 1 => "System.Object",
                        0x06000002 when index == 2 => "System.Type",
                        0x06000003 when index == 0 => "System.Object",
                        0x06000004 when index == 0 => "System.Object",
                        0x06000004 when index == 1 => "System.Boolean",
                        0x06000005 when index == 0 => "System.String",
                        0x06000006 when index == 0 => "System.String",
                        0x06000006 when index == 1 => "System.Type",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIoTransportInterface)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000353 when index == 0 => "BestHTTP.SocketIO.Packet",
                        0x06000354 when index == 0 => socketIoPacketListType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIoJsonEncoder || isSocketIoDefaultJsonEncoder)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000382 when index == 0 => "System.String",
                        0x06000383 when index == 0 => listObjectType,
                        0x06000385 when index == 0 => "System.String",
                        0x06000386 when index == 0 => listObjectType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreEncoder)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000511 when index == 0 => "T",
                        0x06000512 when index == 0 => bufferSegmentType,
                        0x06000513 when index == 0 => "System.Type",
                        0x06000513 when index == 1 => "System.Object",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreProtocol)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060005AA when index == 0 => _hubConnectionTypeName,
                        0x060005AB when index == 0 => bufferSegmentType,
                        0x060005AB when index == 1 => signalRMessageListType,
                        0x060005AC when index == 0 => "BestHTTP.SignalRCore.Messages.Message",
                        0x060005AD when index == 0 => typeArrayType,
                        0x060005AD when index == 1 => objectArrayType,
                        0x060005AE when index == 0 => "System.Type",
                        0x060005AE when index == 1 => "System.Object",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreUploadItemController)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060005BD when index == 0 => "System.String",
                        0x060005BD when index == 1 => "T",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreStreamItemContainer)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000515 when index == 0 => genericListType,
                        0x06000517 when index == 0 => genericItemType,
                        0x06000518 when index == 0 => "System.Int64",
                        0x06000519 when index == 0 => genericItemType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreCallbackDescriptor)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x0600051A when index == 0 => typeArrayType,
                        0x0600051A when index == 1 => actionObjectArrayType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIO3EventsCallbackDescriptor)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060004E2 when index == 0 => typeArrayType,
                        0x060004E2 when index == 1 => actionObjectArrayType,
                        0x060004E2 when index == 2 => "System.Boolean",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIO3EventsSubscription)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060004E3 when index == 0 => typeArrayType,
                        0x060004E3 when index == 1 => actionObjectArrayType,
                        0x060004E3 when index == 2 => "System.Boolean",
                        0x060004E4 when index == 0 => actionObjectArrayType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSocketIO3EventsTypedEventTable)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x060004E8 when index == 0 => "BestHTTP.SocketIO3.Socket",
                        0x060004EA when index == 0 => "System.String",
                        0x060004EA when index == 1 => typeArrayType,
                        0x060004EA when index == 2 => actionObjectArrayType,
                        0x060004EA when index == 3 => "System.Boolean",
                        0x060004EB when index == 0 => "System.String",
                        0x060004EB when index == 1 => objectArrayType,
                        0x060004ED when index == 0 => "System.String",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isSignalRCoreTransportInterface)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x0600050C or 0x0600050D when index == 0 => actionTransportStatesPairType,
                        0x06000510 when index == 0 => bufferSegmentType,
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isFutureCallback)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x0600425A when index == 0 => "System.Object",
                        0x0600425A when index == 1 => "System.IntPtr",
                        0x0600425B when index == 0 => _futureInterfaceTypeName,
                        0x0600425C when index == 0 => _futureInterfaceTypeName,
                        0x0600425C when index == 1 => "System.AsyncCallback",
                        0x0600425C when index == 2 => "System.Object",
                        0x0600425D when index == 0 => "System.IAsyncResult",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isFutureValueCallback)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x0600425E when index == 0 => "System.Object",
                        0x0600425E when index == 1 => "System.IntPtr",
                        0x0600425F when index == 0 => "T",
                        0x06004260 when index == 0 => "T",
                        0x06004260 when index == 1 => "System.AsyncCallback",
                        0x06004260 when index == 2 => "System.Object",
                        0x06004261 when index == 0 => "System.IAsyncResult",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isFlatBuffersByteBuffer)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000002 when index == 0 => "System.Byte[]",
                        0x06000003 when index == 0 => "System.Byte[]",
                        0x06000003 when index == 1 => "System.Int32",
                        0x06000005 when index == 0 => "System.Int32",
                        0x06000006 when index == 0 => "System.Int32",
                        0x06000007 when index <= 1 => "System.Int32",
                        0x06000009 when index <= 1 => "System.Int32",
                        0x0600000A when index <= 1 => "System.Int32",
                        0x0600000A when index == 2 => "System.UInt64",
                        0x0600000B when index <= 1 => "System.Int32",
                        0x0600000C when index <= 1 => "System.Int32",
                        0x0600000D when index == 0 => "System.Int32",
                        0x0600000D when index == 1 => "System.SByte",
                        0x0600000E when index == 0 => "System.Int32",
                        0x0600000E when index == 1 => "System.Byte",
                        0x0600000F when index == 0 => "System.Int32",
                        0x0600000F when index == 1 => "System.Byte",
                        0x0600000F when index == 2 => "System.Int32",
                        0x06000010 when index == 0 => "System.Int32",
                        0x06000010 when index == 1 => "System.Int16",
                        0x06000011 when index == 0 => "System.Int32",
                        0x06000011 when index == 1 => "System.Int32",
                        0x06000012 when index == 0 => "System.Int32",
                        0x06000012 when index == 1 => "System.UInt32",
                        0x06000013 when index == 0 => "System.Int32",
                        0x06000013 when index == 1 => "System.Int64",
                        0x06000014 when index == 0 => "System.Int32",
                        0x06000014 when index == 1 => "System.Single",
                        0x06000015 when index == 0 => "System.Int32",
                        0x06000016 when index == 0 => "System.Int32",
                        0x06000017 when index <= 1 => "System.Int32",
                        0x06000018 when index == 0 => "System.Int32",
                        0x06000019 when index == 0 => "System.Int32",
                        0x0600001A when index == 0 => "System.Int32",
                        0x0600001B when index == 0 => "System.Int32",
                        0x0600001C when index == 0 => "System.Int32",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }
            else if (isAddTypeMenuAttribute)
            {
                adjustedParameters = adjustedParameters.Select((parameter, index) =>
                {
                    string? desiredType = method.Definition.Token switch
                    {
                        0x06000003 when index == 0 => "System.String",
                        0x06000003 when index == 1 => "System.Int32",
                        _ => null,
                    };

                    return desiredType is null
                        ? parameter
                        : parameter with { TypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(parameter.TypeName, desiredType) };
                }).ToArray();
            }

            if (isFurnitureFilter)
            {
                if (method.DisplayName == ".ctor")
                {
                    adjustedParameters = adjustedParameters.Select(parameter =>
                    {
                        string? parameterType = parameter.Identifier switch
                        {
                            "rarityList" => BuildListType("FlatData.Rarity"),
                            "tierList" => secureLongListType,
                            "gradeList" => BuildListType("System.Int32"),
                            "categoryList" => furnitureCategoryListType,
                            "subCategoryList" => furnitureSubCategoryListType,
                            _ => null,
                        };

                        return parameterType is null
                            ? parameter
                            : parameter with
                            {
                                TypeName = forceReferenceTypes ? parameterType! : PreferReferenceType(parameter.TypeName, parameterType),
                            };
                    }).ToArray();
                }
                else if (method.DisplayName == "IsShowAfterFiltering")
                {
                    adjustedParameters = adjustedParameters.Select(parameter =>
                        parameter.Identifier is "assetObject" or "P0"
                            ? parameter with { TypeName = assetObjectBaseType }
                            : parameter).ToArray();
                }
            }

            var adjustedDisplayName = method.DisplayName;
            if (isRuntimeInspectorUtils)
            {
                adjustedDisplayName = method.DisplayName switch
                {
                    "IsEmptyForDev" => "IsEmptyForDev<T>",
                    "GetAssignableObjectFromDraggedReferenceItem" when adjustedParameters.Length == 1 => "GetAssignableObjectFromDraggedReferenceItem<T>",
                    "GetAssignableObjectsFromDraggedReferenceItem" when adjustedParameters.Length == 1 => "GetAssignableObjectsFromDraggedReferenceItem<T>",
                    "HasAttribute" => "HasAttribute<T>",
                    "GetAttribute" => "GetAttribute<T>",
                    "GetAttributes" => "GetAttributes<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isHubConnectionExtensions)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x060004EF => "GetUpAndDownStreamController<TResult, T1>",
                    0x060004F0 => "GetUpAndDownStreamController<TResult, T1>",
                    0x060004F1 => "GetUpAndDownStreamController<TResult, T1, T2>",
                    0x060004F2 => "GetUpAndDownStreamController<TResult, T1, T2>",
                    0x060004F3 => "GetUpAndDownStreamController<TResult, T1, T2, T3>",
                    0x060004F4 => "GetUpAndDownStreamController<TResult, T1, T2, T3>",
                    0x060004F5 => "GetUpAndDownStreamController<TResult, T1, T2, T3, T4>",
                    0x060004F6 => "GetUpAndDownStreamController<TResult, T1, T2, T3, T4>",
                    0x060004F7 => "GetUpAndDownStreamController<TResult, T1, T2, T3, T4, T5>",
                    0x060004F8 => "GetUpAndDownStreamController<TResult, T1, T2, T3, T4, T5>",
                    0x060004F9 => "GetUpStreamController<TResult, T1>",
                    0x060004FA => "GetUpStreamController<TResult, T1>",
                    0x060004FB => "GetUpStreamController<TResult, T1, T2>",
                    0x060004FC => "GetUpStreamController<TResult, T1, T2>",
                    0x060004FD => "GetUpStreamController<TResult, T1, T2, T3>",
                    0x060004FE => "GetUpStreamController<TResult, T1, T2, T3>",
                    0x060004FF => "GetUpStreamController<TResult, T1, T2, T3, T4>",
                    0x06000500 => "GetUpStreamController<TResult, T1, T2, T3, T4>",
                    0x06000501 => "GetUpStreamController<TResult, T1, T2, T3, T4, T5>",
                    0x06000502 => "GetUpStreamController<TResult, T1, T2, T3, T4, T5>",
                    _ => method.DisplayName,
                };
            }
            else if (isUploadItemControllerExtensions)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000503 => "UploadParam<TResult, P1>",
                    0x06000504 => "UploadParam<TResult, P1, P2>",
                    0x06000505 => "UploadParam<TResult, P1, P2, P3>",
                    0x06000506 => "UploadParam<TResult, P1, P2, P3, P4>",
                    0x06000507 => "UploadParam<TResult, P1, P2, P3, P4, P5>",
                    _ => method.DisplayName,
                };
            }
            else if (isSystemRuntimeUnsafe)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000001 => "ReadUnaligned<T>",
                    0x06000002 => "WriteUnaligned<T>",
                    0x06000003 => "AsPointer<T>",
                    0x06000004 => "SizeOf<T>",
                    0x06000006 => "As<T>",
                    0x06000007 => "AsRef<T>",
                    0x06000008 => "AsRef<T>",
                    0x06000009 => "As<TFrom, TTo>",
                    0x0600000A => "Add<T>",
                    0x0600000B => "Add<T>",
                    0x0600000C => "AddByteOffset<T>",
                    0x0600000D => "ByteOffset<T>",
                    0x0600000E => "AreSame<T>",
                    0x0600000F => "IsAddressLessThan<T>",
                    0x06000010 => "IsNullRef<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isCommunityToolkitArrayExtensions)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000008 => "DangerousGetReference<T>",
                    0x06000009 => "DangerousGetReferenceAt<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isTimelineExtensions)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x0600038E => "FindTimelineForBone<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isJsonUtility)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000005 => "FromJson<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isSignalRCoreEncoder)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000511 => "Encode<T>",
                    0x06000512 => "DecodeAs<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isSignalRCoreUploadItemController)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x060005BD => "UploadParam<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isFutureCallback)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x0600425A => ".ctor",
                    0x0600425B => "Invoke",
                    0x0600425C => "BeginInvoke",
                    0x0600425D => "EndInvoke",
                    _ => method.DisplayName,
                };
            }
            else if (isFutureValueCallback)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x0600425E => ".ctor",
                    0x0600425F => "Invoke",
                    0x06004260 => "BeginInvoke",
                    0x06004261 => "EndInvoke",
                    _ => method.DisplayName,
                };
            }

            var adjustedMethod = method with
            {
                DisplayName = adjustedDisplayName,
                Parameters = adjustedParameters,
            };

            if (desiredReturnType is not null)
            {
                adjustedMethod = adjustedMethod with
                {
                    ReturnTypeName = forceReferenceTypes
                        ? desiredReturnType
                        : PreferReferenceType(adjustedMethod.ReturnTypeName, desiredReturnType),
                };
            }

            if (isFurnitureObject &&
                method.DisplayName is "set_LeftTop" or "set_RightBottom")
            {
                adjustedMethod = adjustedMethod with
                {
                    ReturnTypeName = "System.Void",
                    Modifiers = ["private"],
                    Accessibility = ExportMemberAccessibility.Private,
                };
            }

            if (isFurnitureFilter &&
                method.DisplayName == "<>iFixBaseProxy_IsShowAfterFiltering")
            {
                adjustedMethod = adjustedMethod with
                {
                    Parameters = adjustedMethod.Parameters.Select(parameter =>
                        parameter.Identifier == "P0"
                            ? parameter with { TypeName = assetObjectBaseType }
                            : parameter).ToArray(),
                };
            }

            return adjustedMethod;
        }).Select(method =>
        {
            string? desiredType = null;
            if (type.FullName == "FurnitureObject")
            {
                desiredType = method.DisplayName switch
                {
                    "get_CafeDBId" or "get_LevelUpFeedCostAmount" or "get_LevelUpFeedExp" or "get_SetGroupId" or "get_InvalidId" => "System.Int64",
                    "get_Tags" => furnitureTagsDictionaryType,
                    "get_AvailableCharacterStates" => furnitureTimelineStateListType,
                    "get_FurnitureExcel" => furnitureExcelType,
                    "set_CafeDBId" or "set_Tags" or "set_FurnitureExcel" or "set_Position" or "set_LeftTop" or "set_RightBottom" => "System.Void",
                    _ => null,
                };
            }
            else if (type.FullName == "FurnitureInventoryObject")
            {
                desiredType = method.DisplayName switch
                {
                    "GetLevelExp" => "System.Int64",
                    "GetPlacedFurnitures" or "GetAllPlacedFurnitures" => furnitureObjectEnumerableType,
                    "FindFurniture" => "FurnitureObject",
                    _ => null,
                };
            }

            return desiredType is null
                ? method
                : method with { ReturnTypeName = forceReferenceTypes ? desiredType! : PreferReferenceType(method.ReturnTypeName, desiredType) };
        }).ToArray();

        var adjustedEvents = events.Select(evt =>
        {
            if (isSignalRCoreTransportInterface && evt.DisplayName == "OnStateChanged")
            {
                return evt with
                {
                    TypeName = forceReferenceTypes
                        ? actionTransportStatesPairType ?? evt.TypeName
                        : PreferReferenceType(evt.TypeName, actionTransportStatesPairType),
                };
            }

            return evt;
        }).ToArray();

        return (relationships, adjustedFields, adjustedProperties, adjustedEvents, adjustedMethods);
    }

    private static bool IsFutureLikeType(TypeDefinition type, IReadOnlyList<MethodDefinition> methodRows)
    {
        if (!type.FullName.StartsWith("BestHTTP.", StringComparison.Ordinal))
            return false;

        var names = methodRows.Select(method => method.Name).ToHashSet(StringComparer.Ordinal);
        return names.Contains("get_state") &&
               names.Contains("get_value") &&
               names.Contains("get_error") &&
               names.Contains("OnItem") &&
               names.Contains("OnSuccess") &&
               names.Contains("OnError") &&
               names.Contains("OnComplete");
    }

    private static string TypeKind(TypeDefinition type)
    {
        if ((type.Bitfield & 0x20) != 0)
            return "interface";
        if ((type.Bitfield & 0x2) != 0)
            return "enum";
        if ((type.Bitfield & 0x8) != 0)
            return "struct";
        return "class";
    }

    private static string PreferSpecificType(string currentType, string desiredType)
    {
        if (string.IsNullOrWhiteSpace(desiredType))
            return currentType;
        if (string.IsNullOrWhiteSpace(currentType) ||
            currentType.StartsWith("Type_0x", StringComparison.Ordinal) ||
            currentType == "int" ||
            currentType == "float")
        {
            return desiredType;
        }

        return currentType;
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
