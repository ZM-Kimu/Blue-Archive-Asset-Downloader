namespace YldaDumpCsExporter;

internal sealed class YldaPrimitiveMemberSignatureResolver
{
    private readonly MetadataModel _model;
    private readonly YldaTypeResolver _typeResolver;
    private readonly YldaRelationshipResolver _relationshipResolver;
    private readonly TypeDescriptorIndex _descriptors;

    public YldaPrimitiveMemberSignatureResolver(
        MetadataModel model,
        YldaTypeResolver typeResolver,
        YldaRelationshipResolver relationshipResolver,
        TypeDescriptorIndex descriptors)
    {
        _model = model;
        _typeResolver = typeResolver;
        _relationshipResolver = relationshipResolver;
        _descriptors = descriptors;
    }

    public IReadOnlyList<ResolvedFieldModel> ResolveFields(
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


    public IReadOnlyList<ResolvedEventModel> ResolveEvents(
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

    public IReadOnlyList<ResolvedMethodModel> ResolveMethods(
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

    public string[] ResolveTypeGenericParameterNames(TypeDefinition type)
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

    private static bool? MergeOverrideEvidence(bool? current, bool? next)
    {
        if (next == true)
            return true;
        return current ?? next;
    }
}

