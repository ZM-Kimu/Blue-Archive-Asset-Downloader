namespace YldaDumpCsExporter;

internal sealed class TypeDescriptorIndexBuilder
{
    private readonly MetadataModel _model;

    public TypeDescriptorIndexBuilder(MetadataModel model)
    {
        _model = model;
    }

    public TypeDescriptorIndex Build()
    {
        var methodsByType = new Dictionary<int, MethodDefinition[]>(_model.Types.Count);
        var fieldsByType = new Dictionary<int, FieldDefinition[]>(_model.Types.Count);
        var propertiesByType = new Dictionary<int, PropertyDefinition[]>(_model.Types.Count);
        var eventsByType = new Dictionary<int, EventDefinition[]>(_model.Types.Count);
        var methodParametersByMethodIndex = new Dictionary<int, ParameterDefinition[]>(_model.Methods.Count);
        var propertyTypeIndicesByType = new Dictionary<int, Dictionary<string, uint>>(_model.Types.Count);
        var imageNameByType = BuildImageNameIndex();
        var referencedTypeIndicesByType = new Dictionary<int, uint[]>(_model.Types.Count);
        var hintsByType = new Dictionary<int, TypeDescriptorHints>(_model.Types.Count);

        foreach (var method in _model.Methods)
            methodParametersByMethodIndex[method.Index] = Slice(_model.Parameters, unchecked((int)method.ParameterStart), method.ParameterCount);

        foreach (var type in _model.Types)
        {
            methodsByType[type.Index] = Slice(_model.Methods, type.FirstMethodIndex, type.MethodCount);
            fieldsByType[type.Index] = Slice(_model.Fields, type.FirstFieldIndex, type.FieldCount);
            propertiesByType[type.Index] = Slice(_model.Properties, type.FirstPropertyIndex, type.PropertyCount);
            eventsByType[type.Index] = Slice(_model.Events, type.FirstEventIndex, type.EventCount);
            propertyTypeIndicesByType[type.Index] = BuildPropertyTypeIndexMap(type, propertiesByType[type.Index]);
            referencedTypeIndicesByType[type.Index] = BuildReferencedTypeIndices(
                methodsByType[type.Index],
                fieldsByType[type.Index],
                methodParametersByMethodIndex,
                propertyTypeIndicesByType[type.Index]);
            hintsByType[type.Index] = BuildHints(type, methodsByType[type.Index], fieldsByType[type.Index], propertiesByType[type.Index]);
        }

        return new TypeDescriptorIndex(
            methodsByType,
            fieldsByType,
            propertiesByType,
            eventsByType,
            methodParametersByMethodIndex,
            propertyTypeIndicesByType,
            imageNameByType,
            referencedTypeIndicesByType,
            hintsByType);
    }

    private Dictionary<int, string> BuildImageNameIndex()
    {
        var imageNameByType = new Dictionary<int, string>(_model.Types.Count);
        foreach (var image in _model.Images)
        {
            var end = image.EndTypeIndexExclusive;
            for (var typeIndex = image.FirstTypeIndex; typeIndex < end; typeIndex++)
                imageNameByType[typeIndex] = image.DllName;
        }

        return imageNameByType;
    }

    private uint[] BuildReferencedTypeIndices(
        IReadOnlyList<MethodDefinition> methods,
        IReadOnlyList<FieldDefinition> fields,
        IReadOnlyDictionary<int, ParameterDefinition[]> methodParametersByMethodIndex,
        IReadOnlyDictionary<string, uint> propertyTypeIndices)
    {
        var indices = new HashSet<uint>();

        foreach (var field in fields)
        {
            if (field.TypeIndex != uint.MaxValue)
                indices.Add(field.TypeIndex);
        }

        foreach (var method in methods)
        {
            if (method.ReturnTypeIndex != uint.MaxValue)
                indices.Add(method.ReturnTypeIndex);

            if (!methodParametersByMethodIndex.TryGetValue(method.Index, out var parameters))
                continue;

            foreach (var parameter in parameters)
            {
                if (parameter.TypeIndex != uint.MaxValue)
                    indices.Add(parameter.TypeIndex);
            }
        }

        foreach (var propertyTypeIndex in propertyTypeIndices.Values)
        {
            if (propertyTypeIndex != uint.MaxValue)
                indices.Add(propertyTypeIndex);
        }

        return indices.Count == 0 ? [] : indices.ToArray();
    }

    private static TypeDescriptorHints BuildHints(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methods,
        IReadOnlyList<FieldDefinition> fields,
        IReadOnlyList<PropertyDefinition> properties)
    {
        var hasExplicitInterfaces = false;
        var hasFlatBufferAssignOrRoot = false;
        var hasByteBufferAccessor = false;
        var hasInitKeyMethod = false;
        var hasCollectionLikeMembers = false;

        foreach (var method in methods)
        {
            if (!hasExplicitInterfaces && YldaResolutionUtilities.ExplicitInterfacePrefix(method.Name) is not null)
                hasExplicitInterfaces = true;

            if (!hasFlatBufferAssignOrRoot &&
                (method.Name == "__assign" || method.Name.StartsWith("GetRootAs", StringComparison.Ordinal)))
            {
                hasFlatBufferAssignOrRoot = true;
            }

            if (!hasByteBufferAccessor && method.Name == "get_ByteBuffer")
                hasByteBufferAccessor = true;

            if (!hasInitKeyMethod && method.Name == "InitKey")
                hasInitKeyMethod = true;

            if (!hasCollectionLikeMembers)
            {
                if ((method.Name.StartsWith("get_", StringComparison.Ordinal) || method.Name.StartsWith("set_", StringComparison.Ordinal)) &&
                    YldaResolutionUtilities.TrySingularizeCollectionName(method.Name[4..], out _))
                {
                    hasCollectionLikeMembers = true;
                }
                else if ((method.Name.StartsWith("Create", StringComparison.Ordinal) && method.Name.EndsWith("Vector", StringComparison.Ordinal)) ||
                         method.Name == "DataList" ||
                         method.Name == "CreateDataListVector")
                {
                    hasCollectionLikeMembers = true;
                }
            }
        }

        if (!hasCollectionLikeMembers)
        {
            foreach (var field in fields)
            {
                if ((YldaResolutionUtilities.BackingFieldPropertyName(field.Name) is { } backing &&
                     YldaResolutionUtilities.TrySingularizeCollectionName(backing, out _)) ||
                    YldaResolutionUtilities.TrySingularizeCollectionName(field.Name, out _))
                {
                    hasCollectionLikeMembers = true;
                    break;
                }
            }
        }

        if (!hasCollectionLikeMembers)
        {
            foreach (var property in properties)
            {
                if (YldaResolutionUtilities.TrySingularizeCollectionName(property.Name, out _))
                {
                    hasCollectionLikeMembers = true;
                    break;
                }
            }
        }

        var isTableLike = type.FullName.EndsWith("Table", StringComparison.Ordinal);
        var isKnownLocalInferenceType = YldaResolutionConstants.LocalInferenceTypeNames.Contains(type.FullName);
        var requiresLocalTypeInference =
            hasExplicitInterfaces ||
            hasFlatBufferAssignOrRoot ||
            hasByteBufferAccessor ||
            hasInitKeyMethod ||
            hasCollectionLikeMembers ||
            isTableLike ||
            isKnownLocalInferenceType;

        return new TypeDescriptorHints(
            requiresLocalTypeInference,
            hasExplicitInterfaces,
            hasFlatBufferAssignOrRoot,
            hasByteBufferAccessor,
            hasInitKeyMethod,
            hasCollectionLikeMembers,
            isTableLike,
            isKnownLocalInferenceType);
    }

    private Dictionary<string, uint> BuildPropertyTypeIndexMap(TypeDefinition type, IReadOnlyList<PropertyDefinition> properties)
    {
        var propertyTypeIndexByName = new Dictionary<string, uint>(StringComparer.OrdinalIgnoreCase);
        foreach (var property in properties)
        {
            if (TryGetPropertyTypeIndex(type, property, out var typeIndex))
                propertyTypeIndexByName[property.Name] = typeIndex;
        }

        return propertyTypeIndexByName;
    }

    private bool TryGetPropertyTypeIndex(TypeDefinition type, PropertyDefinition property, out uint typeIndex)
    {
        if (property.GetterDelta != uint.MaxValue)
        {
            typeIndex = _model.Methods[type.FirstMethodIndex + (int)property.GetterDelta].ReturnTypeIndex;
            return true;
        }

        if (property.SetterDelta != uint.MaxValue)
        {
            var setter = _model.Methods[type.FirstMethodIndex + (int)property.SetterDelta];
            if (setter.ParameterStart != uint.MaxValue && setter.ParameterCount > 0)
            {
                typeIndex = _model.Parameters[(int)setter.ParameterStart].TypeIndex;
                return true;
            }
        }

        typeIndex = uint.MaxValue;
        return false;
    }

    private static T[] Slice<T>(IReadOnlyList<T> source, int start, int count)
    {
        if (count <= 0 || start < 0)
            return [];

        var result = new T[count];
        for (var i = 0; i < count; i++)
            result[i] = source[start + i];
        return result;
    }
}
