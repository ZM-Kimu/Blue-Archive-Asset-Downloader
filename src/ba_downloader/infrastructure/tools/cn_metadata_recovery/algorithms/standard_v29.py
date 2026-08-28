from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from .attribute_blob import BinaryTypes, MetadataTypeInfo, parse_attribute_blob
from .codegen_registration import RelocatedElf
from .default_values import (
    FIXED_DEFAULT_SIZES,
    IL2CPP_TYPE_I4,
    IL2CPP_TYPE_STRING,
    IL2CPP_TYPE_U4,
    IL2CPP_TYPE_VALUETYPE,
    NULL_INDEX,
    BinaryTypeTable,
    MetadataNames,
    static_array_initializer_size,
)
from .standard_metadata import (
    HEADER_V27_2,
    HEADER_V29,
    Section,
    section_bytes,
    section_map,
    sha256_hex,
)


def read_v27_sections(metadata: bytes) -> dict[str, Section]:
    target, sections = section_map(metadata)
    if target != "27.2":
        raise ValueError(f"expected v27.2 metadata, got {target}")
    return sections


def count_custom_attribute_targets(
    metadata: bytes, sections: dict[str, Section]
) -> int:
    images = sections["images"]
    max_end = 0
    for index in range(images.size // 0x28):
        values = struct.unpack_from("<10I", metadata, images.offset + index * 0x28)
        start = struct.unpack("<i", struct.pack("<I", values[8]))[0]
        count = values[9]
        if start >= 0:
            max_end = max(max_end, start + count)
    return max_end


def encode_unity_compressed_uint(value: int) -> bytes:
    value &= 0xFFFFFFFF
    if value == 0xFFFFFFFF:
        return b"\xff"
    if value == 0xFFFFFFFE:
        return b"\xfe"
    if value < 0x80:
        return bytes([value])
    if value < 0x4000:
        return bytes([0x80 | (value >> 8), value & 0xFF])
    if value < 0x40000000:
        return bytes(
            [
                0xC0 | (value >> 24),
                (value >> 16) & 0xFF,
                (value >> 8) & 0xFF,
                value & 0xFF,
            ]
        )
    return b"\xf0" + struct.pack("<I", value)


def encode_unity_compressed_int(value: int) -> bytes:
    if value == -2147483648:
        return b"\xff"
    encoded = ((-value - 1) << 1) | 1 if value < 0 else value << 1
    return encode_unity_compressed_uint(encoded)


def read_v27_default_payload(
    metadata: bytes,
    sections: dict[str, Section],
    type_table: BinaryTypeTable,
    names: MetadataNames,
    type_enum: int | None,
    type_index: int,
    data_index: int,
) -> tuple[str, bytes | None]:
    data_section = sections["fieldAndParameterDefaultValueData"]
    if data_index == NULL_INDEX:
        return "null", None
    if type_enum is None or data_index < 0 or data_index >= data_section.size:
        return "invalid", None

    absolute = data_section.offset + data_index
    remaining = data_section.size - data_index
    if type_enum == IL2CPP_TYPE_I4:
        if remaining < 4:
            return "invalid", None
        value = struct.unpack_from("<i", metadata, absolute)[0]
        return "i4_compressed", encode_unity_compressed_int(value)
    if type_enum == IL2CPP_TYPE_U4:
        if remaining < 4:
            return "invalid", None
        value = struct.unpack_from("<I", metadata, absolute)[0]
        return "u4_compressed", encode_unity_compressed_uint(value)
    if type_enum == IL2CPP_TYPE_STRING:
        if remaining < 4:
            return "invalid", None
        length = struct.unpack_from("<i", metadata, absolute)[0]
        if length < 0 or length > remaining - 4:
            return "invalid", None
        raw = metadata[absolute + 4 : absolute + 4 + length]
        return "string_compressed", encode_unity_compressed_int(length) + raw
    if type_enum in FIXED_DEFAULT_SIZES:
        size = FIXED_DEFAULT_SIZES[type_enum]
        if remaining < size:
            return "invalid", None
        return "fixed", metadata[absolute : absolute + size]
    if type_enum == IL2CPP_TYPE_VALUETYPE:
        record = type_table.type_record(type_index if type_index != NULL_INDEX else -1)
        type_name = (
            names.type_definition_name(record["datapoint"])
            if isinstance(record, dict)
            else ""
        )
        static_size = static_array_initializer_size(type_name)
        if static_size is not None and remaining >= static_size:
            return "static_array", metadata[absolute : absolute + static_size]
        return "unsupported_valuetype", b"\0"
    return "unsupported", b"\0"


def convert_default_values_to_v29(
    v27_metadata: bytes,
    v27_sections: dict[str, Section],
    binary: Path,
    metadata_registration_va: int,
    *,
    relocated_elf: RelocatedElf | None = None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    type_table = BinaryTypeTable(
        relocated_elf or RelocatedElf(binary), metadata_registration_va
    )
    tuple_sections = {
        name: (section.offset, section.size) for name, section in v27_sections.items()
    }
    names = MetadataNames(v27_metadata, tuple_sections)
    out_data = bytearray()
    replacements: dict[str, bytes] = {}
    report: dict[str, Any] = {"sections": [], "action_histogram": {}}

    for section_name in ("parameterDefaultValues", "fieldDefaultValues"):
        section = v27_sections[section_name]
        converted_rows = bytearray()
        section_report: dict[str, Any] = {
            "section": section_name,
            "total": section.size // 0x0C,
            "converted": 0,
            "invalid": 0,
            "examples": [],
        }
        for index in range(section.size // 0x0C):
            row_offset = section.offset + index * 0x0C
            owner_index, type_index, data_index = struct.unpack_from(
                "<III", v27_metadata, row_offset
            )
            type_enum = type_table.type_enum(
                type_index if type_index != NULL_INDEX else -1
            )
            action, payload = read_v27_default_payload(
                v27_metadata,
                v27_sections,
                type_table,
                names,
                type_enum,
                type_index,
                data_index,
            )
            report["action_histogram"][action] = (
                report["action_histogram"].get(action, 0) + 1
            )

            if payload is None:
                converted_rows += struct.pack(
                    "<III", owner_index, type_index, NULL_INDEX
                )
            elif action == "invalid":
                section_report["invalid"] += 1
                if len(section_report["examples"]) < 12:
                    section_report["examples"].append(
                        {
                            "row": index,
                            "owner_index": owner_index,
                            "type_index": type_index,
                            "type_enum": type_enum,
                            "data_index": data_index,
                        }
                    )
                converted_rows += struct.pack(
                    "<III", owner_index, type_index, NULL_INDEX
                )
            else:
                converted_index = len(out_data)
                out_data += payload
                converted_rows += struct.pack(
                    "<III", owner_index, type_index, converted_index
                )
                section_report["converted"] += 1
        replacements[section_name] = bytes(converted_rows)
        report["sections"].append(section_report)

    replacements["fieldAndParameterDefaultValueData"] = bytes(out_data)
    report["fieldAndParameterDefaultValueData_size"] = len(out_data)
    return replacements, report


def extract_attribute_data(
    source_metadata: bytes,
    v27_metadata: bytes,
    binary: Path,
    metadata_registration_va: int,
    *,
    tail_offset: int,
    blob_start: int,
    target_count: int,
    relocated_elf: RelocatedElf | None = None,
) -> tuple[bytes, bytes, dict[str, Any]]:
    tail = source_metadata[tail_offset:]
    metadata_types = MetadataTypeInfo(v27_metadata)
    binary_types = BinaryTypes(
        relocated_elf or RelocatedElf(binary), metadata_registration_va
    )

    pos = blob_start
    totals = {"attributes": 0, "ctor_args": 0, "fields": 0, "props": 0}
    examples: list[dict[str, Any]] = []
    for index in range(target_count):
        next_pos, info = parse_attribute_blob(
            tail,
            pos,
            metadata_types.method_count,
            binary_types,
            metadata_types,
        )
        if len(examples) < 12:
            examples.append(
                {
                    "index": index,
                    "offset": f"0x{pos:X}",
                    "end": f"0x{next_pos:X}",
                    **info,
                }
            )
        totals["attributes"] += info["attribute_count"]
        totals["ctor_args"] += info["ctor_args"]
        totals["fields"] += info["fields"]
        totals["props"] += info["props"]
        if next_pos <= pos:
            raise ValueError(
                f"attribute parser did not advance at target {index}, offset 0x{pos:X}"
            )
        pos = next_pos

    blob_end = pos
    range_start = blob_end
    if tail[range_start : range_start + 2] == b"\xcc\xcc":
        range_start += 2
    else:
        range_start = (range_start + 3) & ~3

    range_size = (target_count + 1) * 8
    attribute_data_range = tail[range_start : range_start + range_size]
    if len(attribute_data_range) != range_size:
        raise ValueError("hidden tail is too short for v29 attributeDataRange")

    sentinel_token, sentinel_start = struct.unpack_from(
        "<II", attribute_data_range, target_count * 8
    )
    expected_sentinel_start = blob_end - blob_start
    if sentinel_start != expected_sentinel_start:
        raise ValueError(
            f"attributeDataRange sentinel mismatch: got 0x{sentinel_start:X}, expected 0x{expected_sentinel_start:X}"
        )

    attribute_data = tail[blob_start:blob_end]
    report = {
        "targetCount": target_count,
        "attributeData_size": len(attribute_data),
        "attributeDataRange_size": len(attribute_data_range),
        "blob_start": f"0x{blob_start:X}",
        "blob_end": f"0x{blob_end:X}",
        "range_start": f"0x{range_start:X}",
        "absolute_blob_start": f"0x{tail_offset + blob_start:X}",
        "absolute_blob_end": f"0x{tail_offset + blob_end:X}",
        "absolute_range_start": f"0x{tail_offset + range_start:X}",
        "sentinel": {
            "token": f"0x{sentinel_token:08X}",
            "startOffset": f"0x{sentinel_start:X}",
        },
        "totals": totals,
        "examples": examples,
    }
    return attribute_data, attribute_data_range, report


def assemble_standard_v29_sections(
    sections: dict[str, bytes],
) -> tuple[bytes, dict[str, dict[str, Any]]]:
    layout: list[tuple[int, bytes]] = []
    emitted: dict[str, dict[str, Any]] = {}
    cursor = 0x100
    for name in HEADER_V29:
        data = sections.get(name, b"")
        if data:
            cursor += (-cursor) & 3
            offset = cursor
            cursor += len(data)
        else:
            offset = 0
        layout.append((offset, data))
        emitted[name] = {"offset": f"0x{offset:X}", "size": len(data)}

    output = bytearray(cursor)
    struct.pack_into("<II", output, 0, 0xFAB11BAF, 29)
    for index, (offset, data) in enumerate(layout):
        struct.pack_into("<II", output, 8 + index * 8, offset, len(data))
        if data:
            output[offset : offset + len(data)] = data
    return bytes(output), emitted


def build_standard_v29_metadata(
    source_metadata: bytes,
    v27_metadata: bytes,
    binary: Path,
    metadata_registration_va: int = 0xA3D18A0,
    *,
    tail_offset: int = 0x01C9B1DC,
    blob_start: int = 0x870,
    relocated_elf: RelocatedElf | None = None,
) -> tuple[bytes, dict[str, Any]]:
    v27_sections = read_v27_sections(v27_metadata)
    target_count = count_custom_attribute_targets(v27_metadata, v27_sections)
    attribute_data, attribute_data_range, attribute_report = extract_attribute_data(
        source_metadata,
        v27_metadata,
        binary,
        metadata_registration_va,
        tail_offset=tail_offset,
        blob_start=blob_start,
        target_count=target_count,
        relocated_elf=relocated_elf,
    )

    default_replacements, default_report = convert_default_values_to_v29(
        v27_metadata,
        v27_sections,
        binary,
        metadata_registration_va,
        relocated_elf=relocated_elf,
    )

    replacements = {
        **default_replacements,
        "attributeData": attribute_data,
        "attributeDataRange": attribute_data_range,
    }
    section_payloads = {
        name: (
            replacements[name]
            if name in replacements
            else section_bytes(v27_metadata, v27_sections[name])
            if name in HEADER_V27_2
            else b""
        )
        for name in HEADER_V29
    }
    candidate, emitted = assemble_standard_v29_sections(section_payloads)
    report = {
        "source_sha256": sha256_hex(source_metadata),
        "v27_metadata_sha256": sha256_hex(v27_metadata),
        "output_sha256": sha256_hex(candidate),
        "output_size": len(candidate),
        "declared_version": 29,
        "allocation_strategy": "precomputed-single-buffer",
        "attributeData": attribute_report,
        "defaultValues": default_report,
        "emitted_sections": emitted,
        "note": (
            "This is a structural v29 attributeData/attributeDataRange candidate. "
            "It preserves the current v27.2 row layouts for non-attribute sections, "
            "but rewrites default-value payloads into the compressed form LibCpp2IL expects for metadata v29."
        ),
    }
    return candidate, report
