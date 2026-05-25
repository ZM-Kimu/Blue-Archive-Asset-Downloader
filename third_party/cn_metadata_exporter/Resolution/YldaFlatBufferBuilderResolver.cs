namespace YldaDumpCsExporter;

internal sealed class YldaFlatBufferBuilderResolver
{
    private readonly IReadOnlySet<string> _typeFullNames;

    public YldaFlatBufferBuilderResolver(YldaKnownTypeCatalog knownTypes)
    {
        _typeFullNames = knownTypes.TypeFullNames;
    }

    public YldaResolvedMemberSet ApplyFlatBufferTableAdjustments(
        TypeDefinition type,
        YldaResolvedMemberSet members)
    {
        var relationships = members.Relationships;
        var fields = members.Fields;
        var properties = members.Properties;
        var events = members.Events;
        var methods = members.Methods;
        var methodNames = methods.Select(method => method.DisplayName).ToHashSet(StringComparer.Ordinal);
        if (!methodNames.Contains("__assign") &&
            !methodNames.Any(name => name.StartsWith("GetRootAs", StringComparison.Ordinal)))
        {
            return members;
        }

        var offsetType = $"FlatBuffers.Offset<{type.FullName}>";
        var nullableByteSegmentType = "System.Nullable<System.ArraySegment<System.Byte>>";
        var byteArrayType = "System.Byte[]";
        var vectorMemberNames = properties
            .Select(property => property.DisplayName)
            .Where(name => name.EndsWith("Length", StringComparison.Ordinal))
            .Select(name => name[..^"Length".Length])
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        string? MemberElementType(string memberName)
            => FlatBufferTypeRecovery.ResolveMemberElementType(type.FullName, memberName, _typeFullNames);

        string PreferFlatBufferType(string currentType, string desiredType)
            => FlatBufferTypeRecovery.PreferFlatBufferType(currentType, desiredType, _typeFullNames);

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

            if (MemberElementType("DataList") is { } dataListElementType &&
                string.Equals(methodName, "CreateDataListVector", StringComparison.Ordinal) &&
                string.Equals(parameterName, "data", StringComparison.Ordinal))
            {
                return $"FlatBuffers.Offset<{dataListElementType}>[]";
            }

            if (methodName.StartsWith("Create", StringComparison.Ordinal) &&
                methodName.EndsWith("Vector", StringComparison.Ordinal) &&
                string.Equals(parameterName, "data", StringComparison.Ordinal))
            {
                var memberStem = methodName["Create".Length..^"Vector".Length];
                if (MemberElementType(memberStem) is { } vectorElementType)
                    return $"FlatBuffers.Offset<{vectorElementType}>[]";

                if (vectorLongMembers.Contains(memberStem))
                    return "System.Int64[]";
            }

            if (methodName.StartsWith("Add", StringComparison.Ordinal) && parameterName.Length > 0)
            {
                var memberStem = methodName["Add".Length..];
                if (scalarLongMembers.Contains(memberStem))
                    return "System.Int64";

                if (!vectorMemberNames.Contains(memberStem) &&
                    MemberElementType(memberStem) is { } memberElementType)
                {
                    return $"FlatBuffers.Offset<{memberElementType}>";
                }
            }

            if (string.Equals(methodName, $"Create{type.Name}", StringComparison.Ordinal) &&
                parameterName.EndsWith("Offset", StringComparison.Ordinal))
            {
                var memberStem = parameterName[..^"Offset".Length];
                if (!vectorMemberNames.Contains(memberStem) &&
                    MemberElementType(memberStem) is { } memberElementType)
                {
                    return $"FlatBuffers.Offset<{memberElementType}>";
                }
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
            if (!property.DisplayName.EndsWith("Length", StringComparison.Ordinal) &&
                MemberElementType(property.DisplayName) is { } memberElementType)
            {
                return property with { TypeName = PreferFlatBufferType(property.TypeName, $"System.Nullable<{memberElementType}>") };
            }

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
            else if (MemberElementType("DataList") is { } dataListElementType &&
                     string.Equals(method.DisplayName, "DataList", StringComparison.Ordinal))
            {
                desiredReturnType = $"System.Nullable<{dataListElementType}>";
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
            else
            {
                var memberName = StripGetPrefix(method.DisplayName) ?? method.DisplayName;
                if (!memberName.EndsWith("Length", StringComparison.Ordinal) &&
                    MemberElementType(memberName) is { } memberElementType)
                {
                    desiredReturnType = $"System.Nullable<{memberElementType}>";
                }
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

        return new YldaResolvedMemberSet(relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
    }

}

