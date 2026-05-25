using static CnMetadataExporter.TypeNameHelpers;

namespace CnMetadataExporter;

internal sealed class FutureLikeResolver
{
    private readonly string? _futureCallbackTypeName;
    private readonly string? _futureErrorCallbackTypeName;
    private readonly string? _futureInterfaceTypeName;
    private readonly string? _futureValueCallbackTypeName;
    private readonly string? _hubConnectionTypeName;

    public FutureLikeResolver(KnownTypeCatalog knownTypes)
    {
        _futureCallbackTypeName = knownTypes.FutureCallbackTypeName;
        _futureErrorCallbackTypeName = knownTypes.FutureErrorCallbackTypeName;
        _futureInterfaceTypeName = knownTypes.FutureInterfaceTypeName;
        _futureValueCallbackTypeName = knownTypes.FutureValueCallbackTypeName;
        _hubConnectionTypeName = knownTypes.HubConnectionTypeName;
    }

    public ResolvedMemberSet ApplyFutureLikeAdjustments(
        TypeDefinition type,
        IReadOnlyList<MethodDefinition> methodRows,
        IReadOnlyList<string> genericParameterNames,
        ResolvedMemberSet members)
    {
        var relationships = members.Relationships;
        var fields = members.Fields;
        var properties = members.Properties;
        var events = members.Events;
        var methods = members.Methods;
        if (!IsFutureLikeType(type, methodRows) || genericParameterNames.Count != 1)
            return members;

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

        return new ResolvedMemberSet(relationships, adjustedFields, adjustedProperties, events, adjustedMethods);
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
}
