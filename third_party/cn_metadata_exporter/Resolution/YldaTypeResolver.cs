namespace YldaDumpCsExporter;

internal sealed class YldaTypeResolver
{
    private static readonly HashSet<string> PatchFileInfoDictionaryMemberNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "BundleDownloadDict",
        "SplitDownloadBundlesDict",
        "downloadBundlesDict",
        "bundleDownloadDict",
        "splitDownloadBundlesDict",
    };

    private static readonly HashSet<string> PatchFileInfoEnumerableMemberNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "ToBeDownload",
        "PrologueDownloads",
        "InGameDownloads",
        "BatchDownloadList",
        "PartialDownloadList",
        "BatchSplitDownloadList",
        "GetDownloadList",
        "assetHandles",
        "handleList",
    };

    private static readonly HashSet<string> PatchFileInfoListMemberNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "ToBeDownloadAsset",
        "ToBeDownloadTable",
        "ToBeDownloadMedia",
        "PrologueDownload",
        "PrologueDownloadAsset",
        "PrologueDownloadTable",
        "PrologueDownloadMedia",
        "patchFileInfos",
    };

    private static readonly HashSet<string> FurnitureReferenceMemberNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "FurnitureObject",
        "FindVisual",
        "furnitureVisual",
        "otherVisual",
        "visual",
        "furniture",
    };

    private static readonly HashSet<string> FurnitureVector2MemberNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Position",
        "LeftTop",
        "RightBottom",
        "GetPosition",
        "originalPosition",
        "targetPos",
        "pos",
    };

    private static readonly HashSet<string> FurnitureVector3MemberNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "localPos",
    };

    private static readonly HashSet<string> FurnitureLongLikeMemberNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "ServerId",
        "UniqueId",
        "serverId",
        "uniqueId",
        "furnitureId",
        "furnitureServerId",
        "furnitureUniqueId",
        "prevServerId",
        "newServerId",
    };

    private readonly MetadataModel _model;
    private readonly TypeDescriptorIndex _descriptors;
    private readonly Dictionary<uint, string> _globalTypeNames;
    private readonly HashSet<string> _typeFullNames;

    public YldaTypeResolver(MetadataModel model, TypeDescriptorIndex descriptors)
    {
        _model = model;
        _descriptors = descriptors;
        _typeFullNames = model.Types.Select(type => type.FullName).ToHashSet(StringComparer.Ordinal);

        var directTypeNames = BuildDirectTypeNameMap(model.Types);
        var metadataAwareTypeNames = BuildInferredTypeNameMap(model.Types, model.Methods, model.Parameters);
        var primitiveFieldTypeNames = BuildHeuristicPrimitiveTypeMap(model.Fields);
        var safeParameterTypeNames = BuildHeuristicParameterTypeMap(model.Parameters, includeIntLike: false);
        var intParameterTypeNames = BuildHeuristicParameterTypeMap(model.Parameters, includeIntLike: true);

        var coreSeedTypeNames = MergeTypeNameMaps(
            directTypeNames,
            metadataAwareTypeNames,
            primitiveFieldTypeNames);
        var seedTypeNames = MergeTypeNameMaps(coreSeedTypeNames, intParameterTypeNames);
        var contextualSeedTypeNames = MergeTypeNameMaps(coreSeedTypeNames, safeParameterTypeNames);
        var contextualTypeNames = BuildContextualParameterTypeMap(model.Types, model.Methods, model.Parameters, contextualSeedTypeNames);
        var seedWithContextualTypeNames = MergeTypeNameMaps(seedTypeNames, contextualTypeNames);
        var siblingContractTypeNames = BuildSiblingMethodTypeMap(
            model.Types,
            model.Methods,
            model.Parameters,
            seedWithContextualTypeNames);
        var seedWithContextualAndSiblingTypeNames = MergeTypeNameMaps(seedWithContextualTypeNames, siblingContractTypeNames);
        var flatBufferContractTypeNames = BuildFlatBufferContractTypeMap(
            model.Types,
            model.Methods,
            model.Parameters,
            seedWithContextualAndSiblingTypeNames);
        var seedWithContextualSiblingAndFlatBufferTypeNames = MergeTypeNameMaps(seedWithContextualAndSiblingTypeNames, flatBufferContractTypeNames);
        var fieldAdjustedTypeNames = BuildFieldShiftedTypeMap(
            model.Fields,
            seedWithContextualSiblingAndFlatBufferTypeNames);
        var mergedTypeNames = MergeTypeNameMaps(seedWithContextualSiblingAndFlatBufferTypeNames, fieldAdjustedTypeNames);
        var refinedContextualSeedTypeNames = MergeTypeNameMaps(contextualSeedTypeNames, contextualTypeNames, siblingContractTypeNames, flatBufferContractTypeNames);

        _globalTypeNames = MergeTypeNameMaps(
            mergedTypeNames,
            BuildFieldShiftedTypeMap(model.Fields, mergedTypeNames),
            BuildContextualParameterTypeMap(
                model.Types,
                model.Methods,
                model.Parameters,
                refinedContextualSeedTypeNames),
            BuildSiblingMethodTypeMap(model.Types, model.Methods, model.Parameters, mergedTypeNames),
            BuildFlatBufferContractTypeMap(model.Types, model.Methods, model.Parameters, mergedTypeNames));
    }

    public IReadOnlyDictionary<uint, string> GlobalTypeNames => _globalTypeNames;

    public IReadOnlyDictionary<uint, string> CreateTypeNameMap(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyList<FieldDefinition> fieldRows)
    {
        var localTypeNames = BuildLocalTypeOverrides(type, methodRows, fieldRows);
        if (localTypeNames.Count == 0)
            return _globalTypeNames;

        return new TypeNameLookup(_globalTypeNames, localTypeNames);
    }

    public Dictionary<uint, string> BuildLocalTypeOverrides(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyList<FieldDefinition> fieldRows)
    {
        var hints = _descriptors.GetHints(type);
        if (!hints.RequiresLocalTypeInference)
            return new Dictionary<uint, string>();

        var localTypeNames = BuildLocalTypeNameMap(type, methodRows, fieldRows);
        foreach (var field in fieldRows)
        {
            if (field.Name == "__p" &&
                hints.HasByteBufferAccessor &&
                hints.HasFlatBufferAssignOrRoot)
            {
                localTypeNames[field.TypeIndex] = "FlatBuffers.Table";
            }

            if (field.Name == "TableKey" && hints.HasInitKeyMethod)
                localTypeNames[field.TypeIndex] = "byte[]";
        }

        return localTypeNames;
    }

    public string ResolveTypeName(uint typeIndex, IReadOnlyDictionary<uint, string> typeNameMap, string? fallback = null)
    {
        if (typeNameMap.TryGetValue(typeIndex, out var resolvedType))
        {
            if (ShouldPreferFallback(resolvedType, fallback))
            {
                return YldaResolutionUtilities.SimplifyTypeName(fallback!);
            }

            return YldaResolutionUtilities.SimplifyTypeName(resolvedType);
        }

        return YldaResolutionUtilities.FormatType(typeIndex, typeNameMap, fallback);
    }

    public string ResolveContextualTypeName(
        TypeDefinition declaringType,
        string memberName,
        uint typeIndex,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap,
        string? fallback = null)
    {
        var contextualFallback = InferContextualFallback(declaringType, memberName, methodRows, fallback);
        return ResolveTypeName(typeIndex, typeNameMap, contextualFallback ?? fallback);
    }

    private static Dictionary<uint, string> BuildDirectTypeNameMap(IReadOnlyList<TypeDefinition> types)
    {
        var grouped = new Dictionary<uint, HashSet<string>>();
        foreach (var type in types)
        {
            foreach (var index in new[] { type.PrimaryTypeIndex, type.SecondaryTypeIndex })
            {
                if (index == uint.MaxValue)
                    continue;
                if (!grouped.TryGetValue(index, out var names))
                {
                    names = [];
                    grouped[index] = names;
                }

                names.Add(type.FullName);
            }
        }

        var resolved = new Dictionary<uint, string>();
        foreach (var pair in grouped)
            resolved[pair.Key] = YldaResolutionUtilities.ChooseTypeName(pair.Value) ?? $"Type_0x{pair.Key:X8}";
        return resolved;
    }

    private static Dictionary<uint, string> MergeTypeNameMaps(params IReadOnlyDictionary<uint, string>[] maps)
    {
        var grouped = new Dictionary<uint, HashSet<string>>();
        foreach (var map in maps)
        {
            foreach (var pair in map)
            {
                if (!grouped.TryGetValue(pair.Key, out var names))
                {
                    names = [];
                    grouped[pair.Key] = names;
                }

                names.Add(pair.Value);
            }
        }

        var resolved = new Dictionary<uint, string>();
        foreach (var pair in grouped)
            resolved[pair.Key] = YldaResolutionUtilities.ChooseTypeName(pair.Value) ?? $"Type_0x{pair.Key:X8}";
        return resolved;
    }

    private static Dictionary<uint, string> BuildInferredTypeNameMap(
        IReadOnlyList<TypeDefinition> typeDefs,
        IReadOnlyList<MethodDefinition> methods,
        IReadOnlyList<ParameterDefinition> parameters)
    {
        var inferred = new Dictionary<uint, HashSet<string>>();

        void Remember(uint typeIndex, string typeName)
        {
            if (typeIndex == uint.MaxValue)
                return;
            if (!inferred.TryGetValue(typeIndex, out var names))
            {
                names = [];
                inferred[typeIndex] = names;
            }

            names.Add(typeName);
        }

        foreach (var method in methods)
        {
            if (method.DeclaringTypeIndex < 0 || method.DeclaringTypeIndex >= typeDefs.Count)
                continue;

            var declaringType = typeDefs[method.DeclaringTypeIndex].FullName;
            var methodParams = YldaResolutionUtilities.GetMethodParameters(method, parameters);

            if (declaringType == "System.String")
            {
                if (method.Name == "Concat" && methodParams.Count == 1)
                {
                    var param = methodParams[0];
                    if (param.Name == "values")
                        Remember(param.TypeIndex, "System.String[]");
                    else if (param.Name == "args")
                        Remember(param.TypeIndex, "System.Object[]");
                }

                if (method.Name == "Join" && methodParams.Count == 2)
                {
                    var separator = methodParams[0];
                    var values = methodParams[1];
                    if (separator.TypeIndex != values.TypeIndex && (values.Name == "value" || values.Name == "values"))
                        Remember(values.TypeIndex, "System.String[]");
                }

                if (method.Name == "Split")
                    Remember(method.ReturnTypeIndex, "System.String[]");
            }

            if (declaringType == "System.Object" && method.Name == "GetType")
                Remember(method.ReturnTypeIndex, "System.Type");

            if (declaringType == "System.IO.File" && method.Name == "GetFiles")
                Remember(method.ReturnTypeIndex, "System.String[]");

            if (declaringType == "System.DateTime" && method.Name == "GetDateTimeFormats")
                Remember(method.ReturnTypeIndex, "System.String[]");

            if (declaringType == "System.Collections.Specialized.NameValueCollection" && method.Name == "GetValues")
                Remember(method.ReturnTypeIndex, "System.String[]");

            if (declaringType == "UnityEngine.Android.Permission" && method.Name == "RequestUserPermissions" && methodParams.Count > 0)
                Remember(methodParams[0].TypeIndex, "System.String[]");

            if (declaringType == "System.MulticastDelegate" && method.Name == "GetInvocationList")
                Remember(method.ReturnTypeIndex, "System.Delegate[]");

            if (declaringType == "System.Delegate")
            {
                if (method.Name is "get_Method" or "GetVirtualMethod_internal")
                    Remember(method.ReturnTypeIndex, "System.Reflection.MethodInfo");
                if (method.Name == "get_Target")
                    Remember(method.ReturnTypeIndex, "System.Object");
            }

            if (declaringType == "UnityEngine.MonoBehaviour" && method.Name.StartsWith("StartCoroutine", StringComparison.Ordinal))
                Remember(method.ReturnTypeIndex, "UnityEngine.Coroutine");

            if (declaringType.EndsWith("XmlException", StringComparison.Ordinal))
            {
                foreach (var param in methodParams.Where(param => param.Name == "args"))
                    Remember(param.TypeIndex, "System.String[]");
            }
        }

        var resolved = new Dictionary<uint, string>();
        foreach (var pair in inferred)
            resolved[pair.Key] = YldaResolutionUtilities.ChooseTypeName(pair.Value) ?? $"Type_0x{pair.Key:X8}";
        return resolved;
    }

    private static Dictionary<uint, string> BuildHeuristicPrimitiveTypeMap(IReadOnlyList<FieldDefinition> fields)
    {
        var votes = new Dictionary<uint, Dictionary<string, int>>();

        void Vote(uint typeIndex, string typeName, int weight = 1)
        {
            if (typeIndex == uint.MaxValue)
                return;
            if (!votes.TryGetValue(typeIndex, out var bucket))
            {
                bucket = new Dictionary<string, int>(StringComparer.Ordinal);
                votes[typeIndex] = bucket;
            }

            bucket[typeName] = bucket.GetValueOrDefault(typeName) + weight;
        }

        foreach (var field in fields)
        {
            if (string.Equals(field.Name, "__2__current", StringComparison.Ordinal))
            {
                Vote(field.TypeIndex, "System.Object", 4);
                continue;
            }

            if (string.Equals(field.Name, "value__", StringComparison.Ordinal))
            {
                Vote(field.TypeIndex, "System.Int32", 6);
                continue;
            }

             if (YldaResolutionUtilities.LooksLikeReferenceSemanticName(field.Name) ||
                YldaResolutionUtilities.TrySingularizeCollectionName(field.Name, out _))
            {
                continue;
            }

            if (YldaResolutionConstants.IntLikeFieldNames.Contains(field.Name))
                Vote(field.TypeIndex, "System.Int32", 3);

            if (YldaResolutionConstants.BoolLikeFieldNames.Contains(field.Name))
                Vote(field.TypeIndex, "System.Boolean", 3);

            if (field.Name.EndsWith("Id", StringComparison.Ordinal) ||
                field.Name.EndsWith("ID", StringComparison.Ordinal) ||
                field.Name.EndsWith("UniqueId", StringComparison.Ordinal) ||
                field.Name.EndsWith("ServerId", StringComparison.Ordinal) ||
                field.Name.EndsWith("CostumeId", StringComparison.Ordinal) ||
                field.Name.EndsWith("CharacterId", StringComparison.Ordinal))
            {
                Vote(field.TypeIndex, "System.Int64", 2);
            }
        }

        var resolved = new Dictionary<uint, string>();
        foreach (var pair in votes)
        {
            var ranking = pair.Value
                .OrderByDescending(item => item.Value)
                .ThenBy(item => item.Key, StringComparer.Ordinal)
                .ToArray();
            if (ranking.Length == 0)
                continue;

            if (ranking.Length == 1 || ranking[0].Value >= ranking[1].Value * 2 || ranking[0].Value >= 6)
                resolved[pair.Key] = ranking[0].Key;
        }

        return resolved;
    }

    private static Dictionary<uint, string> BuildFieldShiftedTypeMap(
        IReadOnlyList<FieldDefinition> fields,
        IReadOnlyDictionary<uint, string> knownTypeNames)
    {
        var inferred = new Dictionary<uint, string>();
        foreach (var field in fields)
        {
            if (field.TypeIndex == 0 || field.TypeIndex == uint.MaxValue)
                continue;

            if (!knownTypeNames.TryGetValue(field.TypeIndex - 1, out var candidateType))
                continue;
            if (string.IsNullOrWhiteSpace(candidateType) || candidateType.StartsWith("Type_0x", StringComparison.Ordinal))
                continue;

            if (knownTypeNames.TryGetValue(field.TypeIndex, out var existingTypeName) &&
                !existingTypeName.StartsWith("Type_0x", StringComparison.Ordinal) &&
                !YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(existingTypeName) &&
                !YldaResolutionUtilities.LooksLikeReferenceSemanticName(field.Name))
            {
                continue;
            }

            inferred[field.TypeIndex] = candidateType;
        }

        return inferred;
    }

    private static string? InferContextualFallback(
        TypeDefinition declaringType,
        string memberName,
        IReadOnlyList<MethodDefinition> methodRows,
        string? existingFallback)
    {
        if (!string.IsNullOrWhiteSpace(existingFallback) &&
            !existingFallback!.StartsWith("Type_0x", StringComparison.Ordinal))
        {
            return existingFallback;
        }

        var normalizedMemberName = memberName;
        if (normalizedMemberName.StartsWith("get_", StringComparison.Ordinal) ||
            normalizedMemberName.StartsWith("set_", StringComparison.Ordinal) ||
            normalizedMemberName.StartsWith("add_", StringComparison.Ordinal) ||
            normalizedMemberName.StartsWith("remove_", StringComparison.Ordinal))
        {
            normalizedMemberName = normalizedMemberName[(normalizedMemberName.IndexOf('_') + 1)..];
        }

        if (string.Equals(normalizedMemberName, "shapeNames", StringComparison.OrdinalIgnoreCase))
            return "System.String[]";

        if (string.Equals(normalizedMemberName, "DownloadFailedFiles", StringComparison.OrdinalIgnoreCase))
            return "System.String[]";

        if (TryInferFurnitureFallback(declaringType, normalizedMemberName, out var furnitureFallback))
            return furnitureFallback;

        if (!IsPatchDownloadHotspot(declaringType, methodRows))
            return existingFallback;

        if (PatchFileInfoDictionaryMemberNames.Contains(normalizedMemberName))
            return "System.Collections.Generic.Dictionary<string, MX.AssetBundles.PatchFileInfo>";

        if (PatchFileInfoEnumerableMemberNames.Contains(normalizedMemberName))
            return "System.Collections.Generic.IEnumerable<MX.AssetBundles.PatchFileInfo>";

        if (PatchFileInfoListMemberNames.Contains(normalizedMemberName))
            return "System.Collections.Generic.List<MX.AssetBundles.PatchFileInfo>";

        if (normalizedMemberName.Contains("PatchFileInfo", StringComparison.OrdinalIgnoreCase))
            return "System.Collections.Generic.List<MX.AssetBundles.PatchFileInfo>";

        return existingFallback;
    }

    private static bool TryInferFurnitureFallback(TypeDefinition declaringType, string memberName, out string? fallback)
    {
        fallback = null;
        if (!IsFurnitureHotspot(declaringType))
            return false;

        if (string.Equals(memberName, "MyTransform", StringComparison.OrdinalIgnoreCase))
        {
            fallback = "UnityEngine.Transform";
            return true;
        }

        if (string.Equals(memberName, "FurnitureExcel", StringComparison.OrdinalIgnoreCase))
        {
            fallback = "FlatData.FurnitureExcel";
            return true;
        }

        if (string.Equals(memberName, "FurnitureObject", StringComparison.OrdinalIgnoreCase))
        {
            fallback = "FurnitureObject";
            return true;
        }

        if (string.Equals(memberName, "otherObject", StringComparison.OrdinalIgnoreCase))
        {
            fallback = "FurnitureObject";
            return true;
        }

        if (FurnitureReferenceMemberNames.Contains(memberName))
        {
            fallback = memberName switch
            {
                "FindVisual" => "FurnitureVisual",
                _ when IsFurnitureVisualDomain(declaringType) => "FurnitureVisual",
                _ => "FurnitureObject",
            };
            return true;
        }

        if (FurnitureVector2MemberNames.Contains(memberName))
        {
            fallback = "UnityEngine.Vector2";
            return true;
        }

        if (FurnitureVector3MemberNames.Contains(memberName))
        {
            fallback = "UnityEngine.Vector3";
            return true;
        }

        if (FurnitureLongLikeMemberNames.Contains(memberName))
        {
            fallback = "long";
            return true;
        }

        return false;
    }

    private static bool IsPatchDownloadHotspot(TypeDefinition declaringType, IReadOnlyList<MethodDefinition> methodRows)
    {
        if (declaringType.FullName is
            "SplitDownloadPatcher" or
            "MX.AssetBundles.BundlePatchStrategy" or
            "MX.AssetBundles.MediaPatchStrategy" or
            "MX.AssetBundles.TablePatchStrategy" or
            "MX.AssetBundles.ResourcePatcher")
        {
            return true;
        }

        return methodRows.Any(method =>
            method.Name.Contains("Download", StringComparison.OrdinalIgnoreCase) ||
            method.Name.Contains("Patch", StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsFurnitureHotspot(TypeDefinition declaringType)
        => declaringType.FullName is
            "FurnitureObject" or
            "FurnitureVisual" or
            "CafeFurnitureLoader" or
            "FurnitureFactory" or
            "FurnitureInteractionPopulator" or
            "CafeInputHandler";

    private static bool IsFurnitureVisualDomain(TypeDefinition declaringType)
        => declaringType.FullName is
            "FurnitureVisual" or
            "CafeFurnitureLoader" or
            "FurnitureFactory" or
            "FurnitureInteractionPopulator" or
            "CafeInputHandler";

    private static bool ShouldPreferFallback(string resolvedType, string? fallback)
    {
        if (string.IsNullOrWhiteSpace(fallback) || fallback!.StartsWith("Type_0x", StringComparison.Ordinal))
            return false;

        if (resolvedType.StartsWith("Type_0x", StringComparison.Ordinal))
            return true;

        if (YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(resolvedType) &&
            !YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(fallback))
        {
            return true;
        }

        if ((string.Equals(fallback, "long", StringComparison.Ordinal) ||
             string.Equals(fallback, "System.Int64", StringComparison.Ordinal)) &&
            (string.Equals(resolvedType, "int", StringComparison.Ordinal) ||
             string.Equals(resolvedType, "System.Int32", StringComparison.Ordinal) ||
             string.Equals(resolvedType, "float", StringComparison.Ordinal) ||
             string.Equals(resolvedType, "System.Single", StringComparison.Ordinal)))
        {
            return true;
        }

        if (!fallback.Contains("MX.AssetBundles.PatchFileInfo", StringComparison.Ordinal))
            return false;

        return string.Equals(resolvedType, "string[]", StringComparison.Ordinal) ||
               string.Equals(resolvedType, "System.String[]", StringComparison.Ordinal) ||
               resolvedType.Contains("<string", StringComparison.Ordinal) ||
               resolvedType.Contains("<System.String", StringComparison.Ordinal);
    }

    private static Dictionary<uint, string> BuildHeuristicParameterTypeMap(IReadOnlyList<ParameterDefinition> parameters, bool includeIntLike)
    {
        var votes = new Dictionary<uint, Dictionary<string, int>>();

        void Vote(uint typeIndex, string typeName, int weight = 1)
        {
            if (typeIndex == uint.MaxValue)
                return;
            if (!votes.TryGetValue(typeIndex, out var bucket))
            {
                bucket = new Dictionary<string, int>(StringComparer.Ordinal);
                votes[typeIndex] = bucket;
            }

            bucket[typeName] = bucket.GetValueOrDefault(typeName) + weight;
        }

        foreach (var parameter in parameters)
        {
            if (YldaResolutionConstants.ByteArrayParameterNames.Contains(parameter.Name))
                Vote(parameter.TypeIndex, "System.Byte[]", 4);

            if (YldaResolutionConstants.BoolLikeParameterNames.Contains(parameter.Name))
                Vote(parameter.TypeIndex, "System.Boolean", 3);

            if (includeIntLike && YldaResolutionConstants.IntLikeParameterNames.Contains(parameter.Name))
                Vote(parameter.TypeIndex, "System.Int32", 3);

            if (YldaResolutionConstants.FloatLikeParameterNames.Contains(parameter.Name))
                Vote(parameter.TypeIndex, "System.Single", 3);
        }

        var resolved = new Dictionary<uint, string>();
        foreach (var pair in votes)
        {
            var ranking = pair.Value
                .OrderByDescending(item => item.Value)
                .ThenBy(item => item.Key, StringComparer.Ordinal)
                .ToArray();
            if (ranking.Length == 0)
                continue;

            if (ranking.Length == 1 || ranking[0].Value >= ranking[1].Value * 2 || ranking[0].Value >= 6)
                resolved[pair.Key] = ranking[0].Key;
        }

        return resolved;
    }

    private Dictionary<uint, string> BuildContextualParameterTypeMap(
        IReadOnlyList<TypeDefinition> typeDefs,
        IReadOnlyList<MethodDefinition> methods,
        IReadOnlyList<ParameterDefinition> parameters,
        IReadOnlyDictionary<uint, string> knownTypeNames)
    {
        var groupedKnownNames = new Dictionary<int, Dictionary<string, HashSet<string>>>();

        foreach (var method in methods)
        {
            if (method.DeclaringTypeIndex < 0 || method.DeclaringTypeIndex >= typeDefs.Count)
                continue;
            if (method.ParameterStart == uint.MaxValue || method.ParameterCount <= 0)
                continue;

            if (!groupedKnownNames.TryGetValue(method.DeclaringTypeIndex, out var nameMap))
            {
                nameMap = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);
                groupedKnownNames[method.DeclaringTypeIndex] = nameMap;
            }

            for (var index = 0; index < method.ParameterCount; index++)
            {
                var parameter = parameters[(int)method.ParameterStart + index];
                if (!knownTypeNames.TryGetValue(parameter.TypeIndex, out var knownType))
                    continue;
                if (knownType.StartsWith("Type_0x", StringComparison.Ordinal))
                    continue;

                if (!nameMap.TryGetValue(parameter.Name, out var candidates))
                {
                    candidates = new HashSet<string>(StringComparer.Ordinal);
                    nameMap[parameter.Name] = candidates;
                }

                candidates.Add(knownType);
            }
        }

        var inferred = new Dictionary<uint, string>();
        foreach (var method in methods)
        {
            if (method.DeclaringTypeIndex < 0 || method.DeclaringTypeIndex >= typeDefs.Count)
                continue;
            if (method.ParameterStart == uint.MaxValue || method.ParameterCount <= 0)
                continue;
            if (!groupedKnownNames.TryGetValue(method.DeclaringTypeIndex, out var nameMap))
                continue;

            for (var index = 0; index < method.ParameterCount; index++)
            {
                var parameter = parameters[(int)method.ParameterStart + index];
                if (knownTypeNames.ContainsKey(parameter.TypeIndex))
                    continue;
                if (!nameMap.TryGetValue(parameter.Name, out var candidates) || candidates.Count != 1)
                    continue;

                inferred[parameter.TypeIndex] = candidates.First();
            }
        }

        return inferred;
    }

    private Dictionary<uint, string> BuildSiblingMethodTypeMap(
        IReadOnlyList<TypeDefinition> typeDefs,
        IReadOnlyList<MethodDefinition> methods,
        IReadOnlyList<ParameterDefinition> parameters,
        IReadOnlyDictionary<uint, string> knownTypeNames)
    {
        var memberTypesByDeclaringType = new Dictionary<int, Dictionary<string, HashSet<string>>>();

        void RememberMemberType(int declaringTypeIndex, string memberName, string typeName)
        {
            if (declaringTypeIndex < 0 || declaringTypeIndex >= typeDefs.Count)
                return;
            if (string.IsNullOrWhiteSpace(memberName) || string.IsNullOrWhiteSpace(typeName))
                return;
            if (typeName.StartsWith("Type_0x", StringComparison.Ordinal))
                return;

            if (!memberTypesByDeclaringType.TryGetValue(declaringTypeIndex, out var memberTypes))
            {
                memberTypes = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);
                memberTypesByDeclaringType[declaringTypeIndex] = memberTypes;
            }

            foreach (var key in YldaResolutionUtilities.ExpandMemberNameKeys(memberName, typeName))
            {
                if (!memberTypes.TryGetValue(key, out var candidates))
                {
                    candidates = new HashSet<string>(StringComparer.Ordinal);
                    memberTypes[key] = candidates;
                }

                candidates.Add(typeName);
            }
        }

        foreach (var method in methods)
        {
            if (method.DeclaringTypeIndex < 0 || method.DeclaringTypeIndex >= typeDefs.Count)
                continue;

            var methodParams = GetMethodParameters(method);

            if (method.Name.StartsWith("get_", StringComparison.Ordinal) &&
                methodParams.Count == 0 &&
                knownTypeNames.TryGetValue(method.ReturnTypeIndex, out var getterType))
            {
                RememberMemberType(method.DeclaringTypeIndex, method.Name[4..], getterType);
            }

            if (method.Name.StartsWith("set_", StringComparison.Ordinal) &&
                methodParams.Count >= 1 &&
                knownTypeNames.TryGetValue(methodParams[0].TypeIndex, out var setterType))
            {
                RememberMemberType(method.DeclaringTypeIndex, method.Name[4..], setterType);
            }

            if (method.Name.StartsWith("Add", StringComparison.Ordinal) &&
                methodParams.Count >= 2 &&
                knownTypeNames.TryGetValue(methodParams[1].TypeIndex, out var addType))
            {
                RememberMemberType(method.DeclaringTypeIndex, method.Name[3..], addType);
            }
        }

        var inferred = new Dictionary<uint, string>();
        foreach (var method in methods)
        {
            if (method.DeclaringTypeIndex < 0 || method.DeclaringTypeIndex >= typeDefs.Count)
                continue;
            if (!memberTypesByDeclaringType.TryGetValue(method.DeclaringTypeIndex, out var memberTypes))
                continue;

            var methodParams = GetMethodParameters(method);
            foreach (var parameter in methodParams)
            {
                if (knownTypeNames.ContainsKey(parameter.TypeIndex))
                    continue;
                if (!memberTypes.TryGetValue(parameter.Name, out var candidates) || candidates.Count != 1)
                    continue;

                inferred[parameter.TypeIndex] = candidates.First();
            }
        }

        return inferred;
    }

    private Dictionary<uint, string> BuildFlatBufferContractTypeMap(
        IReadOnlyList<TypeDefinition> typeDefs,
        IReadOnlyList<MethodDefinition> methods,
        IReadOnlyList<ParameterDefinition> parameters,
        IReadOnlyDictionary<uint, string> knownTypeNames)
    {
        var memberTypesByDeclaringType = new Dictionary<int, Dictionary<string, HashSet<string>>>();
        var vectorElementTypesByDeclaringType = new Dictionary<int, Dictionary<string, HashSet<string>>>();

        void Remember(
            Dictionary<int, Dictionary<string, HashSet<string>>> store,
            int declaringTypeIndex,
            string memberName,
            string typeName)
        {
            if (declaringTypeIndex < 0 || declaringTypeIndex >= typeDefs.Count)
                return;
            if (string.IsNullOrWhiteSpace(memberName) || string.IsNullOrWhiteSpace(typeName))
                return;
            if (typeName.StartsWith("Type_0x", StringComparison.Ordinal))
                return;

            if (!store.TryGetValue(declaringTypeIndex, out var memberTypes))
            {
                memberTypes = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);
                store[declaringTypeIndex] = memberTypes;
            }

            foreach (var key in YldaResolutionUtilities.ExpandMemberNameKeys(memberName, typeName))
            {
                if (!memberTypes.TryGetValue(key, out var candidates))
                {
                    candidates = new HashSet<string>(StringComparer.Ordinal);
                    memberTypes[key] = candidates;
                }

                candidates.Add(typeName);
            }
        }

        foreach (var method in methods)
        {
            if (method.DeclaringTypeIndex < 0 || method.DeclaringTypeIndex >= typeDefs.Count)
                continue;

            var methodParams = GetMethodParameters(method);

            if (method.Name.StartsWith("Add", StringComparison.Ordinal) &&
                methodParams.Count >= 2 &&
                knownTypeNames.TryGetValue(methodParams[1].TypeIndex, out var addType))
            {
                Remember(memberTypesByDeclaringType, method.DeclaringTypeIndex, method.Name[3..], addType);
            }

            if (methodParams.Count == 1 &&
                methodParams[0].Name is "j" or "index" &&
                knownTypeNames.TryGetValue(method.ReturnTypeIndex, out var elementType) &&
                !method.Name.StartsWith("get_", StringComparison.Ordinal) &&
                !method.Name.StartsWith("Get", StringComparison.Ordinal))
            {
                Remember(vectorElementTypesByDeclaringType, method.DeclaringTypeIndex, method.Name, elementType);
            }
        }

        var inferred = new Dictionary<uint, string>();
        foreach (var method in methods)
        {
            if (method.DeclaringTypeIndex < 0 || method.DeclaringTypeIndex >= typeDefs.Count)
                continue;

            var methodParams = GetMethodParameters(method);

            if (method.Name.StartsWith("Create", StringComparison.Ordinal) &&
                method.Name.EndsWith("Vector", StringComparison.Ordinal) &&
                methodParams.Count >= 2 &&
                methodParams[1].Name == "data" &&
                vectorElementTypesByDeclaringType.TryGetValue(method.DeclaringTypeIndex, out var vectorTypes))
            {
                var vectorName = method.Name["Create".Length..^"Vector".Length];
                if (vectorTypes.TryGetValue(vectorName, out var elementCandidates) && elementCandidates.Count == 1)
                    inferred[methodParams[1].TypeIndex] = YldaResolutionUtilities.NormalizeTypeCandidate(elementCandidates.First()) + "[]";
            }

            if (!method.Name.StartsWith("Create", StringComparison.Ordinal) ||
                !memberTypesByDeclaringType.TryGetValue(method.DeclaringTypeIndex, out var memberTypes))
                continue;

            foreach (var parameter in methodParams.Skip(1))
            {
                if (!memberTypes.TryGetValue(parameter.Name, out var candidates) || candidates.Count != 1)
                    continue;

                inferred[parameter.TypeIndex] = candidates.First();
            }
        }

        return inferred;
    }

    private Dictionary<uint, string> BuildLocalTypeNameMap(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyList<FieldDefinition> fieldRows)
    {
        var hints = _descriptors.GetHints(type);
        var hasExplicitInterfaces = hints.HasExplicitInterfaces;
        var isTableLike = hints.IsTableLike;
        var isKnownLocalInferenceType = hints.IsKnownLocalInferenceType;
        var inferred = new Dictionary<uint, string>();

        void Remember(uint typeIndex, string typeName)
        {
            if (typeIndex == uint.MaxValue || string.IsNullOrWhiteSpace(typeName))
                return;
            inferred[typeIndex] = typeName;
        }

        foreach (var method in methodRows)
        {
            var methodParams = GetMethodParameters(method);
            if (method.Name == "__assign" || method.Name.StartsWith("GetRootAs", StringComparison.Ordinal))
            {
                Remember(method.ReturnTypeIndex, type.FullName);
                foreach (var param in methodParams.Where(param => param.Name == "obj"))
                    Remember(param.TypeIndex, type.FullName);
            }

            var iface = YldaResolutionUtilities.ExplicitInterfacePrefix(method.Name);
            if (iface is not null)
            {
                foreach (var pair in InferFromExplicitInterface(iface, method.Name, method, methodParams))
                    inferred[pair.Key] = pair.Value;
            }
        }

        if (hints.HasCollectionLikeMembers)
        {
            foreach (var pair in BuildCollectionLikeTypeMap(type, methodRows, fieldRows, inferred))
                inferred[pair.Key] = pair.Value;
        }

        Dictionary<string, string>? vectorElementTypes = null;
        if (hints.HasCollectionLikeMembers || isTableLike)
        {
            vectorElementTypes = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var method in methodRows)
            {
                var methodParams = GetMethodParameters(method);
                string? knownReturnType = null;
                if (inferred.TryGetValue(method.ReturnTypeIndex, out var localReturnType))
                    knownReturnType = localReturnType;
                else if (_globalTypeNames.TryGetValue(method.ReturnTypeIndex, out var globalReturnType))
                    knownReturnType = globalReturnType;

                if (methodParams.Count == 1 &&
                    methodParams[0].Name is "j" or "index" &&
                    !string.IsNullOrWhiteSpace(knownReturnType) &&
                    !knownReturnType.StartsWith("Type_0x", StringComparison.Ordinal) &&
                    !method.Name.StartsWith("get_", StringComparison.Ordinal) &&
                    !method.Name.StartsWith("Get", StringComparison.Ordinal))
                {
                    vectorElementTypes[method.Name] = YldaResolutionUtilities.NormalizeTypeCandidate(knownReturnType);
                }
            }
        }

        if (isTableLike)
        {
            var companionTypeName = type.FullName[..^"Table".Length];
            if (_typeFullNames.Contains(companionTypeName))
            {
                foreach (var method in methodRows)
                {
                    var methodParams = GetMethodParameters(method);
                    if (method.Name == "DataList" && methodParams.Count == 1 && methodParams[0].Name is "j" or "index")
                        Remember(method.ReturnTypeIndex, companionTypeName);

                    if (method.Name == "CreateDataListVector" && methodParams.Count >= 2 && methodParams[1].Name == "data")
                        Remember(methodParams[1].TypeIndex, companionTypeName + "[]");
                }
            }
        }

        if (vectorElementTypes is not null && vectorElementTypes.Count > 0)
        {
            foreach (var method in methodRows)
            {
                var methodParams = GetMethodParameters(method);
                if (method.Name.StartsWith("Create", StringComparison.Ordinal) &&
                    method.Name.EndsWith("Vector", StringComparison.Ordinal) &&
                    methodParams.Count >= 2 &&
                    methodParams[1].Name == "data")
                {
                    var vectorName = method.Name["Create".Length..^"Vector".Length];
                    if (vectorElementTypes.TryGetValue(vectorName, out var vectorElementType))
                        Remember(methodParams[1].TypeIndex, vectorElementType + "[]");
                }
            }
        }

        if (!isKnownLocalInferenceType && !hasExplicitInterfaces)
            return inferred;

        switch (type.FullName)
        {
            case "System.Collections.Generic.IEnumerable`1":
                foreach (var method in methodRows.Where(method => method.Name == "GetEnumerator"))
                    Remember(method.ReturnTypeIndex, "System.Collections.Generic.IEnumerator<T>");
                break;

            case "System.Collections.Generic.IEnumerator`1":
                foreach (var method in methodRows.Where(method => method.Name == "get_Current"))
                    Remember(method.ReturnTypeIndex, "T");
                break;

            case "System.Collections.Generic.IReadOnlyList`1":
                foreach (var method in methodRows.Where(method => method.Name == "get_Item"))
                    Remember(method.ReturnTypeIndex, "T");
                break;

            case "System.Collections.Generic.IReadOnlyDictionary`2":
                foreach (var method in methodRows)
                {
                    var methodParams = GetMethodParameters(method);
                    if (method.Name is "ContainsKey" or "get_Item" or "TryGetValue")
                    {
                        if (methodParams.Count > 0)
                            Remember(methodParams[0].TypeIndex, "TKey");
                    }

                    if (method.Name == "get_Item")
                        Remember(method.ReturnTypeIndex, "TValue");
                    else if (method.Name == "TryGetValue" && methodParams.Count > 1)
                        Remember(methodParams[1].TypeIndex, "TValue");
                    else if (method.Name == "get_Keys")
                        Remember(method.ReturnTypeIndex, "System.Collections.Generic.IEnumerable<TKey>");
                    else if (method.Name == "get_Values")
                        Remember(method.ReturnTypeIndex, "System.Collections.Generic.IEnumerable<TValue>");
                }
                break;

            case "System.Collections.Generic.List`1":
                foreach (var method in methodRows)
                {
                    var methodParams = GetMethodParameters(method);
                    if (method.Name == "get_Item")
                        Remember(method.ReturnTypeIndex, "T");

                    if (method.Name is "set_Item" or "Add" or "AddWithResize" or "Contains" or "IndexOf" or "LastIndexOf" or "Remove" or "Insert")
                    {
                        foreach (var param in methodParams.Where(param => param.Name is "item" or "value"))
                            Remember(param.TypeIndex, "T");
                    }

                    if (method.Name is ".ctor" or "AddRange")
                    {
                        foreach (var param in methodParams.Where(param => param.Name == "collection"))
                            Remember(param.TypeIndex, "System.Collections.Generic.IEnumerable<T>");
                    }

                    if (method.Name == "BinarySearch")
                    {
                        foreach (var param in methodParams)
                        {
                            if (param.Name == "item")
                                Remember(param.TypeIndex, "T");
                            else if (param.Name == "comparer")
                                Remember(param.TypeIndex, "System.Collections.Generic.IComparer<T>");
                        }
                    }

                    if (method.Name == "AsReadOnly")
                        Remember(method.ReturnTypeIndex, "System.Collections.ObjectModel.ReadOnlyCollection<T>");

                    if (method.Name == "ConvertAll")
                    {
                        Remember(method.ReturnTypeIndex, "System.Collections.Generic.List<TOutput>");
                        foreach (var param in methodParams.Where(param => param.Name == "converter"))
                            Remember(param.TypeIndex, "System.Converter<T, TOutput>");
                    }

                    if (method.Name is "Exists" or "Find" or "FindAll" or "FindIndex" or "FindLast" or "FindLastIndex" or "RemoveAll" or "TrueForAll")
                    {
                        foreach (var param in methodParams.Where(param => param.Name == "match"))
                            Remember(param.TypeIndex, "System.Predicate<T>");
                    }

                    if (method.Name == "ForEach")
                    {
                        foreach (var param in methodParams.Where(param => param.Name == "action"))
                            Remember(param.TypeIndex, "System.Action<T>");
                    }

                    if (method.Name == "CopyTo")
                    {
                        foreach (var param in methodParams.Where(param => param.Name == "array"))
                            Remember(param.TypeIndex, "T[]");
                    }

                    if (method.Name == "GetEnumerator")
                        Remember(method.ReturnTypeIndex, "System.Collections.Generic.List<T>.Enumerator");

                    if (method.Name is "GetRange" or "FindAll")
                        Remember(method.ReturnTypeIndex, "System.Collections.Generic.List<T>");

                    if (method.Name == "ToArray")
                        Remember(method.ReturnTypeIndex, "T[]");
                }
                break;

            case "System.Collections.Generic.Dictionary`2":
                foreach (var method in methodRows)
                {
                    var methodParams = GetMethodParameters(method);
                    switch (method.Name)
                    {
                        case "get_Comparer":
                            Remember(method.ReturnTypeIndex, "System.Collections.Generic.IEqualityComparer<TKey>");
                            break;
                        case "get_Keys":
                        case "System.Collections.Generic.IDictionary<TKey,TValue>.get_Keys":
                            Remember(method.ReturnTypeIndex, "System.Collections.Generic.ICollection<TKey>");
                            break;
                        case "System.Collections.Generic.IReadOnlyDictionary<TKey,TValue>.get_Keys":
                            Remember(method.ReturnTypeIndex, "System.Collections.Generic.IEnumerable<TKey>");
                            break;
                        case "get_Values":
                        case "System.Collections.Generic.IDictionary<TKey,TValue>.get_Values":
                            Remember(method.ReturnTypeIndex, "System.Collections.Generic.ICollection<TValue>");
                            break;
                        case "System.Collections.Generic.IReadOnlyDictionary<TKey,TValue>.get_Values":
                            Remember(method.ReturnTypeIndex, "System.Collections.Generic.IEnumerable<TValue>");
                            break;
                        case "get_Item":
                            Remember(method.ReturnTypeIndex, "TValue");
                            if (methodParams.Count > 0)
                                Remember(methodParams[0].TypeIndex, "TKey");
                            break;
                        case "Add":
                        case "ContainsKey":
                        case "TryGetValue":
                        case "ContainsValue":
                            foreach (var param in methodParams)
                            {
                                if (param.Name == "key")
                                    Remember(param.TypeIndex, "TKey");
                                else if (param.Name == "value")
                                    Remember(param.TypeIndex, "TValue");
                            }
                            break;
                        case "CopyTo":
                            foreach (var param in methodParams.Where(param => param.Name == "array"))
                                Remember(param.TypeIndex, "System.Collections.Generic.KeyValuePair<TKey, TValue>[]");
                            break;
                        case "System.Collections.Generic.IEnumerable<System.Collections.Generic.KeyValuePair<TKey,TValue>>.GetEnumerator":
                            Remember(method.ReturnTypeIndex, "System.Collections.Generic.IEnumerator<System.Collections.Generic.KeyValuePair<TKey, TValue>>");
                            break;
                        case "GetEnumerator":
                            Remember(method.ReturnTypeIndex, "System.Collections.Generic.Dictionary<TKey, TValue>.Enumerator");
                            break;
                        case ".ctor":
                            foreach (var param in methodParams)
                            {
                                if (param.Name == "dictionary")
                                    Remember(param.TypeIndex, "System.Collections.Generic.IDictionary<TKey, TValue>");
                                else if (param.Name == "collection")
                                    Remember(param.TypeIndex, "System.Collections.Generic.IEnumerable<System.Collections.Generic.KeyValuePair<TKey, TValue>>");
                            }
                            break;
                    }

                    if (method.Name.Contains("KeyValuePair", StringComparison.Ordinal) ||
                        methodParams.Any(param => param.Name == "keyValuePair"))
                    {
                        foreach (var param in methodParams.Where(param => param.Name == "keyValuePair"))
                            Remember(param.TypeIndex, "System.Collections.Generic.KeyValuePair<TKey, TValue>");
                    }
                }
                break;
        }

        return inferred;
    }

    private Dictionary<uint, string> BuildCollectionLikeTypeMap(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyList<FieldDefinition> fieldRows,
        IReadOnlyDictionary<uint, string> localTypeNames)
    {
        IReadOnlyDictionary<uint, string> knownTypeNames =
            localTypeNames.Count == 0
                ? _globalTypeNames
                : new TypeNameLookup(_globalTypeNames, localTypeNames);
        var singularMemberTypes = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var inferred = new Dictionary<uint, string>();

        void RememberKnown(string memberName, string? typeName)
        {
            if (string.IsNullOrWhiteSpace(memberName) || string.IsNullOrWhiteSpace(typeName))
                return;
            if (typeName!.StartsWith("Type_0x", StringComparison.Ordinal) ||
                YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(typeName))
            {
                return;
            }

            singularMemberTypes[memberName] = YldaResolutionUtilities.NormalizeTypeCandidate(typeName);
        }

        foreach (var method in methodRows)
        {
            var methodParams = GetMethodParameters(method);
            if (knownTypeNames.TryGetValue(method.ReturnTypeIndex, out var knownReturnType))
            {
                if (method.Name.StartsWith("get_", StringComparison.Ordinal))
                    RememberKnown(method.Name[4..], knownReturnType);
                else if (method.Name.StartsWith("Get", StringComparison.Ordinal) &&
                         methodParams.Count == 1 &&
                         methodParams[0].Name is "index" or "j")
                {
                    RememberKnown(method.Name[3..], knownReturnType);
                }
            }
        }

        void RememberCollection(uint typeIndex, string memberName)
        {
            if (!YldaResolutionUtilities.TrySingularizeCollectionName(memberName, out var singularName))
                return;
            if (!singularMemberTypes.TryGetValue(singularName, out var elementType))
                return;

            inferred[typeIndex] = elementType + "[]";
        }

        void RememberReferenceCollectionDefault(uint typeIndex, string memberName)
        {
            if (!YldaResolutionUtilities.TrySingularizeCollectionName(memberName, out _) ||
                !YldaResolutionUtilities.LooksLikeReferenceSemanticName(memberName))
            {
                return;
            }

            if (knownTypeNames.TryGetValue(typeIndex, out var existingTypeName) &&
                !YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(existingTypeName) &&
                !existingTypeName.StartsWith("Type_0x", StringComparison.Ordinal))
            {
                return;
            }

            inferred[typeIndex] = "System.String[]";
        }

        foreach (var field in fieldRows)
        {
            if (YldaResolutionUtilities.BackingFieldPropertyName(field.Name) is { } backingProperty)
            {
                RememberCollection(field.TypeIndex, backingProperty);
                RememberReferenceCollectionDefault(field.TypeIndex, backingProperty);
            }
        }

        foreach (var method in methodRows)
        {
            var methodParams = GetMethodParameters(method);

            if (method.Name.StartsWith("get_", StringComparison.Ordinal))
            {
                RememberCollection(method.ReturnTypeIndex, method.Name[4..]);
                RememberReferenceCollectionDefault(method.ReturnTypeIndex, method.Name[4..]);
            }
            else if (method.Name.StartsWith("set_", StringComparison.Ordinal) && methodParams.Count > 0)
            {
                RememberCollection(methodParams[0].TypeIndex, method.Name[4..]);
                RememberReferenceCollectionDefault(methodParams[0].TypeIndex, method.Name[4..]);
            }

            foreach (var parameter in methodParams)
            {
                RememberCollection(parameter.TypeIndex, parameter.Name);
                RememberReferenceCollectionDefault(parameter.TypeIndex, parameter.Name);
            }
        }

        return inferred;
    }

    private static Dictionary<uint, string> InferFromExplicitInterface(
        string interfaceName,
        string methodName,
        MethodDefinition method,
        IReadOnlyList<ParameterDefinition> methodParams)
    {
        var inferred = new Dictionary<uint, string>();
        var parsed = YldaResolutionUtilities.ParseGenericType(interfaceName);
        var memberName = methodName[(methodName.LastIndexOf('.') + 1)..];
        if (parsed is null)
            return inferred;

        void Remember(uint typeIndex, string typeName)
        {
            if (typeIndex != uint.MaxValue)
                inferred[typeIndex] = typeName;
        }

        var (baseName, args) = parsed.Value;
        if (baseName == "System.Collections.Generic.IEnumerable" && args.Count == 1 && memberName == "GetEnumerator")
            Remember(method.ReturnTypeIndex, $"System.Collections.Generic.IEnumerator<{args[0]}>");
        else if (baseName == "System.Collections.Generic.IEnumerator" && args.Count == 1 && memberName == "get_Current")
            Remember(method.ReturnTypeIndex, args[0]);
        else if ((baseName == "System.Collections.Generic.IList" || baseName == "System.Collections.Generic.IReadOnlyList") && args.Count == 1)
        {
            if (memberName == "get_Item")
                Remember(method.ReturnTypeIndex, args[0]);
            else if (memberName == "set_Item" && methodParams.Count >= 2)
                Remember(methodParams[1].TypeIndex, args[0]);
        }
        else if ((baseName == "System.Collections.Generic.ICollection" || baseName == "System.Collections.Generic.IReadOnlyCollection") && args.Count == 1)
        {
            if ((memberName == "Add" || memberName == "Contains" || memberName == "Remove") && methodParams.Count > 0)
                Remember(methodParams[0].TypeIndex, args[0]);
            else if (memberName == "CopyTo" && methodParams.Count > 0)
                Remember(methodParams[0].TypeIndex, $"{args[0]}[]");
        }
        else if ((baseName == "System.Collections.Generic.IDictionary" || baseName == "System.Collections.Generic.IReadOnlyDictionary") && args.Count == 2)
        {
            var keyType = args[0];
            var valueType = args[1];
            if ((memberName == "ContainsKey" || memberName == "get_Item") && methodParams.Count > 0)
                Remember(methodParams[0].TypeIndex, keyType);

            if (memberName == "get_Item")
                Remember(method.ReturnTypeIndex, valueType);
            else if (memberName == "TryGetValue")
            {
                if (methodParams.Count > 0)
                    Remember(methodParams[0].TypeIndex, keyType);
                if (methodParams.Count > 1)
                    Remember(methodParams[1].TypeIndex, valueType);
            }
            else if (memberName == "get_Keys")
            {
                Remember(
                    method.ReturnTypeIndex,
                    baseName == "System.Collections.Generic.IReadOnlyDictionary"
                        ? $"System.Collections.Generic.IEnumerable<{keyType}>"
                        : $"System.Collections.Generic.ICollection<{keyType}>");
            }
            else if (memberName == "get_Values")
            {
                Remember(
                    method.ReturnTypeIndex,
                    baseName == "System.Collections.Generic.IReadOnlyDictionary"
                        ? $"System.Collections.Generic.IEnumerable<{valueType}>"
                        : $"System.Collections.Generic.ICollection<{valueType}>");
            }
        }

        return inferred;
    }

    private IReadOnlyList<ParameterDefinition> GetMethodParameters(MethodDefinition method)
        => _descriptors.GetParameters(method);
}
