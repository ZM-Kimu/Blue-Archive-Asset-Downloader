from __future__ import annotations

import struct
from typing import Any

from .default_values import BinaryTypeTable
from .standard_metadata import HEADER_V27_2 as STANDARD_HEADER_ORDER_V27_2

NULL_INDEX = 0xFFFFFFFF
IL2CPP_TYPE_BOOLEAN = 0x02
IL2CPP_TYPE_CHAR = 0x03
IL2CPP_TYPE_I1 = 0x04
IL2CPP_TYPE_U1 = 0x05
IL2CPP_TYPE_I2 = 0x06
IL2CPP_TYPE_U2 = 0x07
IL2CPP_TYPE_I4 = 0x08
IL2CPP_TYPE_U4 = 0x09
IL2CPP_TYPE_I8 = 0x0A
IL2CPP_TYPE_U8 = 0x0B
IL2CPP_TYPE_R4 = 0x0C
IL2CPP_TYPE_R8 = 0x0D
IL2CPP_TYPE_STRING = 0x0E
IL2CPP_TYPE_VALUETYPE = 0x11
IL2CPP_TYPE_CLASS = 0x12
IL2CPP_TYPE_GENERICINST = 0x15
IL2CPP_TYPE_I = 0x18
IL2CPP_TYPE_U = 0x19
IL2CPP_TYPE_OBJECT = 0x1C
IL2CPP_TYPE_SZARRAY = 0x1D
IL2CPP_TYPE_ENUM = 0x55
IL2CPP_TYPE_IL2CPP_TYPE_INDEX = 0xFF


FIXED_SIZES = {
    IL2CPP_TYPE_BOOLEAN: 1,
    IL2CPP_TYPE_I1: 1,
    IL2CPP_TYPE_U1: 1,
    IL2CPP_TYPE_CHAR: 2,
    IL2CPP_TYPE_I2: 2,
    IL2CPP_TYPE_U2: 2,
    IL2CPP_TYPE_I4: None,
    IL2CPP_TYPE_U4: None,
    IL2CPP_TYPE_R4: 4,
    IL2CPP_TYPE_I8: 8,
    IL2CPP_TYPE_U8: 8,
    IL2CPP_TYPE_R8: 8,
    IL2CPP_TYPE_I: 8,
    IL2CPP_TYPE_U: 8,
}


class BlobReader:
    def __init__(self, data: bytes, start: int = 0):
        self.data = data
        self.pos = start

    def need(self, count: int) -> None:
        if self.pos + count > len(self.data):
            raise EOFError(
                f"need {count} bytes at 0x{self.pos:X}, len=0x{len(self.data):X}"
            )

    def u8(self) -> int:
        self.need(1)
        value = self.data[self.pos]
        self.pos += 1
        return value

    def u32_unaligned(self) -> int:
        self.need(4)
        value = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return value

    def skip(self, count: int) -> None:
        self.need(count)
        self.pos += count

    def compressed_uint(self) -> int:
        b = self.u8()
        if b < 128:
            return b
        if b == 240:
            return self.u32_unaligned()
        if b == 255:
            return 0xFFFFFFFF
        if b == 254:
            return 0xFFFFFFFE
        if b & 0xC0 == 0xC0:
            return (
                ((b & ~0xC0) << 24) | (self.u8() << 16) | (self.u8() << 8) | self.u8()
            )
        if b & 0x80 == 0x80:
            return ((b & ~0x80) << 8) | self.u8()
        raise ValueError(
            f"invalid compressed uint first byte 0x{b:02X} at 0x{self.pos - 1:X}"
        )

    def compressed_int(self) -> int:
        unsigned = self.compressed_uint()
        if unsigned == 0xFFFFFFFF:
            return -2147483648
        is_negative = unsigned & 1
        value = unsigned >> 1
        return -(value + 1) if is_negative else value


class MetadataTypeInfo:
    def __init__(self, metadata: bytes):
        self.sections = {
            name: struct.unpack_from("<II", metadata, 8 + index * 8)
            for index, name in enumerate(STANDARD_HEADER_ORDER_V27_2)
        }
        type_off, type_size = self.sections["typeDefinitions"]
        self.type_count = type_size // 0x58
        self.element_type_indices: list[int] = []
        for index in range(self.type_count):
            row_off = type_off + index * 0x58
            raw = struct.unpack_from("<22I", metadata, row_off)
            self.element_type_indices.append(raw[5])

        self.method_count = self.sections["methods"][1] // 0x20

    def enum_underlying_type_index(self, type_definition_index: int) -> int | None:
        if type_definition_index < 0 or type_definition_index >= self.type_count:
            return None
        value = self.element_type_indices[type_definition_index]
        return None if value == NULL_INDEX else value


class BinaryTypes(BinaryTypeTable):
    def type_record(self, type_index: int) -> tuple[int, int] | None:
        if type_index < 0 or type_index >= self.type_count:
            return None
        ptr = struct.unpack_from(
            "<Q", self.elf.data, self.type_ptrs_offset + type_index * 8
        )[0]
        offset = self.elf.va_to_offset(ptr)
        if offset is None:
            return None
        datapoint = struct.unpack_from("<Q", self.elf.data, offset)[0]
        bits = struct.unpack_from("<I", self.elf.data, offset + 8)[0]
        return (bits >> 16) & 0xFF, datapoint & 0xFFFFFFFF


def primitive_or_special_skip(reader: BlobReader, type_enum: int) -> None:
    if type_enum == IL2CPP_TYPE_I4:
        reader.compressed_int()
        return
    if type_enum == IL2CPP_TYPE_U4:
        reader.compressed_uint()
        return
    if type_enum == IL2CPP_TYPE_STRING:
        length = reader.compressed_int()
        if length > 0:
            reader.skip(length)
        return
    if type_enum == IL2CPP_TYPE_IL2CPP_TYPE_INDEX:
        reader.compressed_int()
        return
    fixed = FIXED_SIZES.get(type_enum)
    if fixed is not None:
        reader.skip(fixed)
        return
    if type_enum == IL2CPP_TYPE_OBJECT:
        # Object values are prefixed with their actual type in Unity's v29 blob.
        parse_value(reader, None, None, reader.u8())
        return
    raise ValueError(
        f"unsupported primitive/special type 0x{type_enum:02X} at 0x{reader.pos:X}"
    )


def parse_value(
    reader: BlobReader,
    binary_types: BinaryTypes | None,
    metadata_types: MetadataTypeInfo | None,
    type_enum: int | None = None,
) -> None:
    if type_enum is None:
        type_enum = reader.u8()

    if type_enum == IL2CPP_TYPE_ENUM:
        enum_type_index = reader.compressed_int()
        if binary_types is None or metadata_types is None:
            raise ValueError("enum encountered without type tables")
        enum_record = binary_types.type_record(enum_type_index)
        if enum_record is None:
            raise ValueError(f"enum type index out of range: {enum_type_index}")
        enum_kind, type_def_index = enum_record
        if enum_kind not in {IL2CPP_TYPE_VALUETYPE, IL2CPP_TYPE_CLASS}:
            raise ValueError(
                f"enum type index {enum_type_index} points to type enum 0x{enum_kind:02X}"
            )
        underlying_index = metadata_types.enum_underlying_type_index(type_def_index)
        underlying_kind = binary_types.type_enum(
            underlying_index if underlying_index is not None else -1
        )
        if underlying_kind is None:
            raise ValueError(
                f"enum underlying type missing for typedef {type_def_index}"
            )
        primitive_or_special_skip(reader, underlying_kind)
        return

    if type_enum == IL2CPP_TYPE_SZARRAY:
        length = reader.compressed_int()
        if length == -1:
            return
        if length < 0 or length > 100000:
            raise ValueError(f"array length out of range: {length}")
        arr_type = reader.u8()
        if arr_type == IL2CPP_TYPE_ENUM:
            enum_type_index = reader.compressed_int()
            if binary_types is None or metadata_types is None:
                raise ValueError("enum array encountered without type tables")
            enum_record = binary_types.type_record(enum_type_index)
            if enum_record is None:
                raise ValueError(
                    f"enum array type index out of range: {enum_type_index}"
                )
            _enum_kind, type_def_index = enum_record
            underlying_index = metadata_types.enum_underlying_type_index(type_def_index)
            underlying_kind = binary_types.type_enum(
                underlying_index if underlying_index is not None else -1
            )
            if underlying_kind is None:
                raise ValueError(
                    f"enum array underlying type missing for typedef {type_def_index}"
                )
            arr_type = underlying_kind
        elements_are_prefixed = reader.u8()
        if elements_are_prefixed not in {0, 1}:
            raise ValueError(f"array prefix flag out of range: {elements_are_prefixed}")
        if elements_are_prefixed and arr_type != IL2CPP_TYPE_OBJECT:
            raise ValueError(
                f"array elements are prefixed but array type is 0x{arr_type:02X}"
            )
        for _ in range(length):
            parse_value(
                reader,
                binary_types,
                metadata_types,
                reader.u8() if elements_are_prefixed else arr_type,
            )
        return

    if type_enum in {IL2CPP_TYPE_CLASS, IL2CPP_TYPE_GENERICINST}:
        raise ValueError(f"unsupported object-like attribute type 0x{type_enum:02X}")

    primitive_or_special_skip(reader, type_enum)


def parse_attribute_blob(
    data: bytes,
    offset: int,
    method_count: int,
    binary_types: BinaryTypes | None,
    metadata_types: MetadataTypeInfo | None,
) -> tuple[int, dict[str, Any]]:
    reader = BlobReader(data, offset)
    attribute_count = reader.compressed_uint()
    if attribute_count <= 0 or attribute_count > 4096:
        raise ValueError(f"attribute count out of range: {attribute_count}")
    constructors = [reader.u32_unaligned() for _ in range(attribute_count)]
    bad_ctor = [value for value in constructors if value >= method_count]
    if bad_ctor:
        raise ValueError(f"constructor index out of range: {bad_ctor[:3]}")

    ctor_args_total = 0
    fields_total = 0
    props_total = 0
    for _ctor in constructors:
        num_ctor_args = reader.compressed_uint()
        num_fields = reader.compressed_uint()
        num_props = reader.compressed_uint()
        if num_ctor_args > 64 or num_fields > 256 or num_props > 256:
            raise ValueError(
                f"attribute member counts out of range: args={num_ctor_args} fields={num_fields} props={num_props}"
            )
        ctor_args_total += num_ctor_args
        fields_total += num_fields
        props_total += num_props
        for _ in range(num_ctor_args):
            parse_value(reader, binary_types, metadata_types)
        for _ in range(num_fields):
            parse_value(reader, binary_types, metadata_types)
            member_index = reader.compressed_int()
            if member_index < 0:
                reader.compressed_uint()
        for _ in range(num_props):
            parse_value(reader, binary_types, metadata_types)
            member_index = reader.compressed_int()
            if member_index < 0:
                reader.compressed_uint()

    return reader.pos, {
        "attribute_count": attribute_count,
        "constructors": constructors,
        "ctor_args": ctor_args_total,
        "fields": fields_total,
        "props": props_total,
    }
