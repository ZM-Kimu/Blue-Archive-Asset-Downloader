namespace CnMetadataExporter;

internal readonly record struct Section(int Offset, int Size)
{
    public int Count => Size;
}

internal readonly record struct MetadataSectionCandidate(
    string Name,
    int RecordSize,
    double ValidityScore,
    string Summary);

internal sealed record MetadataSectionDescriptor(
    int HeaderOffset,
    string Name,
    Section Section,
    int? RecordSize,
    bool IsKnown,
    IReadOnlyList<MetadataSectionCandidate> Candidates);

internal readonly record struct ImageRange(
    string DllName,
    int ImageIndex,
    int FirstTypeIndex,
    int TypeCount,
    int AuxStart,
    int AuxCount,
    int EntryPoint,
    uint Token,
    int ExtraA,
    int ExtraB)
{
    public int EndTypeIndexExclusive => FirstTypeIndex + TypeCount;
    public bool ContainsTypeIndex(int typeIndex) => typeIndex >= FirstTypeIndex && typeIndex < EndTypeIndexExclusive;
}

internal readonly record struct AssemblySummary(
    int ImageIndex,
    uint Token,
    int AuxStart,
    int AuxCount,
    string ShortName,
    int CultureIndex,
    string DllName,
    uint Flags,
    uint[] Extra);

internal readonly record struct ParameterDefaultValueEntry(int Index, uint ParameterIndex, uint TypeIndex, uint DataIndex);
internal readonly record struct FieldDefaultValueEntry(int Index, uint FieldIndex, uint TypeIndex, uint DataIndex);
internal readonly record struct FieldMarshaledSizeEntry(int Index, uint FieldIndex, uint TypeIndex, uint Size);
internal readonly record struct GenericParameterEntry(int Index, uint OwnerIndex, uint NameIndex, uint FlagsOrAttrs, uint Number, string Name);
internal readonly record struct GenericParameterConstraintEntry(int Index, uint TypeIndex);
internal readonly record struct GenericContainerEntry(int Index, uint OwnerIndex, uint TypeArgumentCount, uint IsMethod, uint GenericParameterStart);
internal readonly record struct NestedTypeEntry(int Index, uint TypeIndex);
internal readonly record struct InterfaceTypeEntry(int Index, uint TypeIndex);
internal readonly record struct VTableMethodEntry(int Index, uint MethodIndex);
internal readonly record struct InterfaceOffsetEntry(int Index, uint InterfaceTypeIndex, uint Offset);

internal readonly record struct TypeDefinition(
    int Index,
    string Name,
    string Namespace,
    uint Token,
    uint[] RawWords)
{
    public string FullName => string.IsNullOrEmpty(Namespace) ? Name : $"{Namespace}.{Name}";
    public uint NameIndex => RawWords[0];
    public uint NamespaceIndex => RawWords[1];
    public uint PrimaryTypeIndex => RawWords[2];
    public uint DeclaringTypeIndexHint => RawWords[3];
    public uint BaseTypeIndexHint => RawWords[4];
    public uint SecondaryTypeIndex => RawWords[5];
    public uint ElementTypeIndexHint => RawWords[6];
    public uint Flags => RawWords[7];
    public int FirstFieldIndex => unchecked((int)RawWords[8]);
    public int FirstMethodIndex => unchecked((int)RawWords[9]);
    public int FirstEventIndex => unchecked((int)RawWords[10]);
    public int FirstPropertyIndex => unchecked((int)RawWords[11]);
    public int NestedTypesStart => unchecked((int)RawWords[12]);
    public int InterfacesStart => unchecked((int)RawWords[13]);
    public int VTableStart => unchecked((int)RawWords[14]);
    public int InterfaceOffsetsStart => unchecked((int)RawWords[15]);
    public uint CountsWordA => RawWords[16];
    public uint CountsWordB => RawWords[17];
    public uint CountsWordC => RawWords[18];
    public uint CountsWordD => RawWords[19];
    public uint Bitfield => RawWords[20];
    public int MethodCount => (int)(CountsWordA & 0xFFFF);
    public int PropertyCount => (int)(CountsWordA >> 16);
    public int FieldCount => (int)(CountsWordB & 0xFFFF);
    public int EventCount => (int)(CountsWordB >> 16);
    public int NestedTypeCount => (int)(CountsWordC & 0xFFFF);
    public int VTableCount => (int)(CountsWordC >> 16);
    public int InterfaceCount => (int)(CountsWordD & 0xFFFF);
    public int InterfaceOffsetCount => (int)(CountsWordD >> 16);
}

internal readonly record struct MethodDefinition(
    int Index,
    string Name,
    uint Token,
    int DeclaringTypeIndex,
    uint ReturnTypeIndex,
    uint PackedA,
    uint ParameterStart,
    uint GenericContainerIndex,
    ushort Flags,
    ushort ImplFlags,
    ushort Slot,
    ushort ParameterCount)
{
    public bool HasParameters => ParameterStart != uint.MaxValue && ParameterCount > 0;
    public bool HasGenericContainer => GenericContainerIndex != uint.MaxValue;
}

internal readonly record struct FieldDefinition(int Index, string Name, uint TypeIndex, uint Token);
internal readonly record struct ParameterDefinition(int Index, string Name, uint Token, uint TypeIndex);
internal readonly record struct PropertyDefinition(int Index, string Name, uint GetterDelta, uint SetterDelta, uint Attributes, uint Token);
internal readonly record struct EventDefinition(int Index, string Name, uint TypeIndex, uint AddDelta, uint RemoveDelta, uint RaiseDelta, uint Token);

internal sealed record MetadataModel(
    byte[] Buffer,
    IReadOnlyList<MetadataSectionDescriptor> Sections,
    Section StringSection,
    Section MethodSection,
    Section TypeSection,
    Section ImageSection,
    Section AssemblySection,
    Section ParameterDefaultValueSection,
    Section FieldDefaultValueSection,
    Section FieldMarshaledSizeSection,
    Section FieldSection,
    Section ParameterSection,
    Section PropertySection,
    Section EventSection,
    Section GenericParameterSection,
    Section GenericParameterConstraintSection,
    Section GenericContainerSection,
    Section NestedTypeSection,
    Section InterfaceSection,
    Section VTableMethodSection,
    Section InterfaceOffsetSection,
    IReadOnlyList<ImageRange> Images,
    IReadOnlyList<AssemblySummary> Assemblies,
    IReadOnlyList<ParameterDefaultValueEntry> ParameterDefaultValues,
    IReadOnlyList<FieldDefaultValueEntry> FieldDefaultValues,
    IReadOnlyList<FieldMarshaledSizeEntry> FieldMarshaledSizes,
    IReadOnlyList<TypeDefinition> Types,
    IReadOnlyList<MethodDefinition> Methods,
    IReadOnlyList<FieldDefinition> Fields,
    IReadOnlyList<ParameterDefinition> Parameters,
    IReadOnlyList<PropertyDefinition> Properties,
    IReadOnlyList<EventDefinition> Events,
    IReadOnlyList<GenericParameterEntry> GenericParameters,
    IReadOnlyList<GenericParameterConstraintEntry> GenericParameterConstraints,
    IReadOnlyList<GenericContainerEntry> GenericContainers,
    IReadOnlyList<NestedTypeEntry> NestedTypes,
    IReadOnlyList<InterfaceTypeEntry> Interfaces,
    IReadOnlyList<VTableMethodEntry> VTableMethods,
    IReadOnlyList<InterfaceOffsetEntry> InterfaceOffsets);
