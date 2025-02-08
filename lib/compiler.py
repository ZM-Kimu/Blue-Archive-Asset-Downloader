"""Compiler will parse CSharp dump file to convert to python callable code."""

import os
import re
from enum import Enum

from lib.console import notice
from lib.structure import EnumMember, EnumType, Property, StructTable
from utils.util import TemplateString, Utils


class DataSize(Enum):
    bool = 1
    byte = 1
    ubyte = 1
    short = 2
    ushort = 2
    int = 4
    uint = 4
    long = 8
    ulong = 8
    float = 4
    double = 8
    string = 4  # ptr
    struct = 4  # ptr


class DataFlag(Enum):
    bool = "Bool"
    byte = "Int8"
    ubyte = "Uint8"
    short = "Int16"
    ushort = "Uint16"
    int = "Int32"
    uint = "Uint32"
    long = "Int64"
    ulong = "Uint64"
    float = "Float32"
    double = "Float64"


class ConvertFlag(Enum):
    short = "convert_short"
    ushort = "convert_ushort"
    int = "convert_int"
    uint = "convert_uint"
    long = "convert_long"
    ulong = "convert_ulong"
    float = "convert_float"
    double = "convert_double"
    string = "convert_string"


class String:
    INDENT = "    "
    NEWLINE = "\n"

    ENUM_CLASS = TemplateString("class %s:")
    """Create basic class identifier.\n\nArgs: class_name"""

    VARIABLE_ASSIGNMENT = TemplateString("%s = %s")
    """Basic assignment for 'a = b'.\n\nArgs: key, value"""

    FUNCTION_DEFINE = TemplateString("def %s(%s)%s:")
    """Basic function structure.\n\nArgs: func_name, args, annotaion"""

    WRAPPER_BASE = """
from enum import IntEnum
from lib.encryption import convert_short, convert_ushort, convert_int, convert_long, convert_float, convert_double, convert_string, convert_uint, convert_ulong, create_key
import inspect\n
def dump_table(table_instance) -> list:
    excel_name = table_instance.__class__.__name__.removesuffix("Table")
    current_module = inspect.getmodule(inspect.currentframe())
    dump_func = next(
        f
        for n, f in inspect.getmembers(current_module, inspect.isfunction)
        if n.removeprefix("dump_") == excel_name
    )
    password = create_key(excel_name.removesuffix("Excel"))
    return [dump_func(table_instance.DataList(j), password) for j in range(table_instance.DataListLength())]\n
"""
    """Wrapper basic structure."""

    WRAPPER_GETTER = TemplateString("excel_instance.%s()")
    """Wrap call FlatData method.\n\nArgs: prop_name"""

    WRAPPER_LIST_GETTER = TemplateString("excel_instance.%s(j)")
    """Wrap call FlatData list method.\n\nArgs: prop_name"""

    WRAPPER_LIST_CONVERTION = TemplateString(
        "%s for j in range(excel_instance.%sLength())"
    )
    """Wrap list prop.\n\nArgs: convertion|getter, prop_name"""

    WRAPPER_PASSWD_CONVERTION = TemplateString("%s(%s, password)")
    """Wrap the data has password.\n\nArgs: type_convert_method, getter"""

    WRAPPER_ENUM_CONVERTION = TemplateString("%s(%s).name")
    """Wrap prop of enum type.\n\nArgs: enum_name, convertion"""

    WRAPPER_PROP_KV = TemplateString('"%s": %s,\n')
    """Wrap non-list prop.\n\nArgs: prop_name, convertion|getter"""

    WRAPPER_LIST_KV = TemplateString('"%s": [%s],\n')
    """Wrap list prop.\n\nArgs: prop_name, convertion|getter"""

    WRAPPER_FUNC = TemplateString(
        """
def dump_%s(excel_instance, password: bytes = b"") -> dict:
    return {\n%s    }
"""
    )
    """Wrapper func.\n\nArgs: struct_name, dict_items"""

    WRAPPER_INT_ENUM = TemplateString("class %s(IntEnum):")
    """Wrapper enum class.\n\nArgs: enum_name"""

    # MODULE_IMPORT = TemplateString("from %s import %s")
    # """From module import name.\n\nArgs: module_name, component_name"""

    LOCAL_IMPORT = TemplateString("from .%s import %s")
    """From .module import name.\n\nArgs: local_module_name, component_name"""

    FB_BASIC_CLASS = TemplateString(
        """
import flatbuffers
from flatbuffers.compat import import_numpy
np = import_numpy()\n
class %s:
    __slots__ = ['_tab']\n
    @classmethod
    def GetRootAs(cls, buf, offset=0):
        n = flatbuffers.encode.Get(flatbuffers.packer.uoffset, buf, offset)
        x = %s()
        x.Init(buf, n + offset)
        return x\n
    def Init(self, buf, pos):
        self._tab = flatbuffers.table.Table(buf, pos)\n
"""
    )
    """FlatBuffer basic class.\n\nArgs: struct_name, struct_name"""

    FB_NON_SCALAR_LIST_CLASS_METHODS = TemplateString(
        """
    def %s(self, j):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            x = self._tab.Vector(o)
            x += flatbuffers.number_types.UOffsetTFlags.py_type(j) * %d
            x = self._tab.Indirect(x)
            from .%s import %s
            obj = %s()
            obj.Init(self._tab.Bytes, x)
            return obj
        return None\n
    def %sLength(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            return self._tab.VectorLen(o)
        return 0\n
    def %sIsNone(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        return o == 0\n
"""
    )
    """FlatBuffer method for list is a non-scalar type(ptr).\n\nArgs: prop_name, field_index_offset, type_alignment_size, prop_type, prop_type, prop_type, prop_name, field_index_offset, prop_name, field_index_offset"""

    FB_SCALAR_LIST_CLASS_METHODS = TemplateString(
        """
    def %s(self, j):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            a = self._tab.Vector(o)
            return self._tab.Get(flatbuffers.number_types.%sFlags, a + flatbuffers.number_types.UOffsetTFlags.py_type(j * %d))
        return 0\n
    def %sAsNumpy(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            return self._tab.GetVectorAsNumpy(flatbuffers.number_types.%sFlags, o)
        return 0\n
    def %sLength(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            return self._tab.VectorLen(o)
        return 0\n
    def %sIsNone(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        return o == 0\n
"""
    )
    """FlatBuffer method for list is a scalar type.\n\nArgs: prop_name, field_index_offset, data_type_flag, type_alignment_size, prop_name, field_index_offset, data_type_flag, prop_name, field_index_offset, prop_name, field_index_offset"""

    FB_SCALAR_PROPERTY_CLASS_METHODS = TemplateString(
        """
    def %s(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.%sFlags, o + self._tab.Pos)
        return 0\n
"""
    )
    """FlatBuffer method for scalar type property.\n\nArgs: prop_name, field_index_offset, data_type_flag"""

    FB_STRING_LIST_CLASS_METHODS = TemplateString(
        """
    def %s(self, j):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            a = self._tab.Vector(o)
            return self._tab.String(a + flatbuffers.number_types.UOffsetTFlags.py_type(j * 4))
        return ""\n
    def %sLength(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            return self._tab.VectorLen(o)
        return 0\n
    def %sIsNone(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        return o == 0\n
"""
    )
    """FlatBuffer method for list type is string.\n\nArgs: prop_name, field_index_offset, prop_name, field_index_offset, prop_name, field_index_offset"""

    FB_STRING_PROPERTY_CLASS_METHODS = TemplateString(
        """
    def %s(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None\n
"""
    )
    """FlatBuffer method for string type property.\n\nArgs: prop_name, field_index_offset"""

    FB_STRUCT_PROPERTY_CLASS_METHODS = TemplateString(
        """
    def %s(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            x = self._tab.Indirect(o + self._tab.Pos)
            from .%s import %s
            obj = %s()
            obj.Init(self._tab.Bytes, x)
            return obj
        return None\n
"""
    )
    """FlatBuffer method for struct type property.\n\nArgs: prop_name, field_index_offset, prop_type, prop_type, prop_type"""

    FB_ISOLATED_PROPERTY_CLASS_METHODS = TemplateString(
        """
    def %s(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(%d))
        if o != 0:
            from .%s import %s
            obj = %s()
            obj.Init(self._tab.Bytes, o + self._tab.Pos)
            return obj
        return None\n
"""
    )
    """FlatBuffer method for non-scalar type property(ptr).\n\nArgs: prop_name, field_index_offset, prop_type, prop_type, prop_type"""

    FB_LIST_AND_NON_SCALAR_PROPERTY_FUNCTION = TemplateString(
        """
def Add%s(builder, %s): builder.PrependUOffsetTRelativeSlot(%d, flatbuffers.number_types.UOffsetTFlags.py_type(%s), 0)
def Start%sVector(builder, numElems): return builder.StartVector(%d, numElems, %d)\n
"""
    )
    """FlatBuffer function for list and non-scalar property.\n\nArgs: prop_name, prop_name, field_index_in_struct, prop_name, prop_name, element_size, size_alignment"""

    FB_STRING_AND_STRUCT_PROPERTY_FUNCTION = TemplateString(
        """
def Add%s(builder, %s): builder.PrependUOffsetTRelativeSlot(%d, flatbuffers.number_types.UOffsetTFlags.py_type(%s), 0)
"""
    )
    """FlatBuffer function for string property.\n\nArgs: prop_name, prop_name, field_index_in_struct, prop_name"""

    FB_SCALAR_PROPERTY_FUNCTION = TemplateString(
        """
def Add%s(builder, %s): builder.Prepend%sSlot(%d, %s, 0)\n
"""
    )
    """FlatBuffer function for scalar property.\n\nArgs: prop_name, prop_name, data_type_flag, field_index_in_struct, prop_name"""

    FB_START_AND_END_FUNCTION = TemplateString(
        """
def Start(builder): builder.StartObject(%d)
def End(builder): return builder.EndObject()\n
"""
    )
    """FlatBuffer basic call function to start and end.\n\nArgs: prop_count"""


class Re:
    struct = re.compile(
        r"""struct (.{0,128}?) :.{0,128}?IFlatbufferObject.{0,128}?
\{
(.+?)
\}
""",
        re.M | re.S,
    )
    """Get structure name and its field."""

    struct_property = re.compile(r"""public (.+) (.+?) { get; }""")
    """Get property type and name in field."""

    enum = re.compile(
        r"""// Namespace: FlatData
public enum (.{1,128}?) // TypeDefIndex: \d+?
{
	// Fields
	public (.+?) value__; // 0x0
(.+?)
}""",
        re.M | re.S,
    )
    """Get value, type of enum and enum field."""
    enum_member = re.compile(r"public const .+? (.+?) = (-?\d+?);")
    """Get member name, value in enum."""

    table_data_type = re.compile(r"public Nullable<(.+?)> DataList\(int j\) { }")


class CSParser:
    def __init__(self, file_path: str) -> None:
        with open(file_path, "rt", encoding="utf8") as file:
            self.data = file.read()

    def parse_enum(self) -> list[EnumType]:
        """Extract enum from cs."""
        enums = []
        for enum_name, enum_type, content in Re.enum.findall(self.data):
            if "." in enum_name:
                continue

            enum_members = []
            for name, value in Re.enum_member.findall(content):
                enum_members.append(EnumMember(name, value))

            enums.append(EnumType(enum_name, enum_type, enum_members))

        return enums

    def __parse_struct_property(
        self, prop_type: str, prop_name: str, prop_data: str
    ) -> Property:
        """Extract struct from cs."""
        # Has list in struct if there have its length property.
        prop_is_list = False

        prop_type = prop_type.removeprefix("Nullable<").removesuffix(">")

        if len(prop_name) > 6 and prop_name.endswith("Length"):
            list_name = prop_name.removesuffix("Length")
            re_type_of_list = re.search(
                f"public (.+?) {list_name}\\(int j\\) {{ }}", prop_data
            )  # Get object type in list.

            if re_type_of_list:
                list_type = re_type_of_list.group(1)
                prop_is_list = True

                list_type = list_type.removeprefix("Nullable<").removesuffix(">")

                return Property(list_type, list_name, prop_is_list)

        return Property(prop_type, prop_name, prop_is_list)

    def parse_struct(self) -> list[StructTable]:
        """从数据中提取结构体"""
        structs = []
        # struct name, field
        for struct_name, struct_data in Re.struct.findall(self.data):
            struct_properties = []
            for prop in Re.struct_property.finditer(struct_data):
                prop_type = prop.group(1)
                prop_name = prop.group(2)

                if "ByteBuffer" in prop_name:
                    continue

                if extracted_property := self.__parse_struct_property(
                    prop_type, prop_name, struct_data
                ):
                    struct_properties.append(extracted_property)

            if struct_properties:
                structs.append(StructTable(struct_name, struct_properties))

        return structs


class CompileToPython:
    DUMP_WRAPPER_NAME = "dump_wrapper"

    def __init__(
        self, enums: list[EnumType], structs: list[StructTable], extract_dir: str
    ) -> None:
        self.enums = enums
        self.structs = structs
        self.extract_dir = extract_dir

    def __type_in_struct_or_num(
        self, prop_type: str, structs: list[StructTable], enums: list[EnumType]
    ) -> StructTable | EnumType | None:
        for enum in enums:
            if prop_type == enum.name and enum.underlying_type in DataFlag.__members__:
                return enum

        for struct in structs:
            if prop_type == struct.name:
                return struct

        return None

    def __convert_scalar_type(
        self, prop: Property, index: int, p_name: str, f_offset: int, t_size: int
    ) -> tuple[str, str]:
        t_flag = DataFlag[prop.data_type].value
        if prop.is_list:
            return String.FB_SCALAR_LIST_CLASS_METHODS(
                p_name,
                f_offset,
                t_flag,
                t_size,
                p_name,
                f_offset,
                t_flag,
                p_name,
                f_offset,
                p_name,
                f_offset,
            ), String.FB_LIST_AND_NON_SCALAR_PROPERTY_FUNCTION(
                p_name, p_name, index, p_name, p_name, t_size, t_size
            )

        return String.FB_SCALAR_PROPERTY_CLASS_METHODS(
            p_name, f_offset, t_flag
        ), String.FB_SCALAR_PROPERTY_FUNCTION(p_name, p_name, t_flag, index, p_name)

    def __convert_string_type(
        self, prop: Property, index: int, p_name: str, f_offset: int
    ) -> tuple[str, str]:
        t_size = DataSize[prop.data_type].value
        if prop.is_list:
            return String.FB_STRING_LIST_CLASS_METHODS(
                p_name, f_offset, p_name, f_offset, p_name, f_offset
            ), String.FB_LIST_AND_NON_SCALAR_PROPERTY_FUNCTION(
                p_name, p_name, index, p_name, p_name, t_size, t_size
            )
        return String.FB_STRING_PROPERTY_CLASS_METHODS(
            p_name, f_offset
        ), String.FB_STRING_AND_STRUCT_PROPERTY_FUNCTION(p_name, p_name, index, p_name)

    def __convert_enum_type(
        self,
        prop: Property,
        enum: EnumType,
        index: int,
        p_name: str,
        f_offset: int,
        t_size: int,
    ) -> tuple[str, str]:
        t_flag = DataFlag[enum.underlying_type].value
        if prop.is_list:
            return String.FB_SCALAR_LIST_CLASS_METHODS(
                p_name,
                f_offset,
                t_flag,
                t_size,
                p_name,
                f_offset,
                t_flag,
                p_name,
                f_offset,
                p_name,
                f_offset,
            ), String.FB_LIST_AND_NON_SCALAR_PROPERTY_FUNCTION(
                p_name, p_name, index, p_name, p_name, t_size, t_size
            )

        return String.FB_SCALAR_PROPERTY_CLASS_METHODS(
            p_name, f_offset, t_flag
        ), String.FB_SCALAR_PROPERTY_FUNCTION(p_name, p_name, t_flag, index, p_name)

    def __convert_struct_type(
        self, prop: Property, index: int, p_name: str, f_offset: int
    ) -> tuple[str, str]:
        p_type = prop.data_type
        t_size = DataSize.struct.value
        if prop.is_list:
            return String.FB_NON_SCALAR_LIST_CLASS_METHODS(
                p_name,
                f_offset,
                t_size,
                p_type,
                p_type,
                p_type,
                p_name,
                f_offset,
                p_name,
                f_offset,
            ), String.FB_LIST_AND_NON_SCALAR_PROPERTY_FUNCTION(
                p_name, p_name, index, p_name, p_name, t_size, t_size
            )

        return String.FB_STRUCT_PROPERTY_CLASS_METHODS(
            p_name,
            f_offset,
            p_type,
            p_type,
            p_type,
        ), String.FB_STRING_AND_STRUCT_PROPERTY_FUNCTION(p_name, p_name, index, p_name)

    def __convert_isolated_type(
        self, prop: Property, index: int, p_name: str, f_offset: int, t_size: int
    ) -> tuple[str, str]:
        p_type = prop.data_type
        func = String.FB_LIST_AND_NON_SCALAR_PROPERTY_FUNCTION(
            p_name, p_name, index, p_name, p_name, t_size, t_size
        )
        if prop.is_list:
            return (
                String.FB_NON_SCALAR_LIST_CLASS_METHODS(
                    p_name,
                    f_offset,
                    t_size,
                    p_type,
                    p_type,
                    p_type,
                    p_name,
                    f_offset,
                    p_name,
                    f_offset,
                ),
                func,
            )

        return (
            String.FB_ISOLATED_PROPERTY_CLASS_METHODS(
                p_name, f_offset, p_type, p_type, p_type
            ),
            func,
        )

    def create_enum_files(self) -> None:
        """Convert enum to python."""
        os.makedirs(self.extract_dir, exist_ok=True)
        for enum in self.enums:
            enum_name = Utils.convert_name_to_available(enum.name)
            with open(
                f"{os.path.join(self.extract_dir, enum_name)}.py", "wt", encoding="utf8"
            ) as file:
                file.write(String.ENUM_CLASS(enum_name) + String.NEWLINE)
                for member in enum.members:
                    value = (
                        int(member.value)
                        if enum.underlying_type == "int"
                        else member.value
                    )

                    file.write(String.INDENT)
                    file.write(
                        String.VARIABLE_ASSIGNMENT(
                            Utils.convert_name_to_available(member.name), value
                        )
                    )
                    file.write(String.NEWLINE)

    def create_struct_files(self) -> None:
        """Convert struct to python."""
        os.makedirs(self.extract_dir, exist_ok=True)
        for struct in self.structs:
            struct_name = Utils.convert_name_to_available(struct.name)
            function_string = String.FB_START_AND_END_FUNCTION(len(struct.properties))
            file = open(
                f"{os.path.join(self.extract_dir, struct_name)}.py",
                "wt",
                encoding="utf8",
            )
            file.write(String.FB_BASIC_CLASS(struct_name, struct_name))

            for index, prop in enumerate(struct.properties):
                method, func = "", ""
                field_offset = 4 + 2 * index
                type_size = (
                    DataSize[prop.data_type].value
                    if prop.data_type in DataSize.__members__
                    else DataSize.struct.value
                )
                prop_name = Utils.convert_name_to_available(prop.name)

                # Prop is scalar type.
                if prop.data_type in DataFlag.__members__:
                    method, func = self.__convert_scalar_type(
                        prop, index, prop_name, field_offset, type_size
                    )

                # Prop is string type and not a list.
                elif prop.data_type == "string":
                    method, func = self.__convert_string_type(
                        prop, index, prop_name, field_offset
                    )

                # Prop type is struct or enum.
                elif prop_data := self.__type_in_struct_or_num(
                    prop.data_type, self.structs, self.enums
                ):
                    if isinstance(prop_data, StructTable):
                        method, func = self.__convert_struct_type(
                            prop, index, prop_name, field_offset
                        )
                    elif isinstance(prop_data, EnumType):
                        method, func = self.__convert_enum_type(
                            prop, prop_data, index, prop_name, field_offset, type_size
                        )

                # Prop is a isolated type.
                if not (method or func):
                    method, func = self.__convert_isolated_type(
                        prop, index, prop_name, field_offset, type_size
                    )

                file.write(method)
                function_string += func

            if function_string:
                file.write(String.NEWLINE * 2 + function_string)

        file.close()

    def create_module_file(self) -> None:
        """Create flatbuffer module file."""
        with open(
            os.path.join(self.extract_dir, "__init__.py"),
            "wt",
            encoding="utf8",
        ) as file:
            for enum in self.enums:
                enum_name = Utils.convert_name_to_available(enum.name)
                file.write(String.LOCAL_IMPORT(enum_name, enum_name) + String.NEWLINE)

            for struct in self.structs:
                struct_name = Utils.convert_name_to_available(struct.name)
                file.write(
                    String.LOCAL_IMPORT(struct_name, struct_name) + String.NEWLINE
                )

    def __wrap_list_prop(self, prop: Property, p_name: str) -> str:
        func, convertion = "", ""
        if prop.data_type in ConvertFlag.__members__:
            convertion = String.WRAPPER_PASSWD_CONVERTION(
                ConvertFlag[prop.data_type].value, String.WRAPPER_LIST_GETTER(p_name)
            )
        elif prop_data := self.__type_in_struct_or_num(
            prop.data_type, self.structs, self.enums
        ):
            data_name = Utils.convert_name_to_available(prop_data.name)
            if isinstance(prop_data, StructTable):
                convertion = String.WRAPPER_PASSWD_CONVERTION(
                    f"dump_{Utils.convert_name_to_available(data_name)}",
                    String.WRAPPER_LIST_GETTER(p_name),
                )

            elif isinstance(prop_data, EnumType):
                convertion = String.WRAPPER_ENUM_CONVERTION(
                    data_name,
                    String.WRAPPER_PASSWD_CONVERTION(
                        ConvertFlag[prop_data.underlying_type].value,
                        String.WRAPPER_LIST_GETTER(p_name),
                    ),
                )

        elif prop.data_type == "bool":
            convertion = String.WRAPPER_LIST_GETTER(p_name)

        if convertion:
            func = String.WRAPPER_LIST_CONVERTION(convertion, p_name)

        if func:
            func = String.WRAPPER_LIST_KV(p_name, func)

        return func

    def __wrap_prop(self, prop: Property, p_name: str) -> str:
        func = ""
        if prop.data_type in ConvertFlag.__members__:
            func = String.WRAPPER_PASSWD_CONVERTION(
                ConvertFlag[prop.data_type].value, String.WRAPPER_GETTER(p_name)
            )

        elif prop_data := self.__type_in_struct_or_num(
            prop.data_type, self.structs, self.enums
        ):
            data_name = Utils.convert_name_to_available(prop_data.name)
            if isinstance(prop_data, StructTable):
                func = String.WRAPPER_PASSWD_CONVERTION(
                    f"dump_{Utils.convert_name_to_available(data_name)}",
                    String.WRAPPER_GETTER(p_name),
                )

            elif isinstance(prop_data, EnumType):
                func = String.WRAPPER_ENUM_CONVERTION(
                    data_name,
                    String.WRAPPER_PASSWD_CONVERTION(
                        ConvertFlag[prop_data.underlying_type].value,
                        String.WRAPPER_GETTER(p_name),
                    ),
                )
        elif prop.data_type == "bool":
            func = String.WRAPPER_GETTER(p_name)

        if func:
            func = String.WRAPPER_PROP_KV(p_name, func)

        return func

    def create_dump_dict_file(self) -> None:
        """Dump excel structure of table to python dict."""
        file = open(
            os.path.join(self.extract_dir, f"{self.DUMP_WRAPPER_NAME}.py"),
            "wt",
            encoding="utf8",
        )
        file.write(String.WRAPPER_BASE)

        for enum in self.enums:
            file.write(
                String.WRAPPER_INT_ENUM(Utils.convert_name_to_available(enum.name))
                + String.NEWLINE
            )
            if enum.underlying_type != "int":
                notice(f"Not implementation for enum type: {enum.underlying_type}.")
            for kv in enum.members:
                file.write(
                    String.INDENT
                    + String.VARIABLE_ASSIGNMENT(
                        Utils.convert_name_to_available(kv.name), kv.value
                    )
                    + String.NEWLINE
                )
            file.write(String.NEWLINE)

        for struct in self.structs:
            # if struct.name.endswith("Table"):
            # continue
            struct_name = Utils.convert_name_to_available(struct.name)
            items = ""
            for prop in struct.properties:
                prop_name = Utils.convert_name_to_available(prop.name)
                func = ""

                if prop.is_list:
                    func = self.__wrap_list_prop(prop, prop_name)

                else:
                    func = self.__wrap_prop(prop, prop_name)

                items += String.INDENT * 2 + func
            file.write(String.WRAPPER_FUNC(struct_name, items))

        file.close()
