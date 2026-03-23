"""Organize memory pack structure."""

# TODO:Not complete yet
import struct
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, IntEnum
from io import BytesIO
from types import GenericAlias
from typing import Any, TypeVar, get_type_hints

T = TypeVar("T", int, float)


@dataclass
class DataSize:
    bool = 1
    byte = 1
    sbyte = 1
    short = 2
    ushort = 2
    int = 4
    uint = 4
    long = 8
    ulong = 8
    float = 4
    double = 8
    decimal = 16

    string = 4  # ptr
    struct = 4  # ptr


class MemoryPackDataType:
    size: int
    b_type: str
    is_scalar: bool
    convert: Any


class MPType:
    class bool(MemoryPackDataType):
        size = 1
        b_type = "?"
        is_scalar = True
        convert = bool

    class byte(MemoryPackDataType):
        size = 1
        b_type = "B"
        is_scalar = True
        convert = bytes

    class sbyte(MemoryPackDataType):
        size = 1
        b_type = "b"
        is_scalar = True
        convert = bytes

    class short(MemoryPackDataType):
        size = 2
        b_type = "h"
        is_scalar = True
        convert = int

    class ushort(MemoryPackDataType):
        size = 2
        b_type = "H"
        is_scalar = True
        convert = int

    class int(MemoryPackDataType):
        size = 4
        b_type = "i"
        is_scalar = True
        convert = int

    class uint(MemoryPackDataType):
        size = 4
        b_type = "I"
        is_scalar = True
        convert = int

    class long(MemoryPackDataType):
        size = 8
        b_type = "l"
        is_scalar = True
        convert = int

    class ulong(MemoryPackDataType):
        size = 8
        b_type = "L"
        is_scalar = True
        convert = int

    class float(MemoryPackDataType):
        size = 4
        b_type = "f"
        is_scalar = True
        convert = float

    class double(MemoryPackDataType):
        size = 8
        b_type = "d"
        is_scalar = True
        convert = float

    class decimal(MemoryPackDataType):
        size = 16
        b_type = "c"
        is_scalar = False

    class string(MemoryPackDataType):
        size = 4  # String length express as int
        b_type = "s"
        is_scalar = False
        convert = str

        @staticmethod
        def length(string_length: int) -> str:
            return f"{string_length}s"


class MediaType(IntEnum):
    none = 0
    audio = 1
    video = 2
    texture = 3


# data.read(I8)
# item_num = data.read(I32)
# data.read(I32)
# key = data.read_string()
# data.read(I8)
# data.read(I32)
# path = data.read_string()
# data.read(I32)
# file_name = data.read_string()
# bytes = data.read(I64)
# crc = data.read(I64)
# is_prologue = data.read(BOOL)
# is_split_download = data.read(BOOL)
# media_type = data.read(I32)

# path = path.replace("\\", "/")
# container.add_media_resource(
#     key, path, file_name, media_type, bytes, crc, is_prologue, is_split_download
# )


@dataclass
class MPNode:
    name: str
    data_type: Any
    is_container: bool  # One of list, tuple and dict
    parent: "MPNode|None" = None
    next: "MPNode|None" = None


@dataclass
class CaseSub:
    name: str


@dataclass
class CaseSubCatalog:
    name: str
    cases: list[CaseSub]
    cases_hash: dict[MPType.string, CaseSub]
    crcs: list[MPType.int]


@dataclass
class JPMedia:
    path: MPType.string
    file_name: MPType.string
    bytes: MPType.long
    crc: MPType.long
    is_prologue: MPType.bool
    is_split_download: MPType.bool
    media_type: MediaType


@dataclass
class JPMediaCatalog:
    table: dict[MPType.string, JPMedia]


@dataclass
class JPTableCatalog:
    name: str
    size: int
    crc: int
    is_inbuild: bool
    is_changed: bool
    is_prologue: bool
    is_split_download: bool
    includes: list[str]


BIT8: str = "b"
BIT32: str = "i"
BIT64: str = "q"
BOOL: str = "?"


class DataTree:
    container_type = (dict, tuple, list)

    def __init__(self, struct_class: Any) -> None:
        self.root: MPNode | None = None
        self.trees: list[MPNode] = []
        self.__parse_annotation(struct_class)

    def __resolve_type(self, type_anno: Any):

        if isinstance(type_anno, GenericAlias):
            origin_type = type_anno.__origin__
            args = type_anno.__args__
            args_annotations = [self.__parse_annotation(arg) for arg in args]

            if origin_type == dict:
                return {"key": args_annotations[0], "value": args_annotations[1]}
            return origin_type, args_annotations

        if issubclass(type_anno, Enum):
            if not issubclass(type_anno, IntEnum):
                raise TypeError("Current not support for enum underlying is not int.")
            type_anno = MPType.int

        if hasattr(type_anno, "__annotations__"):
            return self.__parse_annotation(type_anno)

        return type_anno

    def __parse_annotation(self, cls: Any, parent: MPNode | None = None) -> Any:
        annotations = get_type_hints(cls)

        if hasattr(cls, "__mro__") and issubclass(cls, MemoryPackDataType):
            return cls

        is_container = (
            isinstance(cls, GenericAlias) and cls.__origin__ in self.container_type
        )
        root = MPNode(cls.__name__, cls, is_container, parent)

        if not self.root:
            self.root = root
        self.trees.append(root)

        prev: MPNode | None = None
        for name, anno in annotations.items():
            resolved_type = self.__resolve_type(anno)

            is_container = isinstance(resolved_type, self.container_type)
            current = MPNode(name, resolved_type, is_container, root)

            self.trees.append(current)

            if prev:
                prev.next = current
            prev = current

            # if hasattr(anno, "__annotations__"):
            #     self.__parse_annotation(anno, current)
        return root

    def print_tree(self) -> None:
        for node in self.trees:
            parent_name = node.parent.name if node.parent else "None"
            next_name = node.next.name if node.next else "None"
            print(
                f"Node: {node.name}, Type: {node.data_type}, is container Parent:{node.is_container}, {parent_name}, Next: {next_name}"
            )
        print(self.trees)


a = DataTree(JPMediaCatalog)


class MemoryPack:
    def __init__(self, data_structure: object, data: bytes) -> None:
        self.structure = data_structure
        self.byte_io = BytesIO(data)

    def read(self, format: str) -> bytes:
        return struct.unpack(format, self.byte_io.read(struct.calcsize(format)))[0]

    def __read_from_tree(self, data_tree: DataTree) -> list:
        for tree in data_tree.trees:
            if tree.is_container:
                if isinstance(tree.data_type, dict):
                    pass
        data = []
        for d_type in data_tree:
            if d_type == MPType.string:
                string_length = int(self.read(MPType.int.b_type))
                data.append(self.read(MPType.string.convert(string_length)))
            else:
                data.append(self.read(d_type.b_type))
        return data

    def parse(self, offset_byte: int = 0):
        self.byte_io.read(offset_byte)
        data_struct: dict[str, Any] = self.__parse_annotation(self.structure)
        read_tree = self.__create_read_tree(data_struct)
        self.__parse_structure(data_struct, read_tree)


with open("MediaCatalog.bytes", "rb") as f:
    data = f.read()
table = MemoryPack(JPMediaCatalog, data)
table.parse(1)


I8: str = "b"
I32: str = "i"
I64: str = "q"
BOOL: str = "?"


class Reader:
    def __init__(self, initial_bytes) -> None:
        self.io = BytesIO(initial_bytes)

    def read(self, fmt: str) -> Any:
        return struct.unpack(fmt, self.io.read(struct.calcsize(fmt)))[0]

    def read_string(self) -> str:
        return self.io.read(self.read(I32)).decode(encoding="utf-8", errors="replace")

    def read_table_includes(self) -> list[str]:
        size = self.read(I32)
        if size == -1:
            return []
        self.read(I32)
        includes = []
        for i in range(size):
            includes.append(self.read_string())
            if i != size - 1:
                self.read(I32)
        return includes


r = Reader(data)
r.read(I8)

print(r.read(I32))
