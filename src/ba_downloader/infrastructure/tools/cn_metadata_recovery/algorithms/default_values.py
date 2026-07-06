from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Any

from .codegen_registration import RelocatedElf
from .standard_metadata import (
    HEADER_V27_2 as STANDARD_HEADER_ORDER_V27_2,
)
from .standard_metadata import (
    Section,
    read_string,
    sha256_hex,
)

DEFAULT_METADATA_REGISTRATION_VA = 0xA3D18A0

BinaryTypeRecord = dict[str, int] | tuple[int, int]
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
IL2CPP_TYPE_I = 0x18
IL2CPP_TYPE_U = 0x19

FIXED_DEFAULT_SIZES = {
    IL2CPP_TYPE_BOOLEAN: 1,
    IL2CPP_TYPE_I1: 1,
    IL2CPP_TYPE_U1: 1,
    IL2CPP_TYPE_CHAR: 2,
    IL2CPP_TYPE_I2: 2,
    IL2CPP_TYPE_U2: 2,
    IL2CPP_TYPE_I4: 4,
    IL2CPP_TYPE_U4: 4,
    IL2CPP_TYPE_R4: 4,
    IL2CPP_TYPE_I8: 8,
    IL2CPP_TYPE_U8: 8,
    IL2CPP_TYPE_R8: 8,
    IL2CPP_TYPE_I: 8,
    IL2CPP_TYPE_U: 8,
}


def u32(buf: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", buf, offset)[0]


def read_sections(buf: bytes | bytearray) -> dict[str, tuple[int, int]]:
    if u32(buf, 0) != 0xFAB11BAF or u32(buf, 4) != 27:
        raise ValueError("expected a standardized v27 metadata candidate")
    return {
        name: struct.unpack_from("<II", buf, 8 + index * 8)
        for index, name in enumerate(STANDARD_HEADER_ORDER_V27_2)
    }


class BinaryTypeTable:
    def __init__(self, elf: RelocatedElf, metadata_registration_va: int):
        reg_offset = elf.va_to_offset(metadata_registration_va)
        if reg_offset is None:
            raise ValueError(
                f"metadata registration is not mapped: 0x{metadata_registration_va:X}"
            )
        reg = struct.unpack_from("<16Q", elf.data, reg_offset)
        self.generic_inst_count = reg[2]
        self.type_count = reg[6]
        type_ptrs_offset = elf.va_to_offset(reg[7])
        if type_ptrs_offset is None:
            raise ValueError("type pointer table is not mapped")
        self.type_ptrs_offset = type_ptrs_offset
        self.elf = elf

    def type_enum(self, type_index: int) -> int | None:
        record = self.type_record(type_index)
        if isinstance(record, tuple):
            return record[0]
        return None if record is None else record["type_enum"]

    def type_record(self, type_index: int) -> BinaryTypeRecord | None:
        if type_index < 0 or type_index >= self.type_count:
            return None
        ptr = struct.unpack_from(
            "<Q", self.elf.data, self.type_ptrs_offset + type_index * 8
        )[0]
        offset = self.elf.va_to_offset(ptr)
        if offset is None:
            return None
        datapoint = struct.unpack_from("<Q", self.elf.data, offset)[0] & 0xFFFFFFFF
        bits = struct.unpack_from("<I", self.elf.data, offset + 8)[0]
        return {
            "type_enum": (bits >> 16) & 0xFF,
            "datapoint": datapoint,
            "bits": bits,
        }


class MetadataNames:
    def __init__(
        self, metadata: bytes | bytearray, sections: dict[str, tuple[int, int]]
    ):
        self.metadata = bytes(metadata)
        self.strings = Section(*sections["string"])
        self.type_definitions = Section(*sections["typeDefinitions"])

    @property
    def type_definition_count(self) -> int:
        return self.type_definitions.size // 0x58

    def type_definition_name(self, type_definition_index: int) -> str:
        if (
            type_definition_index < 0
            or type_definition_index >= self.type_definition_count
        ):
            return ""
        row_offset = self.type_definitions.offset + type_definition_index * 0x58
        name_index = u32(self.metadata, row_offset)
        return read_string(self.metadata, self.strings, name_index)


def default_payload_is_valid(
    metadata: bytes | bytearray,
    data_offset: int,
    data_size: int,
    type_enum: int | None,
    data_index: int,
) -> bool:
    if data_index == NULL_INDEX:
        return True
    if type_enum is None or data_index < 0 or data_index >= data_size:
        return False

    if type_enum in FIXED_DEFAULT_SIZES:
        return data_index + FIXED_DEFAULT_SIZES[type_enum] <= data_size

    if type_enum == IL2CPP_TYPE_STRING:
        if data_index + 4 > data_size:
            return False
        length = struct.unpack_from("<i", metadata, data_offset + data_index)[0]
        return 0 <= length <= 64 * 1024 and data_index + 4 + length <= data_size

    return False


def read_unity_compressed_uint(
    data: bytes | bytearray, offset: int, limit: int
) -> tuple[int, int] | None:
    if offset >= limit:
        return None
    first = data[offset]
    if first < 0x80:
        return first, 1
    if first == 0xF0:
        if offset + 5 > limit:
            return None
        return struct.unpack_from("<I", data, offset + 1)[0], 5
    if first == 0xFF:
        return 0xFFFFFFFF, 1
    if first == 0xFE:
        return 0xFFFFFFFE, 1
    if first & 0xC0 == 0xC0:
        if offset + 4 > limit:
            return None
        return ((first & ~0xC0) << 24) | (data[offset + 1] << 16) | (
            data[offset + 2] << 8
        ) | data[offset + 3], 4
    if first & 0x80 == 0x80:
        if offset + 2 > limit:
            return None
        return ((first & ~0x80) << 8) | data[offset + 1], 2
    return None


def read_unity_compressed_int(
    data: bytes | bytearray, offset: int, limit: int
) -> tuple[int, int] | None:
    result = read_unity_compressed_uint(data, offset, limit)
    if result is None:
        return None
    unsigned, byte_count = result
    if unsigned == 0xFFFFFFFF:
        return -2147483648, byte_count
    is_negative = unsigned & 1
    value = unsigned >> 1
    return (-(value + 1) if is_negative else value), byte_count


def is_reasonable_default_string(raw: bytes) -> bool:
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def try_read_v27_string(
    metadata: bytes | bytearray, data_offset: int, data_size: int, data_index: int
) -> bytes | None:
    if data_index + 4 > data_size:
        return None
    length = struct.unpack_from("<i", metadata, data_offset + data_index)[0]
    if length < 0 or length > 64 * 1024:
        return None
    start = data_offset + data_index + 4
    end = start + length
    if end > data_offset + data_size:
        return None
    raw = bytes(metadata[start:end])
    if length > 4096 or not is_reasonable_default_string(raw):
        return None
    return raw


def try_read_compressed_string(
    metadata: bytes | bytearray, data_offset: int, data_size: int, data_index: int
) -> bytes | None:
    limit = data_offset + data_size
    result = read_unity_compressed_int(metadata, data_offset + data_index, limit)
    if result is None:
        return None
    length, length_size = result
    if length < 0 or length > 64 * 1024:
        return None
    start = data_offset + data_index + length_size
    end = start + length
    if end > limit:
        return None
    raw = bytes(metadata[start:end])
    return raw if is_reasonable_default_string(raw) else None


def static_array_initializer_size(type_name: str) -> int | None:
    match = re.fullmatch(r"__StaticArrayInitTypeSize=(\d+)", type_name)
    return None if match is None else int(match.group(1))


def classify_default_payload(
    metadata: bytes | bytearray,
    sections: dict[str, tuple[int, int]],
    type_table: BinaryTypeTable,
    names: MetadataNames,
    type_index: int,
    data_index: int,
) -> tuple[str, bytes | None]:
    data_offset, data_size = sections["fieldAndParameterDefaultValueData"]
    if data_index == NULL_INDEX:
        return "null", None

    record = type_table.type_record(type_index if type_index != NULL_INDEX else -1)
    if not isinstance(record, dict) or data_index < 0 or data_index >= data_size:
        return "invalid", None

    type_enum = record["type_enum"]
    if type_enum in FIXED_DEFAULT_SIZES:
        size = FIXED_DEFAULT_SIZES[type_enum]
        if data_index + size <= data_size:
            return "fixed", None
        if data_index < data_size:
            remaining = bytes(
                metadata[data_offset + data_index : data_offset + data_size]
            )
            missing = size - len(remaining)
            if (
                0 < missing <= size
                and remaining
                and all(value == 0 for value in remaining)
            ):
                return "fixed_zero_padded", remaining + (b"\0" * missing)
        return "invalid", None

    if type_enum == IL2CPP_TYPE_STRING:
        compressed = try_read_compressed_string(
            metadata, data_offset, data_size, data_index
        )
        if compressed is not None:
            return "string_compressed", struct.pack("<i", len(compressed)) + compressed
        v27 = try_read_v27_string(metadata, data_offset, data_size, data_index)
        if v27 is not None:
            return "string_v27", None
        return "invalid", None

    if type_enum == IL2CPP_TYPE_VALUETYPE:
        type_name = names.type_definition_name(record["datapoint"])
        static_size = static_array_initializer_size(type_name)
        if static_size is not None and data_index + static_size <= data_size:
            return "static_array", None
        return "invalid", None

    return "invalid", None


def section_bytes(metadata: bytes | bytearray, section: tuple[int, int]) -> bytes:
    offset, size = section
    if offset == 0 and size == 0:
        return b""
    return bytes(metadata[offset : offset + size])


def rebuild_metadata(
    metadata: bytes | bytearray,
    sections: dict[str, tuple[int, int]],
    replacements: dict[str, bytes],
) -> bytes:
    out = bytearray(0x100)
    struct.pack_into("<II", out, 0, 0xFAB11BAF, 27)
    cursor = 0x100

    for index, name in enumerate(STANDARD_HEADER_ORDER_V27_2):
        data = replacements.get(name, section_bytes(metadata, sections[name]))
        if data:
            padding = (-cursor) & 3
            if padding:
                out += b"\0" * padding
                cursor += padding
            offset = cursor
            out += data
            cursor += len(data)
        else:
            offset = 0
        struct.pack_into("<II", out, 8 + index * 8, offset, len(data))

    return bytes(out)


def clear_image_custom_attribute_ranges(
    metadata: bytes | bytearray, sections: dict[str, tuple[int, int]]
) -> bytes:
    image_data = bytearray(section_bytes(metadata, sections["images"]))
    if len(image_data) % 0x28:
        raise ValueError("image section size is not divisible by 0x28")
    for index in range(len(image_data) // 0x28):
        row_offset = index * 0x28
        struct.pack_into("<II", image_data, row_offset + 0x20, 0, 0)
    return bytes(image_data)


def sanitize_default_section(
    metadata: bytes | bytearray,
    sections: dict[str, tuple[int, int]],
    type_table: BinaryTypeTable,
    names: MetadataNames,
    section_name: str,
    target_section_name: str,
    appended_default_data: bytearray,
) -> tuple[bytes, dict[str, Any]]:
    section_offset, section_size = sections[section_name]
    target_count = sections[target_section_name][1] // 0x0C
    _data_offset, _data_size = sections["fieldAndParameterDefaultValueData"]

    total = section_size // 0x0C
    kept = 0
    dropped = 0
    by_type: dict[str, int] = {}
    by_action: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    sanitized = bytearray()

    for index in range(total):
        row_offset = section_offset + index * 0x0C
        target_index, type_index, data_index = struct.unpack_from(
            "<III", metadata, row_offset
        )
        type_enum = type_table.type_enum(type_index if type_index != NULL_INDEX else -1)
        by_type[str(type_enum)] = by_type.get(str(type_enum), 0) + 1

        valid_target = target_index == NULL_INDEX or target_index < target_count
        action, replacement_payload = classify_default_payload(
            metadata, sections, type_table, names, type_index, data_index
        )
        valid_payload = action != "invalid"
        by_action[action] = by_action.get(action, 0) + 1
        if valid_target and valid_payload:
            kept += 1
            if replacement_payload is None:
                sanitized += metadata[row_offset : row_offset + 0x0C]
            else:
                converted_index = len(appended_default_data)
                appended_default_data += replacement_payload
                sanitized += struct.pack(
                    "<III", target_index, type_index, converted_index
                )
            continue

        if len(examples) < 12:
            examples.append(
                {
                    "row": index,
                    "target_index": target_index,
                    "type_index": type_index,
                    "type_enum": type_enum,
                    "data_index": data_index,
                }
            )
        dropped += 1

    report = {
        "section": section_name,
        "total": total,
        "kept": kept,
        "dropped": dropped,
        "output_size": len(sanitized),
        "type_histogram": dict(sorted(by_type.items())),
        "action_histogram": dict(sorted(by_action.items())),
        "dropped_examples": examples,
    }
    return bytes(sanitized), report


def sanitize_default_values(
    binary: Path,
    metadata: bytes,
    metadata_registration_va: int = DEFAULT_METADATA_REGISTRATION_VA,
    *,
    keep_custom_attributes: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    elf = RelocatedElf(binary)
    type_table = BinaryTypeTable(elf, metadata_registration_va)
    sections = read_sections(metadata)
    names = MetadataNames(metadata, sections)

    report: dict[str, Any] = {
        "binary": str(binary),
        "metadata_sha256": sha256_hex(metadata),
        "metadata_registration_va": f"0x{metadata_registration_va:X}",
        "sections": [],
    }
    replacements: dict[str, bytes] = {}
    default_data = bytearray(
        section_bytes(metadata, sections["fieldAndParameterDefaultValueData"])
    )
    field_defaults, field_report = sanitize_default_section(
        metadata,
        sections,
        type_table,
        names,
        "fieldDefaultValues",
        "fields",
        default_data,
    )
    parameter_defaults, parameter_report = sanitize_default_section(
        metadata,
        sections,
        type_table,
        names,
        "parameterDefaultValues",
        "parameters",
        default_data,
    )
    replacements["fieldDefaultValues"] = field_defaults
    replacements["parameterDefaultValues"] = parameter_defaults
    replacements["fieldAndParameterDefaultValueData"] = bytes(default_data)
    if keep_custom_attributes:
        report["custom_attributes"] = "preserved from input metadata"
    else:
        replacements["images"] = clear_image_custom_attribute_ranges(metadata, sections)
        replacements["attributesInfo"] = b""
        replacements["attributeTypes"] = b""
        report["custom_attributes"] = (
            "image customAttributeStart/customAttributeCount and attribute sections cleared"
        )
    report["sections"].extend([field_report, parameter_report])

    sanitized_metadata = rebuild_metadata(metadata, sections, replacements)
    report["output_sha256"] = sha256_hex(sanitized_metadata)
    report["output_size"] = len(sanitized_metadata)
    return sanitized_metadata, report
