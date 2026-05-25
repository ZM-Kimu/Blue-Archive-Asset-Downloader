using System.Buffers.Binary;
using System.Text;

namespace CnMetadataExporter;

internal static class MetadataReader
{
    private static readonly (int RecordSize, string SemanticName)[] CandidateLayouts =
    [
        (0x04, "index-list"),
        (0x08, "pair-list"),
        (0x0C, "triple-list"),
        (0x10, "quad-list"),
        (0x14, "quint-list"),
        (0x18, "hexa-list"),
        (0x20, "octa-list"),
        (0x28, "deca-list"),
        (0x40, "summary-list"),
    ];

    public static MetadataModel Load(string metadataPath)
    {
        var buffer = File.ReadAllBytes(metadataPath);
        return Load(buffer);
    }

    public static MetadataModel Load(byte[] buffer)
    {
        var rawSections = ReadSectionInventory(buffer);
        var stringSection = rawSections[MetadataLayout.HeaderOffString];
        var methodSection = rawSections[MetadataLayout.HeaderOffMethods];
        var typeSection = rawSections[MetadataLayout.HeaderOffTypeDefs];
        var imageSection = rawSections[MetadataLayout.HeaderOffImageRanges];
        var assemblySection = rawSections[MetadataLayout.HeaderOffAssemblySummary];
        var parameterDefaultValueSection = rawSections[MetadataLayout.HeaderOffParameterDefaultValues];
        var fieldDefaultValueSection = rawSections[MetadataLayout.HeaderOffFieldDefaultValues];
        var fieldMarshaledSizeSection = rawSections[MetadataLayout.HeaderOffFieldMarshaledSizes];
        var fieldSection = rawSections[MetadataLayout.HeaderOffFields];
        var parameterSection = rawSections[MetadataLayout.HeaderOffParameters];
        var propertySection = rawSections[MetadataLayout.HeaderOffProperties];
        var eventSection = rawSections[MetadataLayout.HeaderOffEvents];
        var genericParameterSection = rawSections[MetadataLayout.HeaderOffGenericParameters];
        var genericParameterConstraintSection = rawSections[MetadataLayout.HeaderOffGenericParameterConstraints];
        var genericContainerSection = rawSections[MetadataLayout.HeaderOffGenericContainers];
        var nestedTypeSection = rawSections[MetadataLayout.HeaderOffNestedTypes];
        var interfaceSection = rawSections[MetadataLayout.HeaderOffInterfaces];
        var vtableMethodSection = rawSections[MetadataLayout.HeaderOffVTableMethods];
        var interfaceOffsetSection = rawSections[MetadataLayout.HeaderOffInterfaceOffsets];

        var parameterDefaults = ParseParameterDefaultValues(buffer, parameterDefaultValueSection);
        var fieldDefaults = ParseFieldDefaultValues(buffer, fieldDefaultValueSection);
        var fieldMarshaledSizes = ParseFieldMarshaledSizes(buffer, fieldMarshaledSizeSection);
        var nestedTypes = ParseNestedTypes(buffer, nestedTypeSection);
        var interfaces = ParseInterfaces(buffer, interfaceSection);
        var vtableMethods = ParseVTableMethods(buffer, vtableMethodSection);
        var interfaceOffsets = ParseInterfaceOffsets(buffer, interfaceOffsetSection);
        var genericParameterConstraints = ParseGenericParameterConstraints(buffer, genericParameterConstraintSection);
        var genericParameters = ParseGenericParameters(buffer, stringSection, genericParameterSection);
        var genericContainers = ParseGenericContainers(buffer, genericContainerSection);

        var typedCounts = BuildTypedCounts(
            typeSection,
            methodSection,
            fieldSection,
            parameterSection,
            propertySection,
            eventSection,
            imageSection,
            assemblySection);
        var sections = BuildSectionDescriptors(buffer, rawSections, typedCounts);

        return new MetadataModel(
            buffer,
            sections,
            stringSection,
            methodSection,
            typeSection,
            imageSection,
            assemblySection,
            parameterDefaultValueSection,
            fieldDefaultValueSection,
            fieldMarshaledSizeSection,
            fieldSection,
            parameterSection,
            propertySection,
            eventSection,
            genericParameterSection,
            genericParameterConstraintSection,
            genericContainerSection,
            nestedTypeSection,
            interfaceSection,
            vtableMethodSection,
            interfaceOffsetSection,
            ParseImages(buffer, stringSection, imageSection),
            ParseAssemblies(buffer, stringSection, assemblySection),
            parameterDefaults,
            fieldDefaults,
            fieldMarshaledSizes,
            ParseTypes(buffer, stringSection, typeSection),
            ParseMethods(buffer, stringSection, methodSection),
            ParseFields(buffer, stringSection, fieldSection),
            ParseParameters(buffer, stringSection, parameterSection),
            ParseProperties(buffer, stringSection, propertySection),
            ParseEvents(buffer, stringSection, eventSection),
            genericParameters,
            genericParameterConstraints,
            genericContainers,
            nestedTypes,
            interfaces,
            vtableMethods,
            interfaceOffsets);
    }

    public static Section ReadSection(byte[] buffer, int headerOffset)
        => new(ReadInt32(buffer, headerOffset), ReadInt32(buffer, headerOffset + 4));

    private static Dictionary<int, Section> ReadSectionInventory(byte[] buffer)
    {
        var sections = new Dictionary<int, Section>();
        for (var headerOffset = MetadataLayout.HeaderStart;
             headerOffset <= MetadataLayout.HeaderEnd;
             headerOffset += MetadataLayout.HeaderStride)
        {
            sections[headerOffset] = ReadSection(buffer, headerOffset);
        }

        return sections;
    }

    private static IReadOnlyList<MetadataSectionDescriptor> BuildSectionDescriptors(
        byte[] buffer,
        IReadOnlyDictionary<int, Section> rawSections,
        IReadOnlyDictionary<string, int> typedCounts)
    {
        var descriptors = new List<MetadataSectionDescriptor>(rawSections.Count);
        foreach (var pair in rawSections.OrderBy(item => item.Key))
        {
            var headerOffset = pair.Key;
            var section = pair.Value;
            var recordSize = MetadataLayout.GetRecordSize(headerOffset);
            descriptors.Add(new MetadataSectionDescriptor(
                headerOffset,
                MetadataLayout.GetSectionName(headerOffset),
                section,
                recordSize,
                MetadataLayout.IsKnownTypedSection(headerOffset),
                BuildSectionCandidates(buffer, section, recordSize, typedCounts)));
        }

        return descriptors;
    }

    private static IReadOnlyDictionary<string, int> BuildTypedCounts(
        Section typeSection,
        Section methodSection,
        Section fieldSection,
        Section parameterSection,
        Section propertySection,
        Section eventSection,
        Section imageSection,
        Section assemblySection)
    {
        return new Dictionary<string, int>(StringComparer.Ordinal)
        {
            ["types"] = typeSection.Size / MetadataLayout.TypeDefSize,
            ["methods"] = methodSection.Size / MetadataLayout.MethodDefSize,
            ["fields"] = fieldSection.Size / MetadataLayout.FieldDefSize,
            ["parameters"] = parameterSection.Size / MetadataLayout.ParamDefSize,
            ["properties"] = propertySection.Size / MetadataLayout.PropertyDefSize,
            ["events"] = eventSection.Size / MetadataLayout.EventDefSize,
            ["images"] = imageSection.Size / MetadataLayout.ImageRangeSize,
            ["assemblies"] = assemblySection.Size / MetadataLayout.AssemblySummarySize,
        };
    }

    private static IReadOnlyList<MetadataSectionCandidate> BuildSectionCandidates(
        byte[] buffer,
        Section section,
        int? knownRecordSize,
        IReadOnlyDictionary<string, int> typedCounts)
    {
        var candidates = new List<MetadataSectionCandidate>();
        if (section.Offset <= 0 || section.Size <= 0 || section.Offset + section.Size > buffer.Length)
            return candidates;

        if (knownRecordSize is { } exactSize && exactSize > 0 && section.Size % exactSize == 0)
        {
            candidates.Add(new MetadataSectionCandidate(
                "known-layout",
                exactSize,
                1.0,
                $"count={section.Size / exactSize}"));
        }

        foreach (var (recordSize, semanticName) in CandidateLayouts)
        {
            if (recordSize <= 0 || section.Size % recordSize != 0)
                continue;

            var recordCount = section.Size / recordSize;
            var wordsPerRecord = recordSize / sizeof(uint);
            var sampleCount = Math.Min(recordCount, 256);
            var notes = new List<string>();
            double bestScore = 0;

            for (var wordIndex = 0; wordIndex < wordsPerRecord; wordIndex++)
            {
                var values = new uint[sampleCount];
                for (var i = 0; i < sampleCount; i++)
                {
                    var offset = section.Offset + i * recordSize + wordIndex * sizeof(uint);
                    values[i] = ReadUInt32(buffer, offset);
                }

                foreach (var typedCount in typedCounts)
                {
                    var valid = values.Count(value => value == uint.MaxValue || value < typedCount.Value);
                    var score = sampleCount == 0 ? 0 : valid / (double)sampleCount;
                    if (score < 0.70)
                        continue;

                    bestScore = Math.Max(bestScore, score);
                    notes.Add($"w{wordIndex}->{typedCount.Key}:{score:F2}");
                }
            }

            if (bestScore >= 0.70)
            {
                candidates.Add(new MetadataSectionCandidate(
                    semanticName,
                    recordSize,
                    bestScore,
                    string.Join(", ", notes.Distinct(StringComparer.Ordinal))));
            }
        }

        return candidates
            .OrderByDescending(candidate => candidate.ValidityScore)
            .ThenBy(candidate => candidate.RecordSize)
            .Take(6)
            .ToArray();
    }

    private static List<ImageRange> ParseImages(byte[] buffer, Section stringSection, Section imageSection)
    {
        var count = imageSection.Size / MetadataLayout.ImageRangeSize;
        var rows = new List<ImageRange>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = imageSection.Offset + idx * MetadataLayout.ImageRangeSize;
            rows.Add(new ImageRange(
                ReadString(buffer, stringSection, ReadUInt32(buffer, off), skipLeadingNuls: true),
                ReadInt32(buffer, off + 4),
                ReadInt32(buffer, off + 8),
                ReadInt32(buffer, off + 12),
                ReadInt32(buffer, off + 16),
                ReadInt32(buffer, off + 20),
                ReadInt32(buffer, off + 24),
                ReadUInt32(buffer, off + 28),
                ReadInt32(buffer, off + 32),
                ReadInt32(buffer, off + 36)));
        }
        return rows;
    }

    private static List<AssemblySummary> ParseAssemblies(byte[] buffer, Section stringSection, Section assemblySection)
    {
        var count = assemblySection.Size / MetadataLayout.AssemblySummarySize;
        var rows = new List<AssemblySummary>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = assemblySection.Offset + idx * MetadataLayout.AssemblySummarySize;
            var extra = new uint[8];
            for (var i = 0; i < extra.Length; i++)
                extra[i] = ReadUInt32(buffer, off + 32 + i * 4);

            rows.Add(new AssemblySummary(
                ReadInt32(buffer, off),
                ReadUInt32(buffer, off + 4),
                ReadInt32(buffer, off + 8),
                ReadInt32(buffer, off + 12),
                ReadString(buffer, stringSection, ReadUInt32(buffer, off + 16)),
                ReadInt32(buffer, off + 20),
                ReadString(buffer, stringSection, ReadUInt32(buffer, off + 24), skipLeadingNuls: true),
                ReadUInt32(buffer, off + 28),
                extra));
        }
        return rows;
    }

    private static List<ParameterDefaultValueEntry> ParseParameterDefaultValues(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.ParameterDefaultValueDefSize;
        var rows = new List<ParameterDefaultValueEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.ParameterDefaultValueDefSize;
            rows.Add(new ParameterDefaultValueEntry(idx, ReadUInt32(buffer, off), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }

        return rows;
    }

    private static List<FieldDefaultValueEntry> ParseFieldDefaultValues(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.FieldDefaultValueDefSize;
        var rows = new List<FieldDefaultValueEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.FieldDefaultValueDefSize;
            rows.Add(new FieldDefaultValueEntry(idx, ReadUInt32(buffer, off), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }

        return rows;
    }

    private static List<FieldMarshaledSizeEntry> ParseFieldMarshaledSizes(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.FieldMarshaledSizeDefSize;
        var rows = new List<FieldMarshaledSizeEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.FieldMarshaledSizeDefSize;
            rows.Add(new FieldMarshaledSizeEntry(idx, ReadUInt32(buffer, off), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }

        return rows;
    }

    private static List<TypeDefinition> ParseTypes(byte[] buffer, Section stringSection, Section typeSection)
    {
        var count = typeSection.Size / MetadataLayout.TypeDefSize;
        var rows = new List<TypeDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = typeSection.Offset + idx * MetadataLayout.TypeDefSize;
            var rawWords = new uint[22];
            for (var i = 0; i < rawWords.Length; i++)
                rawWords[i] = ReadUInt32(buffer, off + i * 4);

            rows.Add(new TypeDefinition(
                idx,
                ReadString(buffer, stringSection, rawWords[0]),
                ReadString(buffer, stringSection, rawWords[1]),
                rawWords[21],
                rawWords));
        }

        return rows;
    }

    private static List<MethodDefinition> ParseMethods(byte[] buffer, Section stringSection, Section methodSection)
    {
        var count = methodSection.Size / MetadataLayout.MethodDefSize;
        var rows = new List<MethodDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = methodSection.Offset + idx * MetadataLayout.MethodDefSize;
            rows.Add(new MethodDefinition(
                idx,
                ReadString(buffer, stringSection, ReadUInt32(buffer, off)),
                ReadUInt32(buffer, off + 24),
                ReadInt32(buffer, off + 4),
                ReadUInt32(buffer, off + 8),
                ReadUInt32(buffer, off + 12),
                ReadUInt32(buffer, off + 16),
                ReadUInt32(buffer, off + 20),
                ReadUInt16(buffer, off + 28),
                ReadUInt16(buffer, off + 30),
                ReadUInt16(buffer, off + 32),
                ReadUInt16(buffer, off + 34)));
        }
        return rows;
    }

    private static List<FieldDefinition> ParseFields(byte[] buffer, Section stringSection, Section fieldSection)
    {
        var count = fieldSection.Size / MetadataLayout.FieldDefSize;
        var rows = new List<FieldDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = fieldSection.Offset + idx * MetadataLayout.FieldDefSize;
            rows.Add(new FieldDefinition(idx, ReadString(buffer, stringSection, ReadUInt32(buffer, off)), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }
        return rows;
    }

    private static List<ParameterDefinition> ParseParameters(byte[] buffer, Section stringSection, Section parameterSection)
    {
        var count = parameterSection.Size / MetadataLayout.ParamDefSize;
        var rows = new List<ParameterDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = parameterSection.Offset + idx * MetadataLayout.ParamDefSize;
            rows.Add(new ParameterDefinition(idx, ReadString(buffer, stringSection, ReadUInt32(buffer, off)), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }
        return rows;
    }

    private static List<PropertyDefinition> ParseProperties(byte[] buffer, Section stringSection, Section propertySection)
    {
        var count = propertySection.Size / MetadataLayout.PropertyDefSize;
        var rows = new List<PropertyDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = propertySection.Offset + idx * MetadataLayout.PropertyDefSize;
            rows.Add(new PropertyDefinition(
                idx,
                ReadString(buffer, stringSection, ReadUInt32(buffer, off)),
                ReadUInt32(buffer, off + 4),
                ReadUInt32(buffer, off + 8),
                ReadUInt32(buffer, off + 12),
                ReadUInt32(buffer, off + 16)));
        }
        return rows;
    }

    private static List<EventDefinition> ParseEvents(byte[] buffer, Section stringSection, Section eventSection)
    {
        var count = eventSection.Size / MetadataLayout.EventDefSize;
        var rows = new List<EventDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = eventSection.Offset + idx * MetadataLayout.EventDefSize;
            rows.Add(new EventDefinition(
                idx,
                ReadString(buffer, stringSection, ReadUInt32(buffer, off)),
                ReadUInt32(buffer, off + 4),
                ReadUInt32(buffer, off + 8),
                ReadUInt32(buffer, off + 12),
                ReadUInt32(buffer, off + 16),
                ReadUInt32(buffer, off + 20)));
        }
        return rows;
    }

    private static List<GenericParameterEntry> ParseGenericParameters(byte[] buffer, Section stringSection, Section section)
    {
        var count = section.Size / MetadataLayout.GenericParameterDefSize;
        var rows = new List<GenericParameterEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.GenericParameterDefSize;
            var nameIndex = ReadUInt32(buffer, off + 4);
            rows.Add(new GenericParameterEntry(
                idx,
                ReadUInt32(buffer, off),
                nameIndex,
                ReadUInt32(buffer, off + 8),
                ReadUInt32(buffer, off + 12),
                ReadString(buffer, stringSection, nameIndex)));
        }

        return rows;
    }

    private static List<GenericParameterConstraintEntry> ParseGenericParameterConstraints(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.GenericParameterConstraintDefSize;
        var rows = new List<GenericParameterConstraintEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.GenericParameterConstraintDefSize;
            rows.Add(new GenericParameterConstraintEntry(idx, ReadUInt32(buffer, off)));
        }

        return rows;
    }

    private static List<GenericContainerEntry> ParseGenericContainers(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.GenericContainerDefSize;
        var rows = new List<GenericContainerEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.GenericContainerDefSize;
            rows.Add(new GenericContainerEntry(
                idx,
                ReadUInt32(buffer, off),
                ReadUInt32(buffer, off + 4),
                ReadUInt32(buffer, off + 8),
                ReadUInt32(buffer, off + 12)));
        }

        return rows;
    }

    private static List<NestedTypeEntry> ParseNestedTypes(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.NestedTypeDefSize;
        var rows = new List<NestedTypeEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.NestedTypeDefSize;
            rows.Add(new NestedTypeEntry(idx, ReadUInt32(buffer, off)));
        }

        return rows;
    }

    private static List<InterfaceTypeEntry> ParseInterfaces(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.InterfaceDefSize;
        var rows = new List<InterfaceTypeEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.InterfaceDefSize;
            rows.Add(new InterfaceTypeEntry(idx, ReadUInt32(buffer, off)));
        }

        return rows;
    }

    private static List<VTableMethodEntry> ParseVTableMethods(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.VTableMethodDefSize;
        var rows = new List<VTableMethodEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.VTableMethodDefSize;
            rows.Add(new VTableMethodEntry(idx, ReadUInt32(buffer, off)));
        }

        return rows;
    }

    private static List<InterfaceOffsetEntry> ParseInterfaceOffsets(byte[] buffer, Section section)
    {
        var count = section.Size / MetadataLayout.InterfaceOffsetDefSize;
        var rows = new List<InterfaceOffsetEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * MetadataLayout.InterfaceOffsetDefSize;
            rows.Add(new InterfaceOffsetEntry(idx, ReadUInt32(buffer, off), ReadUInt32(buffer, off + 4)));
        }

        return rows;
    }

    private static string ReadString(byte[] buffer, Section stringSection, uint index, bool skipLeadingNuls = false)
    {
        var pos = checked(stringSection.Offset + (int)index);
        if (pos < 0 || pos >= buffer.Length)
            return string.Empty;

        if (skipLeadingNuls)
        {
            while (pos < buffer.Length && buffer[pos] == 0)
                pos++;
        }

        var end = pos;
        var max = Math.Min(buffer.Length, pos + 256);
        while (end < max && buffer[end] != 0)
            end++;

        return Encoding.UTF8.GetString(buffer, pos, end - pos);
    }

    private static int ReadInt32(byte[] buffer, int offset) => unchecked((int)BinaryPrimitives.ReadUInt32LittleEndian(buffer.AsSpan(offset, 4)));
    private static ushort ReadUInt16(byte[] buffer, int offset) => BinaryPrimitives.ReadUInt16LittleEndian(buffer.AsSpan(offset, 2));
    private static uint ReadUInt32(byte[] buffer, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(buffer.AsSpan(offset, 4));
}
