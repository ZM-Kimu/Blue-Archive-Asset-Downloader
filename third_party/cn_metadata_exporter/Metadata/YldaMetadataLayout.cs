namespace YldaDumpCsExporter;

internal static class YldaMetadataLayout
{
    public const int HeaderStart = 0x18;
    public const int HeaderEnd = 0xB8;
    public const int HeaderStride = 0x08;

    public const int HeaderOffString = 0x18;
    public const int HeaderOffEvents = 0x20;
    public const int HeaderOffProperties = 0x28;
    public const int HeaderOffMethods = 0x30;
    public const int HeaderOffParameterDefaultValues = 0x38;
    public const int HeaderOffFieldDefaultValues = 0x40;
    public const int HeaderOffFieldAndParameterDefaultValueData = 0x48;
    public const int HeaderOffFieldMarshaledSizes = 0x50;
    public const int HeaderOffParameters = 0x58;
    public const int HeaderOffFields = 0x60;
    public const int HeaderOffGenericParameters = 0x68;
    public const int HeaderOffGenericParameterConstraints = 0x70;
    public const int HeaderOffGenericContainers = 0x78;
    public const int HeaderOffNestedTypes = 0x80;
    public const int HeaderOffInterfaces = 0x88;
    public const int HeaderOffVTableMethods = 0x90;
    public const int HeaderOffInterfaceOffsets = 0x98;
    public const int HeaderOffTypeDefs = 0xA0;
    public const int HeaderOffImageRanges = 0xA8;
    public const int HeaderOffAssemblySummary = 0xB0;
    public const int HeaderOffTrailingTypeSystemData = 0xB8;

    public const int ParameterDefaultValueDefSize = 0x0C;
    public const int FieldDefaultValueDefSize = 0x0C;
    public const int FieldMarshaledSizeDefSize = 0x0C;
    public const int MethodDefSize = 0x24;
    public const int TypeDefSize = 0x58;
    public const int ImageRangeSize = 0x28;
    public const int AssemblySummarySize = 0x40;
    public const int FieldDefSize = 0x0C;
    public const int ParamDefSize = 0x0C;
    public const int PropertyDefSize = 0x14;
    public const int EventDefSize = 0x18;
    public const int GenericParameterDefSize = 0x10;
    public const int GenericParameterConstraintDefSize = 0x04;
    public const int GenericContainerDefSize = 0x10;
    public const int NestedTypeDefSize = 0x04;
    public const int InterfaceDefSize = 0x04;
    public const int VTableMethodDefSize = 0x04;
    public const int InterfaceOffsetDefSize = 0x08;

    public static string GetSectionName(int headerOffset) => headerOffset switch
    {
        HeaderOffString => "strings",
        HeaderOffEvents => "events",
        HeaderOffProperties => "properties",
        HeaderOffMethods => "methods",
        HeaderOffParameterDefaultValues => "parameterDefaultValues",
        HeaderOffFieldDefaultValues => "fieldDefaultValues",
        HeaderOffFieldAndParameterDefaultValueData => "fieldAndParameterDefaultValueData",
        HeaderOffFieldMarshaledSizes => "fieldMarshaledSizes",
        HeaderOffParameters => "parameters",
        HeaderOffFields => "fields",
        HeaderOffGenericParameters => "genericParameters",
        HeaderOffGenericParameterConstraints => "genericParameterConstraints",
        HeaderOffGenericContainers => "genericContainers",
        HeaderOffNestedTypes => "nestedTypes",
        HeaderOffInterfaces => "interfaces",
        HeaderOffVTableMethods => "vtableMethods",
        HeaderOffInterfaceOffsets => "interfaceOffsets",
        HeaderOffTypeDefs => "typeDefinitions",
        HeaderOffImageRanges => "imageRanges",
        HeaderOffAssemblySummary => "assemblySummary",
        HeaderOffTrailingTypeSystemData => "trailingTypeSystemData",
        _ => $"header_0x{headerOffset:X}",
    };

    public static int? GetRecordSize(int headerOffset) => headerOffset switch
    {
        HeaderOffEvents => EventDefSize,
        HeaderOffProperties => PropertyDefSize,
        HeaderOffMethods => MethodDefSize,
        HeaderOffParameterDefaultValues => ParameterDefaultValueDefSize,
        HeaderOffFieldDefaultValues => FieldDefaultValueDefSize,
        HeaderOffFieldMarshaledSizes => FieldMarshaledSizeDefSize,
        HeaderOffParameters => ParamDefSize,
        HeaderOffFields => FieldDefSize,
        HeaderOffGenericParameters => GenericParameterDefSize,
        HeaderOffGenericParameterConstraints => GenericParameterConstraintDefSize,
        HeaderOffGenericContainers => GenericContainerDefSize,
        HeaderOffNestedTypes => NestedTypeDefSize,
        HeaderOffInterfaces => InterfaceDefSize,
        HeaderOffVTableMethods => VTableMethodDefSize,
        HeaderOffInterfaceOffsets => InterfaceOffsetDefSize,
        HeaderOffTypeDefs => TypeDefSize,
        HeaderOffImageRanges => ImageRangeSize,
        HeaderOffAssemblySummary => AssemblySummarySize,
        _ => null,
    };

    public static bool IsKnownTypedSection(int headerOffset) => GetRecordSize(headerOffset) is not null;
}
