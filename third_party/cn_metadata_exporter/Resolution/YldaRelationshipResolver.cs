using System.Collections.Concurrent;

namespace YldaDumpCsExporter;

internal sealed class YldaRelationshipResolver
{
    private readonly MetadataModel _model;
    private readonly IReadOnlyDictionary<uint, string> _globalTypeNames;
    private readonly Lazy<Dictionary<string, IReadOnlyList<InterfaceContract>>> _interfaceCandidateIndex;
    private readonly Lazy<Dictionary<string, IReadOnlyList<int>>> _baseCandidateIndex;
    private readonly Dictionary<uint, TypeDefinition> _typesBySemanticIndex;
    private readonly Dictionary<string, TypeDefinition> _typesByFullName;
    private readonly Dictionary<int, int> _nestedParentByChild;
    private readonly ConcurrentDictionary<int, int> _structuralBaseByType = [];
    private readonly ConcurrentDictionary<int, sbyte> _overrideByMethodIndex = [];
    private readonly TypeDescriptorIndex _descriptors;

    public YldaRelationshipResolver(MetadataModel model, YldaTypeResolver typeResolver, TypeDescriptorIndex descriptors)
    {
        _model = model;
        _descriptors = descriptors;
        _globalTypeNames = typeResolver.GlobalTypeNames;
        _typesBySemanticIndex = BuildTypeLookup(model.Types);
        _typesByFullName = model.Types
            .GroupBy(type => type.FullName, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.OrderBy(type => type.Index).First(), StringComparer.Ordinal);
        _nestedParentByChild = BuildNestedParentMap(model.Types, model.NestedTypes);
        _interfaceCandidateIndex = new Lazy<Dictionary<string, IReadOnlyList<InterfaceContract>>>(
            () => BuildInterfaceCandidateIndex(BuildInterfaceContracts(model.Types, model.Methods, model.Parameters, typeResolver.GlobalTypeNames)));
        _baseCandidateIndex = new Lazy<Dictionary<string, IReadOnlyList<int>>>(BuildBaseCandidateIndex);
    }

    public string? ResolveDeclaringType(TypeDefinition type, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (_nestedParentByChild.TryGetValue(type.Index, out var parentTypeIndex))
            return _model.Types[parentTypeIndex].FullName;

        var ownerIndex = type.DeclaringTypeIndexHint;
        if (ownerIndex == uint.MaxValue || ownerIndex == type.PrimaryTypeIndex || ownerIndex == type.SecondaryTypeIndex)
            return null;

        var ownerName = typeNameMap.GetValueOrDefault(ownerIndex) ?? _globalTypeNames.GetValueOrDefault(ownerIndex);
        return YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(ownerName) ? null : ownerName;
    }

    public TypeRelationships ResolveTypeRelationships(TypeDefinition type, IReadOnlyList<MethodDefinition> methodRows, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var baseType = ResolveBaseType(type, typeNameMap);
        var interfaces = ResolveInterfaces(type, methodRows, typeNameMap).ToList();
        var comments = ResolveSpecialComments(type, methodRows, baseType, interfaces).ToArray();
        return new TypeRelationships(baseType, interfaces, comments);
    }

    public IReadOnlyList<string> ResolveTypeModifiers(TypeDefinition type)
    {
        var flags = type.Flags;
        var modifiers = new List<string>
        {
            (flags & YldaResolutionConstants.TypeAttrVisibilityMask) switch
            {
                YldaResolutionConstants.TypeAttrPublic or YldaResolutionConstants.TypeAttrNestedPublic => "public",
                YldaResolutionConstants.TypeAttrNestedPrivate => "private",
                YldaResolutionConstants.TypeAttrNestedFamily => "protected",
                YldaResolutionConstants.TypeAttrNestedAssembly => "internal",
                YldaResolutionConstants.TypeAttrNestedFamAndAssem => "private protected",
                YldaResolutionConstants.TypeAttrNestedFamOrAssem => "protected internal",
                _ => "internal",
            }
        };

        if ((flags & YldaResolutionConstants.TypeAttrInterface) != 0)
        {
            modifiers.Add("interface");
            return modifiers;
        }

        var bitfield = type.Bitfield;
        var isEnum = (bitfield & 0x2) != 0;
        var isStruct = !isEnum && (bitfield & 0x1) != 0;

        if (isEnum)
        {
            modifiers.Add("enum");
            return modifiers;
        }

        if (isStruct)
        {
            modifiers.Add("struct");
            return modifiers;
        }

        var isAbstract = (flags & YldaResolutionConstants.TypeAttrAbstract) != 0;
        var isSealed = (flags & YldaResolutionConstants.TypeAttrSealed) != 0;
        if (isAbstract && isSealed)
            modifiers.Add("static");
        else
        {
            if (isAbstract)
                modifiers.Add("abstract");
            if (isSealed)
                modifiers.Add("sealed");
        }

        modifiers.Add("class");
        return modifiers;
    }

    public IReadOnlyList<string> ResolveMethodModifiers(MethodDefinition method, bool? confirmedOverride = null)
    {
        var modifiers = new List<string>
        {
            YldaResolutionUtilities.AccessibilityModifier(ResolveMethodAccessibility(method))
        };

        if ((method.Flags & YldaResolutionConstants.MethodAttrStatic) != 0)
            modifiers.Add("static");

        var isAbstract = (method.Flags & YldaResolutionConstants.MethodAttrAbstract) != 0;
        var isVirtual = (method.Flags & YldaResolutionConstants.MethodAttrVirtual) != 0;
        var isFinal = (method.Flags & YldaResolutionConstants.MethodAttrFinal) != 0;

        if (isAbstract)
            modifiers.Add("abstract");
        else if (isVirtual)
        {
            if (confirmedOverride == true)
            {
                if (isFinal)
                    modifiers.Add("sealed");
                modifiers.Add("override");
            }
            else
            {
                modifiers.Add("virtual");
            }
        }

        var codeType = (ushort)(method.ImplFlags & YldaResolutionConstants.MethodImplCodeTypeMask);
        if ((method.ImplFlags & YldaResolutionConstants.MethodImplInternalCall) != 0 ||
            codeType is YldaResolutionConstants.MethodImplNative or YldaResolutionConstants.MethodImplRuntime)
        {
            modifiers.Add("extern");
        }

        return modifiers;
    }

    public ExportMemberAccessibility ResolveMethodAccessibility(MethodDefinition method)
        => YldaResolutionUtilities.MethodAccessibility(method.Flags);

    public ExportMemberAccessibility ResolvePropertyAccessibility(TypeDefinition type, PropertyDefinition property)
    {
        var accessors = new List<MethodDefinition>();
        if (property.GetterDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)property.GetterDelta]);
        if (property.SetterDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)property.SetterDelta]);
        if (accessors.Count == 0)
            return ExportMemberAccessibility.Private;

        return accessors
            .Select(ResolveMethodAccessibility)
            .OrderByDescending(accessibility => YldaResolutionUtilities.AccessModifierRank(YldaResolutionUtilities.AccessibilityModifier(accessibility)))
            .First();
    }

    public ExportMemberAccessibility ResolveEventAccessibility(TypeDefinition type, EventDefinition evt)
    {
        var accessors = new List<MethodDefinition>();
        if (evt.AddDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)evt.AddDelta]);
        if (evt.RemoveDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)evt.RemoveDelta]);
        if (evt.RaiseDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)evt.RaiseDelta]);
        if (accessors.Count == 0)
            return ExportMemberAccessibility.Private;

        return accessors
            .Select(ResolveMethodAccessibility)
            .OrderByDescending(accessibility => YldaResolutionUtilities.AccessModifierRank(YldaResolutionUtilities.AccessibilityModifier(accessibility)))
            .First();
    }

    public IReadOnlyList<string> ResolvePropertyModifiers(TypeDefinition type, PropertyDefinition property, bool? confirmedOverride = null)
    {
        var accessors = new List<MethodDefinition>();
        if (property.GetterDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)property.GetterDelta]);
        if (property.SetterDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)property.SetterDelta]);
        if (accessors.Count == 0)
            return ["private"];

        var baseModifiers = ResolveMethodModifiers(accessors[0], confirmedOverride).ToList();
        baseModifiers[0] = YldaResolutionUtilities.AccessibilityModifier(ResolvePropertyAccessibility(type, property));

        return baseModifiers.Where(modifier => modifier != "extern").ToArray();
    }

    public IReadOnlyList<string> ResolveEventModifiers(TypeDefinition type, EventDefinition evt, bool? confirmedOverride = null)
    {
        var accessors = new List<MethodDefinition>();
        if (evt.AddDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)evt.AddDelta]);
        if (evt.RemoveDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)evt.RemoveDelta]);
        if (evt.RaiseDelta != uint.MaxValue)
            accessors.Add(_model.Methods[type.FirstMethodIndex + (int)evt.RaiseDelta]);
        if (accessors.Count == 0)
            return ["private"];

        var baseModifiers = ResolveMethodModifiers(accessors[0], confirmedOverride).ToList();
        baseModifiers[0] = YldaResolutionUtilities.AccessibilityModifier(ResolveEventAccessibility(type, evt));

        return baseModifiers.Where(modifier => modifier != "extern").ToArray();
    }

    public bool? ResolveOverride(TypeDefinition type, MethodDefinition method, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (_overrideByMethodIndex.TryGetValue(method.Index, out var cached))
            return DecodeOverrideCache(cached);

        if ((method.Flags & YldaResolutionConstants.MethodAttrVirtual) == 0)
        {
            _overrideByMethodIndex[method.Index] = EncodeOverrideCache(false);
            return false;
        }
        if ((method.Flags & YldaResolutionConstants.MethodAttrNewSlot) != 0)
        {
            _overrideByMethodIndex[method.Index] = EncodeOverrideCache(false);
            return false;
        }

        if (MatchesBaseOverrideChain(type, method, typeNameMap))
        {
            _overrideByMethodIndex[method.Index] = EncodeOverrideCache(true);
            return true;
        }
        if (MatchesInterfaceContract(type, method, typeNameMap))
        {
            _overrideByMethodIndex[method.Index] = EncodeOverrideCache(true);
            return true;
        }

        _overrideByMethodIndex[method.Index] = EncodeOverrideCache(null);
        return null;
    }

    private string? ResolveBaseType(TypeDefinition type, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (ResolveBaseTypeDefinition(type, typeNameMap) is not { } baseType)
            return null;

        return baseType.FullName;
    }

    private IReadOnlyList<string> ResolveInterfaces(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var interfaces = ResolveMetadataInterfaces(type, typeNameMap).ToList();

        foreach (var explicitInterface in methodRows
                     .Select(method => YldaResolutionUtilities.ExplicitInterfacePrefix(method.Name))
                     .Where(prefix => !string.IsNullOrWhiteSpace(prefix))
                     .Select(prefix => prefix!)
                     .Distinct(StringComparer.Ordinal))
        {
            if (!interfaces.Contains(explicitInterface, StringComparer.Ordinal))
                interfaces.Add(explicitInterface);
        }

        var shouldTryStructural =
            TypeKind(type) == "class" &&
            methodRows.Count >= 5 &&
            (interfaces.Count == 0 || IsFutureLikeInterfaceCarrier(type, methodRows));
        if (!shouldTryStructural)
            return interfaces;

        foreach (var interfaceName in InferStructuralInterfaces(type, methodRows, typeNameMap))
        {
            if (!interfaces.Contains(interfaceName, StringComparer.Ordinal))
                interfaces.Add(interfaceName);
        }

        return interfaces;
    }

    private static bool IsFutureLikeInterfaceCarrier(TypeDefinition type, IReadOnlyList<MethodDefinition> methodRows)
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

    private IEnumerable<string> ResolveSpecialComments(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        string? baseType,
        IReadOnlyList<string> interfaces)
    {
        if (type.Name == "<>c")
            yield return "CompilerGenerated: lambda cache holder";
        else if (type.Name.Contains("DisplayClass", StringComparison.Ordinal))
            yield return "CompilerGenerated: closure display class";
        else if (type.Name.Contains("d__", StringComparison.Ordinal))
        {
            yield return "CompilerGenerated: state machine";
            if (interfaces.Any(name => name.StartsWith("System.Collections.Generic.IEnumerator", StringComparison.Ordinal) || name == "System.Collections.IEnumerator"))
                yield return "StateMachineKind: IEnumerator";
        }

        if (baseType == "System.MulticastDelegate" && methodRows.Any(method => method.Name == "Invoke"))
            yield return "DelegateType";
    }

    private IReadOnlyList<InterfaceContract> BuildInterfaceContracts(
        IReadOnlyList<TypeDefinition> typeDefs,
        IReadOnlyList<MethodDefinition> methods,
        IReadOnlyList<ParameterDefinition> parameters,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        _ = methods;

        var contracts = new List<InterfaceContract>();
        foreach (var type in typeDefs)
        {
            if (TypeKind(type) != "interface")
                continue;

            var methodRows = IterTypeMethods(type).ToArray();
            if (methodRows.Length == 0)
                continue;

            var members = new HashSet<string>(StringComparer.Ordinal);
            var memberNames = new HashSet<string>(StringComparer.Ordinal);
            foreach (var method in methodRows)
            {
                members.Add(YldaResolutionUtilities.MethodContractKeyForResolvedParameters(method, GetMethodParameters(method), typeNameMap));
                memberNames.Add(method.Name);
            }

            if (members.Count > 0)
                contracts.Add(new InterfaceContract(type.FullName, memberNames, members, memberNames.Count));
        }

        return contracts;
    }

    private static Dictionary<string, IReadOnlyList<InterfaceContract>> BuildInterfaceCandidateIndex(
        IReadOnlyList<InterfaceContract> interfaceContracts)
    {
        var grouped = new Dictionary<string, List<InterfaceContract>>(StringComparer.Ordinal);
        foreach (var contract in interfaceContracts)
        {
            foreach (var memberName in contract.MemberNames)
            {
                if (!grouped.TryGetValue(memberName, out var contracts))
                {
                    contracts = [];
                    grouped[memberName] = contracts;
                }

                contracts.Add(contract);
            }
        }

        return grouped.ToDictionary(
            pair => pair.Key,
            pair => (IReadOnlyList<InterfaceContract>)pair.Value,
            StringComparer.Ordinal);
    }

    private IEnumerable<string> ResolveMetadataInterfaces(TypeDefinition type, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (type.InterfaceCount <= 0 || type.InterfacesStart < 0)
            yield break;

        for (var i = 0; i < type.InterfaceCount; i++)
        {
            var interfaceRowIndex = type.InterfacesStart + i;
            if (interfaceRowIndex < 0 || interfaceRowIndex >= _model.Interfaces.Count)
                break;

            var interfaceTypeIndex = _model.Interfaces[interfaceRowIndex].TypeIndex;
            var interfaceName = typeNameMap.GetValueOrDefault(interfaceTypeIndex) ?? _globalTypeNames.GetValueOrDefault(interfaceTypeIndex);
            if (string.IsNullOrWhiteSpace(interfaceName) ||
                interfaceName.StartsWith("Type_0x", StringComparison.Ordinal) ||
                YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(interfaceName))
            {
                continue;
            }

            yield return interfaceName;
        }
    }

    private IReadOnlyList<string> InferStructuralInterfaces(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (TypeKind(type) == "interface")
            return [];

        var classMembers = new HashSet<string>(StringComparer.Ordinal);
        var classMemberNames = new HashSet<string>(StringComparer.Ordinal);
        foreach (var method in methodRows)
        {
            foreach (var key in YldaResolutionUtilities.ExpandedMethodContractKeysForResolvedParameters(method, GetMethodParameters(method), typeNameMap))
                classMembers.Add(key);

            classMemberNames.Add(method.Name);
            if (method.Name.Contains('.') && !method.Name.StartsWith('<'))
                classMemberNames.Add(method.Name[(method.Name.LastIndexOf('.') + 1)..]);
        }

        var classMemberCount = classMemberNames.Count;

        var candidates = new HashSet<InterfaceContract>();
        foreach (var memberName in classMemberNames)
        {
            if (_interfaceCandidateIndex.Value.TryGetValue(memberName, out var contracts))
            {
                foreach (var contract in contracts)
                    candidates.Add(contract);
            }
        }

        var matches = new List<string>();
        foreach (var contract in candidates)
        {
            if (contract.Members.Count <= 1)
                continue;
            if (contract.MemberCount > classMemberCount)
                continue;
            if (string.Equals(contract.FullName, type.FullName, StringComparison.Ordinal))
                continue;
            if (!contract.MemberNames.All(classMemberNames.Contains))
                continue;
            if (contract.Members.All(classMembers.Contains))
                matches.Add(contract.FullName);
        }

        return matches.Distinct(StringComparer.Ordinal).OrderBy(name => name, StringComparer.Ordinal).ToArray();
    }

    private bool MatchesBaseOverrideChain(TypeDefinition type, MethodDefinition method, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        var visited = new HashSet<int>();
        TypeDefinition? currentBaseType = ResolveBaseTypeDefinition(type, typeNameMap);
        while (currentBaseType is { } baseType && visited.Add(baseType.Index))
        {
            foreach (var candidate in IterTypeMethods(baseType))
            {
                if (!MethodSignaturesCompatible(method, candidate, typeNameMap))
                    continue;
                return true;
            }

            currentBaseType = ResolveBaseTypeDefinition(baseType, typeNameMap);
        }

        return false;
    }

    private TypeDefinition? ResolveBaseTypeDefinition(TypeDefinition type, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (TryResolveHintedBaseType(type, typeNameMap, out var hintedBaseType))
            return hintedBaseType;

        if (TryResolveAssetObjectBase(type, out var assetObjectBase))
            return assetObjectBase;

        if (TryResolveDelegateBase(type, out var multicastDelegateBase))
            return multicastDelegateBase;

        if (type.Name.Contains('`', StringComparison.Ordinal))
            return null;

        return InferStructuralBaseType(type, typeNameMap);
    }

    private bool TryResolveHintedBaseType(
        TypeDefinition type,
        IReadOnlyDictionary<uint, string> typeNameMap,
        out TypeDefinition? baseType)
    {
        baseType = null;

        var baseIndex = type.BaseTypeIndexHint;
        if (baseIndex == uint.MaxValue)
            return false;
        if (!_typesBySemanticIndex.TryGetValue(baseIndex, out var candidate))
            return false;

        var baseTypeName = typeNameMap.GetValueOrDefault(baseIndex) ?? _globalTypeNames.GetValueOrDefault(baseIndex);
        if (!IsValidBaseTypeName(baseTypeName))
            return false;

        baseType = candidate;
        return true;
    }

    private TypeDefinition? InferStructuralBaseType(TypeDefinition type, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (_structuralBaseByType.TryGetValue(type.Index, out var cached))
            return DecodeStructuralBaseCache(cached);

        if (TypeKind(type) != "class")
        {
            _structuralBaseByType[type.Index] = -1;
            return null;
        }

        var overrideLikeMethods = IterTypeMethods(type)
            .Where(method =>
                (method.Flags & YldaResolutionConstants.MethodAttrVirtual) != 0 &&
                (method.Flags & YldaResolutionConstants.MethodAttrNewSlot) == 0)
            .ToArray();
        if (overrideLikeMethods.Length < 5)
        {
            overrideLikeMethods = IterTypeMethods(type)
                .Where(method => (method.Flags & YldaResolutionConstants.MethodAttrVirtual) != 0)
                .ToArray();
        }
        if (overrideLikeMethods.Length < 5)
        {
            _structuralBaseByType[type.Index] = -1;
            return null;
        }

        TypeDefinition? bestCandidate = null;
        var bestStrongScore = 0;
        var secondStrongScore = 0;
        var bestWeakScore = 0;
        var secondWeakScore = 0;

        var candidateIndices = new HashSet<int>();
        foreach (var method in overrideLikeMethods)
        {
            if (_baseCandidateIndex.Value.TryGetValue(BaseCandidateKey(method), out var narrowedCandidates))
            {
                foreach (var candidateIndex in narrowedCandidates)
                    candidateIndices.Add(candidateIndex);
            }
        }

        if (candidateIndices.Count == 0)
        {
            _structuralBaseByType[type.Index] = -1;
            return null;
        }

        foreach (var candidateIndex in candidateIndices)
        {
            var candidate = _model.Types[candidateIndex];
            if (candidate.Index == type.Index || TypeKind(candidate) != "class" || candidate.MethodCount <= 0)
                continue;
            if (!IsValidBaseTypeName(candidate.FullName))
                continue;

            var strongScore = 0;
            var weakScore = 0;
            foreach (var method in overrideLikeMethods)
            {
                foreach (var candidateMethod in IterTypeMethods(candidate))
                {
                    if (MethodSignaturesCompatible(method, candidateMethod, typeNameMap))
                    {
                        strongScore++;
                        weakScore++;
                        break;
                    }

                    if (NormalizeMethodName(method.Name) == NormalizeMethodName(candidateMethod.Name) &&
                        method.ParameterCount == candidateMethod.ParameterCount)
                    {
                        weakScore++;
                        break;
                    }
                }
            }

            if (strongScore > bestStrongScore || (strongScore == bestStrongScore && weakScore > bestWeakScore))
            {
                secondStrongScore = bestStrongScore;
                secondWeakScore = bestWeakScore;
                bestStrongScore = strongScore;
                bestWeakScore = weakScore;
                bestCandidate = candidate;
            }
            else if (strongScore > secondStrongScore || (strongScore == secondStrongScore && weakScore > secondWeakScore))
            {
                secondStrongScore = strongScore;
                secondWeakScore = weakScore;
            }
        }

        if (bestCandidate is null ||
            (bestStrongScore < 5 && bestWeakScore < 8) ||
            (secondStrongScore > 0 &&
             bestStrongScore < secondStrongScore + 3 &&
             bestStrongScore < secondStrongScore * 2 &&
             bestWeakScore < secondWeakScore + 4))
        {
            _structuralBaseByType[type.Index] = -1;
            return null;
        }

        _structuralBaseByType[type.Index] = bestCandidate.Value.Index;
        return bestCandidate.Value;
    }

    private bool TryResolveAssetObjectBase(TypeDefinition type, out TypeDefinition? baseType)
    {
        baseType = null;
        if (!_typesByFullName.TryGetValue("AssetObjectBase", out var assetObjectBase))
            return false;
        if (type.Index == assetObjectBase.Index)
            return false;

        var contractMembers = new HashSet<string>(StringComparer.Ordinal)
        {
            "get_StackCount",
            "set_StackCount",
            "get_HasLevel",
            "get_IsStackable",
            "get_LevelUpFeedCostCurrency",
            "get_LevelUpFeedCostAmount",
            "get_LevelUpFeedExp",
            "get_TypeSprite",
            "get_TextureDir",
            "get_CanBeConsumed",
            "get_IsValid",
        };

        var matches = IterTypeMethods(type)
            .Select(method => method.Name)
            .Count(contractMembers.Contains);
        if (matches < 7)
            return false;

        baseType = assetObjectBase;
        return true;
    }

    private bool TryResolveDelegateBase(TypeDefinition type, out TypeDefinition? baseType)
    {
        baseType = null;

        if (TypeKind(type) != "class")
            return false;

        var methodRows = IterTypeMethods(type).ToArray();
        var names = methodRows.Select(method => method.Name).ToHashSet(StringComparer.Ordinal);
        if (!names.Contains(".ctor") || !names.Contains("Invoke") || !names.Contains("BeginInvoke") || !names.Contains("EndInvoke"))
            return false;

        if (!_typesByFullName.TryGetValue("System.MulticastDelegate", out var delegateType))
            return false;

        baseType = delegateType;
        return true;
    }

    private bool MatchesInterfaceContract(TypeDefinition type, MethodDefinition method, IReadOnlyDictionary<uint, string> typeNameMap)
    {
        if (type.InterfaceCount <= 0 || type.InterfacesStart < 0)
            return false;

        for (var i = 0; i < type.InterfaceCount; i++)
        {
            var interfaceRowIndex = type.InterfacesStart + i;
            if (interfaceRowIndex < 0 || interfaceRowIndex >= _model.Interfaces.Count)
                break;

            var interfaceTypeIndex = _model.Interfaces[interfaceRowIndex].TypeIndex;
            if (!_typesBySemanticIndex.TryGetValue(interfaceTypeIndex, out var interfaceType))
                continue;

            foreach (var candidate in IterTypeMethods(interfaceType))
            {
                if (!MethodSignaturesCompatible(method, candidate, typeNameMap))
                    continue;
                return true;
            }
        }

        return false;
    }

    private bool MethodSignaturesCompatible(
        MethodDefinition currentMethod,
        MethodDefinition candidateMethod,
        IReadOnlyDictionary<uint, string> localTypeNameMap)
    {
        if (currentMethod.Slot != candidateMethod.Slot)
            return false;
        if (NormalizeMethodName(currentMethod.Name) != NormalizeMethodName(candidateMethod.Name))
            return false;
        if (currentMethod.ParameterCount != candidateMethod.ParameterCount)
            return false;

        var currentReturn = NormalizeResolvedType(localTypeNameMap.GetValueOrDefault(currentMethod.ReturnTypeIndex) ?? _globalTypeNames.GetValueOrDefault(currentMethod.ReturnTypeIndex));
        var candidateReturn = NormalizeResolvedType(_globalTypeNames.GetValueOrDefault(candidateMethod.ReturnTypeIndex));
        if (!string.Equals(currentReturn, candidateReturn, StringComparison.Ordinal))
            return false;

        var currentParameters = GetMethodParameters(currentMethod);
        var candidateParameters = GetMethodParameters(candidateMethod);
        for (var i = 0; i < currentParameters.Count; i++)
        {
            var currentParameterType = NormalizeResolvedType(localTypeNameMap.GetValueOrDefault(currentParameters[i].TypeIndex) ?? _globalTypeNames.GetValueOrDefault(currentParameters[i].TypeIndex));
            var candidateParameterType = NormalizeResolvedType(_globalTypeNames.GetValueOrDefault(candidateParameters[i].TypeIndex));
            if (!string.Equals(currentParameterType, candidateParameterType, StringComparison.Ordinal))
                return false;
        }

        return true;
    }

    private static string NormalizeMethodName(string methodName)
        => methodName.Contains('.') && !methodName.StartsWith('<')
            ? methodName[(methodName.LastIndexOf('.') + 1)..]
            : methodName;

    private static string BaseCandidateKey(MethodDefinition method)
        => $"{NormalizeMethodName(method.Name)}#{method.ParameterCount}";

    private static string? NormalizeResolvedType(string? typeName)
    {
        if (string.IsNullOrWhiteSpace(typeName))
            return null;
        if (typeName.StartsWith("Type_0x", StringComparison.Ordinal))
            return null;
        return YldaResolutionUtilities.NormalizeTypeCandidate(typeName!);
    }

    private static bool IsValidBaseTypeName(string? typeName)
    {
        if (string.IsNullOrWhiteSpace(typeName))
            return false;
        if (typeName.StartsWith("Type_0x", StringComparison.Ordinal))
            return false;
        if (YldaResolutionUtilities.IsPrimitiveOrVoidTypeName(typeName))
            return false;
        return !string.Equals(typeName, "System.Object", StringComparison.Ordinal) &&
               !string.Equals(typeName, "object", StringComparison.Ordinal);
    }

    private TypeDefinition? DecodeStructuralBaseCache(int cachedTypeIndex)
        => cachedTypeIndex >= 0 && cachedTypeIndex < _model.Types.Count
            ? _model.Types[cachedTypeIndex]
            : null;

    private static sbyte EncodeOverrideCache(bool? value)
        => value switch
        {
            true => 1,
            false => 0,
            _ => -1,
        };

    private static bool? DecodeOverrideCache(sbyte value)
        => value switch
        {
            1 => true,
            0 => false,
            _ => null,
        };

    private IEnumerable<MethodDefinition> IterTypeMethods(TypeDefinition type)
    {
        return _descriptors.GetMethods(type);
    }

    private IReadOnlyList<ParameterDefinition> GetMethodParameters(MethodDefinition method)
        => _descriptors.GetParameters(method);

    private Dictionary<string, IReadOnlyList<int>> BuildBaseCandidateIndex()
    {
        var grouped = new Dictionary<string, HashSet<int>>(StringComparer.Ordinal);
        foreach (var type in _model.Types)
        {
            if (TypeKind(type) != "class" || type.MethodCount <= 0)
                continue;
            if (!IsValidBaseTypeName(type.FullName))
                continue;

            foreach (var method in IterTypeMethods(type))
            {
                if ((method.Flags & YldaResolutionConstants.MethodAttrVirtual) == 0)
                    continue;

                var key = BaseCandidateKey(method);
                if (!grouped.TryGetValue(key, out var candidateTypes))
                {
                    candidateTypes = [];
                    grouped[key] = candidateTypes;
                }

                candidateTypes.Add(type.Index);
            }
        }

        return grouped.ToDictionary(
            pair => pair.Key,
            pair => (IReadOnlyList<int>)pair.Value.OrderBy(index => index).ToArray(),
            StringComparer.Ordinal);
    }

    private static Dictionary<uint, TypeDefinition> BuildTypeLookup(IReadOnlyList<TypeDefinition> types)
    {
        var lookup = new Dictionary<uint, TypeDefinition>();
        foreach (var type in types)
        {
            if (type.PrimaryTypeIndex != uint.MaxValue)
                lookup[type.PrimaryTypeIndex] = type;
            if (type.SecondaryTypeIndex != uint.MaxValue)
                lookup[type.SecondaryTypeIndex] = type;
        }

        return lookup;
    }

    private static Dictionary<int, int> BuildNestedParentMap(IReadOnlyList<TypeDefinition> types, IReadOnlyList<NestedTypeEntry> nestedTypes)
    {
        var map = new Dictionary<int, int>();
        foreach (var type in types)
        {
            if (type.NestedTypeCount <= 0 || type.NestedTypesStart < 0)
                continue;

            for (var i = 0; i < type.NestedTypeCount; i++)
            {
                var nestedIndex = type.NestedTypesStart + i;
                if (nestedIndex < 0 || nestedIndex >= nestedTypes.Count)
                    break;

                var childTypeIndex = unchecked((int)nestedTypes[nestedIndex].TypeIndex);
                if (childTypeIndex < 0 || childTypeIndex >= types.Count)
                    continue;

                map[childTypeIndex] = type.Index;
            }
        }

        return map;
    }

    private static string TypeKind(TypeDefinition type)
    {
        var flags = type.Flags;
        var bitfield = type.Bitfield;
        if ((bitfield & 0x2) != 0)
            return "enum";
        if ((flags & YldaResolutionConstants.TypeAttrInterface) != 0)
            return "interface";
        if ((bitfield & 0x1) != 0)
            return "struct";
        return "class";
    }
}
