using System.Buffers.Binary;
using System.Text;

namespace YldaDumpCsExporter;

internal static class YldaMetadataReader
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
        var stringSection = rawSections[YldaMetadataLayout.HeaderOffString];
        var methodSection = rawSections[YldaMetadataLayout.HeaderOffMethods];
        var typeSection = rawSections[YldaMetadataLayout.HeaderOffTypeDefs];
        var imageSection = rawSections[YldaMetadataLayout.HeaderOffImageRanges];
        var assemblySection = rawSections[YldaMetadataLayout.HeaderOffAssemblySummary];
        var parameterDefaultValueSection = rawSections[YldaMetadataLayout.HeaderOffParameterDefaultValues];
        var fieldDefaultValueSection = rawSections[YldaMetadataLayout.HeaderOffFieldDefaultValues];
        var fieldMarshaledSizeSection = rawSections[YldaMetadataLayout.HeaderOffFieldMarshaledSizes];
        var fieldSection = rawSections[YldaMetadataLayout.HeaderOffFields];
        var parameterSection = rawSections[YldaMetadataLayout.HeaderOffParameters];
        var propertySection = rawSections[YldaMetadataLayout.HeaderOffProperties];
        var eventSection = rawSections[YldaMetadataLayout.HeaderOffEvents];
        var genericParameterSection = rawSections[YldaMetadataLayout.HeaderOffGenericParameters];
        var genericParameterConstraintSection = rawSections[YldaMetadataLayout.HeaderOffGenericParameterConstraints];
        var genericContainerSection = rawSections[YldaMetadataLayout.HeaderOffGenericContainers];
        var nestedTypeSection = rawSections[YldaMetadataLayout.HeaderOffNestedTypes];
        var interfaceSection = rawSections[YldaMetadataLayout.HeaderOffInterfaces];
        var vtableMethodSection = rawSections[YldaMetadataLayout.HeaderOffVTableMethods];
        var interfaceOffsetSection = rawSections[YldaMetadataLayout.HeaderOffInterfaceOffsets];

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
        for (var headerOffset = YldaMetadataLayout.HeaderStart;
             headerOffset <= YldaMetadataLayout.HeaderEnd;
             headerOffset += YldaMetadataLayout.HeaderStride)
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
            var recordSize = YldaMetadataLayout.GetRecordSize(headerOffset);
            descriptors.Add(new MetadataSectionDescriptor(
                headerOffset,
                YldaMetadataLayout.GetSectionName(headerOffset),
                section,
                recordSize,
                YldaMetadataLayout.IsKnownTypedSection(headerOffset),
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
            ["types"] = typeSection.Size / YldaMetadataLayout.TypeDefSize,
            ["methods"] = methodSection.Size / YldaMetadataLayout.MethodDefSize,
            ["fields"] = fieldSection.Size / YldaMetadataLayout.FieldDefSize,
            ["parameters"] = parameterSection.Size / YldaMetadataLayout.ParamDefSize,
            ["properties"] = propertySection.Size / YldaMetadataLayout.PropertyDefSize,
            ["events"] = eventSection.Size / YldaMetadataLayout.EventDefSize,
            ["images"] = imageSection.Size / YldaMetadataLayout.ImageRangeSize,
            ["assemblies"] = assemblySection.Size / YldaMetadataLayout.AssemblySummarySize,
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
        var count = imageSection.Size / YldaMetadataLayout.ImageRangeSize;
        var rows = new List<ImageRange>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = imageSection.Offset + idx * YldaMetadataLayout.ImageRangeSize;
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
        var count = assemblySection.Size / YldaMetadataLayout.AssemblySummarySize;
        var rows = new List<AssemblySummary>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = assemblySection.Offset + idx * YldaMetadataLayout.AssemblySummarySize;
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
        var count = section.Size / YldaMetadataLayout.ParameterDefaultValueDefSize;
        var rows = new List<ParameterDefaultValueEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.ParameterDefaultValueDefSize;
            rows.Add(new ParameterDefaultValueEntry(idx, ReadUInt32(buffer, off), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }

        return rows;
    }

    private static List<FieldDefaultValueEntry> ParseFieldDefaultValues(byte[] buffer, Section section)
    {
        var count = section.Size / YldaMetadataLayout.FieldDefaultValueDefSize;
        var rows = new List<FieldDefaultValueEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.FieldDefaultValueDefSize;
            rows.Add(new FieldDefaultValueEntry(idx, ReadUInt32(buffer, off), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }

        return rows;
    }

    private static List<FieldMarshaledSizeEntry> ParseFieldMarshaledSizes(byte[] buffer, Section section)
    {
        var count = section.Size / YldaMetadataLayout.FieldMarshaledSizeDefSize;
        var rows = new List<FieldMarshaledSizeEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.FieldMarshaledSizeDefSize;
            rows.Add(new FieldMarshaledSizeEntry(idx, ReadUInt32(buffer, off), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }

        return rows;
    }

    private static List<TypeDefinition> ParseTypes(byte[] buffer, Section stringSection, Section typeSection)
    {
        var count = typeSection.Size / YldaMetadataLayout.TypeDefSize;
        var rows = new List<TypeDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = typeSection.Offset + idx * YldaMetadataLayout.TypeDefSize;
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
        var count = methodSection.Size / YldaMetadataLayout.MethodDefSize;
        var rows = new List<MethodDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = methodSection.Offset + idx * YldaMetadataLayout.MethodDefSize;
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
        var count = fieldSection.Size / YldaMetadataLayout.FieldDefSize;
        var rows = new List<FieldDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = fieldSection.Offset + idx * YldaMetadataLayout.FieldDefSize;
            rows.Add(new FieldDefinition(idx, ReadString(buffer, stringSection, ReadUInt32(buffer, off)), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }
        return rows;
    }

    private static List<ParameterDefinition> ParseParameters(byte[] buffer, Section stringSection, Section parameterSection)
    {
        var count = parameterSection.Size / YldaMetadataLayout.ParamDefSize;
        var rows = new List<ParameterDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = parameterSection.Offset + idx * YldaMetadataLayout.ParamDefSize;
            rows.Add(new ParameterDefinition(idx, ReadString(buffer, stringSection, ReadUInt32(buffer, off)), ReadUInt32(buffer, off + 4), ReadUInt32(buffer, off + 8)));
        }
        return rows;
    }

    private static List<PropertyDefinition> ParseProperties(byte[] buffer, Section stringSection, Section propertySection)
    {
        var count = propertySection.Size / YldaMetadataLayout.PropertyDefSize;
        var rows = new List<PropertyDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = propertySection.Offset + idx * YldaMetadataLayout.PropertyDefSize;
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
        var count = eventSection.Size / YldaMetadataLayout.EventDefSize;
        var rows = new List<EventDefinition>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = eventSection.Offset + idx * YldaMetadataLayout.EventDefSize;
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
        var count = section.Size / YldaMetadataLayout.GenericParameterDefSize;
        var rows = new List<GenericParameterEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.GenericParameterDefSize;
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
        var count = section.Size / YldaMetadataLayout.GenericParameterConstraintDefSize;
        var rows = new List<GenericParameterConstraintEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.GenericParameterConstraintDefSize;
            rows.Add(new GenericParameterConstraintEntry(idx, ReadUInt32(buffer, off)));
        }

        return rows;
    }

    private static List<GenericContainerEntry> ParseGenericContainers(byte[] buffer, Section section)
    {
        var count = section.Size / YldaMetadataLayout.GenericContainerDefSize;
        var rows = new List<GenericContainerEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.GenericContainerDefSize;
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
        var count = section.Size / YldaMetadataLayout.NestedTypeDefSize;
        var rows = new List<NestedTypeEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.NestedTypeDefSize;
            rows.Add(new NestedTypeEntry(idx, ReadUInt32(buffer, off)));
        }

        return rows;
    }

    private static List<InterfaceTypeEntry> ParseInterfaces(byte[] buffer, Section section)
    {
        var count = section.Size / YldaMetadataLayout.InterfaceDefSize;
        var rows = new List<InterfaceTypeEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.InterfaceDefSize;
            rows.Add(new InterfaceTypeEntry(idx, ReadUInt32(buffer, off)));
        }

        return rows;
    }

    private static List<VTableMethodEntry> ParseVTableMethods(byte[] buffer, Section section)
    {
        var count = section.Size / YldaMetadataLayout.VTableMethodDefSize;
        var rows = new List<VTableMethodEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.VTableMethodDefSize;
            rows.Add(new VTableMethodEntry(idx, ReadUInt32(buffer, off)));
        }

        return rows;
    }

    private static List<InterfaceOffsetEntry> ParseInterfaceOffsets(byte[] buffer, Section section)
    {
        var count = section.Size / YldaMetadataLayout.InterfaceOffsetDefSize;
        var rows = new List<InterfaceOffsetEntry>(count);
        for (var idx = 0; idx < count; idx++)
        {
            var off = section.Offset + idx * YldaMetadataLayout.InterfaceOffsetDefSize;
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
