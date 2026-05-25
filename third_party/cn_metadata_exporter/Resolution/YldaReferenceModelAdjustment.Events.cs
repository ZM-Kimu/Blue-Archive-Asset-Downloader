namespace YldaDumpCsExporter;

internal sealed partial class YldaReferenceModelAdjustment
{
    private IReadOnlyList<ResolvedEventModel> AdjustEvents()
    {
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

        return adjustedEvents;
    }
}
