from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from .codegen_registration import RelocatedElf
from .standard_metadata import (
    HEADER_V27_2 as STANDARD_HEADER_ORDER_V27_2,
)
from .standard_metadata import (
    Section,
    read_section,
    sha256_hex,
)
from .standardize import CUSTOM_SECTIONS


def read_standard_sections(metadata: bytes) -> dict[str, tuple[int, int]]:
    if struct.unpack_from("<II", metadata, 0) != (0xFAB11BAF, 27):
        raise ValueError("expected standardized v27 metadata")
    return {
        name: struct.unpack_from("<II", metadata, 8 + index * 8)
        for index, name in enumerate(STANDARD_HEADER_ORDER_V27_2)
    }


def section_bytes(metadata: bytes, section: tuple[int, int]) -> bytes:
    offset, size = section
    if offset == 0 and size == 0:
        return b""
    return metadata[offset : offset + size]


def read_metadata_string(
    buf: bytes, string_section: Section, index: int, *, skip_leading_nuls: bool = False
) -> str:
    if index < 0 or index == 0xFFFFFFFF or index >= string_section.size:
        return ""
    pos = string_section.offset + index
    if skip_leading_nuls:
        while pos < string_section.end and buf[pos] == 0:
            pos += 1
    end = buf.find(b"\0", pos, min(len(buf), pos + 512))
    if end < 0:
        end = min(len(buf), pos + 512)
    return buf[pos:end].decode("utf-8", "replace")


def rebuild_metadata(metadata: bytes, replacements: dict[str, bytes]) -> bytes:
    sections = read_standard_sections(metadata)
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


def parse_source_image_custom_ranges(source: bytes) -> dict[str, tuple[int, int]]:
    sections = {
        name: read_section(source, off) for name, off in CUSTOM_SECTIONS.items()
    }
    strings = sections["string"]
    images = sections["imageRanges"]
    result: dict[str, tuple[int, int]] = {}
    for index in range(images.size // 0x28):
        values = struct.unpack_from("<10I", source, images.offset + index * 0x28)
        name = read_metadata_string(source, strings, values[0], skip_leading_nuls=True)
        result[name] = (values[8], values[9])
    return result


def parse_source_image_names(source: bytes) -> list[str]:
    sections = {
        name: read_section(source, off) for name, off in CUSTOM_SECTIONS.items()
    }
    strings = sections["string"]
    images = sections["imageRanges"]
    names: list[str] = []
    for index in range(images.size // 0x28):
        values = struct.unpack_from("<10I", source, images.offset + index * 0x28)
        names.append(
            read_metadata_string(source, strings, values[0], skip_leading_nuls=True)
        )
    return names


def parse_standard_image_names(metadata: bytes) -> list[str]:
    sections = read_standard_sections(metadata)
    string_off, string_size = sections["string"]
    image_off, image_size = sections["images"]
    names: list[str] = []
    for index in range(image_size // 0x28):
        values = struct.unpack_from("<10I", metadata, image_off + index * 0x28)
        names.append(
            read_metadata_string(
                metadata,
                Section(string_off, string_size),
                values[0],
                skip_leading_nuls=True,
            )
        )
    return names


def recover_referenced_assemblies(
    source: bytes,
    metadata: bytes,
    *,
    tail_offset: int,
    blob_start: int,
) -> tuple[bytes, dict[str, Any]]:
    sections = {
        name: read_section(source, off) for name, off in CUSTOM_SECTIONS.items()
    }
    assembly_summary = sections["assemblySummary"]
    source_names = parse_source_image_names(source)
    target_names = parse_standard_image_names(metadata)
    if sorted(source_names) != sorted(target_names):
        raise ValueError(
            "source/current image names differ; cannot remap referenced assemblies"
        )

    old_to_new = {
        old_index: target_names.index(name)
        for old_index, name in enumerate(source_names)
    }
    max_end = 0
    referenced_rows = []
    for index in range(assembly_summary.size // 0x40):
        values = struct.unpack_from(
            "<16I", source, assembly_summary.offset + index * 0x40
        )
        start = struct.unpack("<i", struct.pack("<I", values[2]))[0]
        count = values[3]
        referenced_rows.append((index, start, count))
        if start >= 0:
            max_end = max(max_end, start + count)

    prefix_size = max_end * 4
    if prefix_size > blob_start:
        raise ValueError(
            f"referenced assembly table exceeds pre-attribute tail prefix: need 0x{prefix_size:X}, have 0x{blob_start:X}"
        )

    tail = source[tail_offset:]
    if len(tail) < prefix_size:
        raise ValueError("hidden tail is too short for referenced assembly table")

    refs: list[int] = []
    for index in range(max_end):
        old_ref = struct.unpack_from("<I", tail, index * 4)[0]
        if old_ref not in old_to_new:
            raise ValueError(
                f"referenced assembly index {old_ref} at row {index} is not a known source image"
            )
        refs.append(old_to_new[old_ref])

    data = b"".join(struct.pack("<I", value) for value in refs)
    report = {
        "referencedAssemblyCount": len(refs),
        "sourcePrefixSize": f"0x{prefix_size:X}",
        "sourcePrefixOffset": f"0x{tail_offset:X}",
        "sourcePrefixEnd": f"0x{tail_offset + prefix_size:X}",
        "nonEmptyAssemblyRows": sum(
            1 for _index, start, count in referenced_rows if start >= 0 and count
        ),
        "maxReferencedRangeEnd": max_end,
        "examples": [
            {
                "oldAssemblyIndex": index,
                "newAssemblyIndex": old_to_new[index],
                "name": source_names[index],
                "start": start,
                "count": count,
            }
            for index, start, count in referenced_rows
            if start >= 0 and count
        ][:12],
    }
    return data, report


def recover_exported_type_definitions(
    source: bytes,
    metadata: bytes,
    *,
    tail_offset: int,
    exported_types_offset: int,
) -> tuple[bytes, dict[str, Any]]:
    sections = {
        name: read_section(source, off) for name, off in CUSTOM_SECTIONS.items()
    }
    source_names = parse_source_image_names(source)
    target_names = parse_standard_image_names(metadata)
    if sorted(source_names) != sorted(target_names):
        raise ValueError(
            "source/current image names differ; cannot recover exported type definitions"
        )

    image_ranges = sections["imageRanges"]
    exported_rows = []
    max_end = 0
    for old_index in range(image_ranges.size // 0x28):
        values = struct.unpack_from(
            "<10I", source, image_ranges.offset + old_index * 0x28
        )
        start = struct.unpack("<i", struct.pack("<I", values[4]))[0]
        count = values[5]
        if count:
            max_end = max(max_end, start + count)
            exported_rows.append(
                {
                    "oldImageIndex": old_index,
                    "newImageIndex": target_names.index(source_names[old_index]),
                    "name": source_names[old_index],
                    "start": start,
                    "count": count,
                }
            )

    if max_end == 0:
        return b"", {"exportedTypeDefinitionCount": 0, "examples": []}

    standard_sections = read_standard_sections(metadata)
    type_count = standard_sections["typeDefinitions"][1] // 0x58
    tail = source[tail_offset:]
    byte_count = max_end * 4
    if exported_types_offset < 0 or exported_types_offset + byte_count > len(tail):
        raise ValueError("exported type definition table offset is outside hidden tail")

    exported_values = list(
        struct.unpack_from("<" + "I" * max_end, tail, exported_types_offset)
    )
    bad = [value for value in exported_values if value >= type_count]
    if bad:
        raise ValueError(
            f"exported type definition table contains out-of-range type indices: {bad[:8]}"
        )

    data = b"".join(struct.pack("<I", value) for value in exported_values)
    report = {
        "exportedTypeDefinitionCount": len(values),
        "sourceTableOffset": f"0x{tail_offset + exported_types_offset:X}",
        "sourceTailOffset": f"0x{exported_types_offset:X}",
        "sourceTableEnd": f"0x{tail_offset + exported_types_offset + byte_count:X}",
        "nonEmptyImageRows": len(exported_rows),
        "maxExportedRangeEnd": max_end,
        "examples": exported_rows[:12],
        "firstValues": values[:16],
    }
    return data, report


def restore_image_custom_ranges(
    metadata: bytes, ranges_by_name: dict[str, tuple[int, int]]
) -> bytes:
    sections = read_standard_sections(metadata)
    string_off, string_size = sections["string"]
    _image_off, image_size = sections["images"]
    image_data = bytearray(section_bytes(metadata, sections["images"]))
    for index in range(image_size // 0x28):
        row_off = index * 0x28
        values = list(struct.unpack_from("<10I", image_data, row_off))
        name = read_metadata_string(
            metadata,
            Section(string_off, string_size),
            values[0],
            skip_leading_nuls=True,
        )
        if name not in ranges_by_name:
            raise ValueError(f"image not found in source custom ranges: {name}")
        values[8], values[9] = ranges_by_name[name]
        struct.pack_into("<10I", image_data, row_off, *values)
    return bytes(image_data)


def parse_method_declaring_types(metadata: bytes) -> list[int]:
    sections = read_standard_sections(metadata)
    method_off, method_size = sections["methods"]
    declaring: list[int] = []
    for index in range(method_size // 0x20):
        _name, declaring_type, *_rest = struct.unpack_from(
            "<IIIIIIHHHH", metadata, method_off + index * 0x20
        )
        declaring.append(declaring_type)
    return declaring


def parse_type_byval_indices(metadata: bytes) -> list[int]:
    sections = read_standard_sections(metadata)
    type_off, type_size = sections["typeDefinitions"]
    byval: list[int] = []
    for index in range(type_size // 0x58):
        byval.append(struct.unpack_from("<I", metadata, type_off + index * 0x58 + 8)[0])
    return byval


def restore_pre29_attribute_sections(
    source: bytes,
    metadata: bytes,
    binary: Path,
    metadata_registration_va: int = 0xA3D18A0,
    *,
    tail_offset: int = 0x01C9B1DC,
    blob_start: int = 0x870,
    exported_types_offset: int = 0x2177D0,
    relocated_elf: RelocatedElf | None = None,
) -> tuple[bytes, dict[str, Any]]:
    from .attribute_blob import BinaryTypes, MetadataTypeInfo, parse_attribute_blob

    ranges_by_name = parse_source_image_custom_ranges(source)
    target_count = sum(count for _start, count in ranges_by_name.values())
    tail = source[tail_offset:]
    metadata_types = MetadataTypeInfo(metadata)
    binary_types = BinaryTypes(
        relocated_elf or RelocatedElf(binary), metadata_registration_va
    )
    declaring_types = parse_method_declaring_types(metadata)
    byval_indices = parse_type_byval_indices(metadata)

    pos = blob_start
    blob_offsets: list[int] = []
    constructors_by_blob: list[list[int]] = []
    blob_examples: list[dict[str, Any]] = []
    totals = {"attributes": 0, "ctor_args": 0, "fields": 0, "props": 0}

    for index in range(target_count):
        blob_offsets.append(pos)
        next_pos, info = parse_attribute_blob(
            tail, pos, len(declaring_types), binary_types, metadata_types
        )
        constructors = list(info["constructors"])
        constructors_by_blob.append(constructors)
        if len(blob_examples) < 12:
            blob_examples.append(
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
        pos = next_pos

    blob_end = pos
    range_start = blob_end
    if tail[range_start : range_start + 2] == b"\xcc\xcc":
        range_start += 2
    else:
        range_start = (range_start + 3) & ~3

    range_rows = []
    for index in range(target_count + 1):
        token, start_offset = struct.unpack_from("<II", tail, range_start + index * 8)
        range_rows.append((token, start_offset))

    if range_rows[-1][1] != blob_end - blob_start:
        raise ValueError(
            f"sentinel offset mismatch: got 0x{range_rows[-1][1]:X}, expected 0x{blob_end - blob_start:X}"
        )

    attributes_info = bytearray()
    attribute_types = bytearray()
    attribute_type_cursor = 0
    for index, constructors in enumerate(constructors_by_blob):
        token, start_offset = range_rows[index]
        expected_start = blob_offsets[index] - blob_start
        if start_offset != expected_start:
            raise ValueError(
                f"range row {index} start mismatch: got 0x{start_offset:X}, expected 0x{expected_start:X}"
            )
        attributes_info += struct.pack(
            "<Iii", token, attribute_type_cursor, len(constructors)
        )
        for constructor in constructors:
            declaring_type = declaring_types[constructor]
            if declaring_type >= len(byval_indices):
                raise ValueError(
                    f"constructor {constructor} has invalid declaring type {declaring_type}"
                )
            attribute_types += struct.pack("<I", byval_indices[declaring_type])
        attribute_type_cursor += len(constructors)

    restored_images = restore_image_custom_ranges(metadata, ranges_by_name)
    referenced_assemblies, referenced_assemblies_report = recover_referenced_assemblies(
        source,
        metadata,
        tail_offset=tail_offset,
        blob_start=blob_start,
    )
    exported_type_definitions, exported_type_definitions_report = (
        recover_exported_type_definitions(
            source,
            metadata,
            tail_offset=tail_offset,
            exported_types_offset=exported_types_offset,
        )
    )
    restored = rebuild_metadata(
        metadata,
        {
            "images": restored_images,
            "referencedAssemblies": referenced_assemblies,
            "exportedTypeDefinitions": exported_type_definitions,
            "attributesInfo": bytes(attributes_info),
            "attributeTypes": bytes(attribute_types),
        },
    )
    report = {
        "source_sha256": sha256_hex(source),
        "base_metadata_sha256": sha256_hex(metadata),
        "output_sha256": sha256_hex(restored),
        "output_size": len(restored),
        "tail_offset": f"0x{tail_offset:X}",
        "blob_start": f"0x{blob_start:X}",
        "blob_end": f"0x{blob_end:X}",
        "range_start": f"0x{range_start:X}",
        "custom_attribute_targets": target_count,
        "attribute_constructor_count": attribute_type_cursor,
        "attributesInfo_size": len(attributes_info),
        "attributeTypes_size": len(attribute_types),
        "referencedAssemblies_size": len(referenced_assemblies),
        "referencedAssemblies": referenced_assemblies_report,
        "exportedTypeDefinitions_size": len(exported_type_definitions),
        "exportedTypeDefinitions": exported_type_definitions_report,
        "image_custom_total": target_count,
        "totals": totals,
        "examples": blob_examples,
        "sentinel": {
            "token": f"0x{range_rows[-1][0]:08X}",
            "startOffset": f"0x{range_rows[-1][1]:X}",
        },
    }
    return restored, report
