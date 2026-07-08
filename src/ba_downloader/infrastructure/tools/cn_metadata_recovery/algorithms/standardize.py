from __future__ import annotations

import struct
from collections.abc import Iterable

from .standard_metadata import (
    HEADER_V24_4 as STANDARD_HEADER_ORDER_V24_4,
)
from .standard_metadata import (
    HEADER_V27_2 as STANDARD_HEADER_ORDER_V27_2,
)
from .standard_metadata import (
    MAGIC as STANDARD_MAGIC,
)
from .standard_metadata import (
    Section,
    read_section,
    read_string,
    section_bytes,
    sha256_hex,
    u32,
)

CUSTOM_MAGIC = 0x12724394

HEADER_SIZE_STANDARD_V24_4 = 0x108
HEADER_SIZE_STANDARD_V27_2 = 0x100

CUSTOM_SECTIONS = {
    "stringLiteral": 0x08,
    "stringLiteralData": 0x10,
    "string": 0x18,
    "events": 0x20,
    "properties": 0x28,
    "methods": 0x30,
    "parameterDefaultValues": 0x38,
    "fieldDefaultValues": 0x40,
    "fieldAndParameterDefaultValueData": 0x48,
    "fieldMarshaledSizes": 0x50,
    "parameters": 0x58,
    "fields": 0x60,
    "genericParameters": 0x68,
    "genericParameterConstraints": 0x70,
    "genericContainers": 0x78,
    "nestedTypes": 0x80,
    "interfaces": 0x88,
    "vtableMethods": 0x90,
    "interfaceOffsets": 0x98,
    "typeDefinitions": 0xA0,
    "imageRanges": 0xA8,
    "assemblySummary": 0xB0,
    "trailingTypeSystemData": 0xB8,
}

TRAILING_TARGETS = {
    "drop",
    "metadataUsageLists",
    "metadataUsagePairs",
    "fieldRefs",
    "windowsRuntimeTypeNames",
    "exportedTypeDefinitions",
}


def iter_field_rows(buf: bytes, section: Section) -> Iterable[tuple[int, int, int]]:
    for idx in range(section.size // 0x0C):
        yield struct.unpack_from("<III", buf, section.offset + idx * 0x0C)


def infer_type_element_index(
    buf: bytes,
    strings: Section,
    fields: Section,
    first_field: int,
    field_count: int,
    bitfield: int,
) -> int:
    if (bitfield & 0x2) == 0:
        return 0xFFFFFFFF
    if first_field == 0xFFFFFFFF or field_count <= 0:
        return 0xFFFFFFFF
    off = fields.offset + first_field * 0x0C
    if off < fields.offset or off + 0x0C > fields.end:
        return 0xFFFFFFFF
    name_index, type_index, _token = struct.unpack_from("<III", buf, off)
    return (
        type_index if read_string(buf, strings, name_index) == "value__" else 0xFFFFFFFF
    )


def expand_methods(
    buf: bytes,
    section: Section,
    *,
    cpp2il_safe: bool = False,
    preserve_method_tokens: bool = False,
) -> bytes:
    out = bytearray()
    if section.size % 0x24:
        raise ValueError(
            f"method section size is not divisible by 0x24: 0x{section.size:x}"
        )

    for idx in range(section.size // 0x24):
        off = section.offset + idx * 0x24
        (
            name_index,
            declaring_type_idx,
            return_type_idx,
            _packed_a,
            parameter_start,
            generic_container_index,
            token,
            flags,
            iflags,
            slot,
            parameter_count,
        ) = struct.unpack_from("<IIIIIIIHHHH", buf, off)
        if cpp2il_safe and not preserve_method_tokens:
            token = 0x06000001
        out += struct.pack(
            "<IIIIIIHHHH",
            name_index,
            declaring_type_idx,
            return_type_idx,
            parameter_start,
            generic_container_index,
            token,
            flags,
            iflags,
            slot,
            parameter_count,
        )
    return bytes(out)


def expand_images(
    buf: bytes, section: Section, *, clear_custom_attribute_ranges: bool = False
) -> bytes:
    if not clear_custom_attribute_ranges:
        return section_bytes(buf, section)

    out = bytearray()
    if section.size % 0x28:
        raise ValueError(
            f"image section size is not divisible by 0x28: 0x{section.size:x}"
        )

    for idx in range(section.size // 0x28):
        values = list(struct.unpack_from("<10I", buf, section.offset + idx * 0x28))
        values[8] = 0
        values[9] = 0
        out += struct.pack("<10I", *values)

    return bytes(out)


def expand_type_definitions(
    buf: bytes,
    string_section: Section,
    type_section: Section,
    field_section: Section,
    target: str,
) -> bytes:
    out = bytearray()
    if type_section.size % 0x58:
        raise ValueError(
            f"type section size is not divisible by 0x58: 0x{type_section.size:x}"
        )

    for idx in range(type_section.size // 0x58):
        raw = struct.unpack_from("<22I", buf, type_section.offset + idx * 0x58)
        field_count = raw[17] & 0xFFFF
        element_type_index = infer_type_element_index(
            buf,
            string_section,
            field_section,
            raw[8],
            field_count,
            raw[20],
        )
        counts = (
            raw[16] & 0xFFFF,
            (raw[16] >> 16) & 0xFFFF,
            raw[17] & 0xFFFF,
            (raw[17] >> 16) & 0xFFFF,
            raw[18] & 0xFFFF,
            (raw[18] >> 16) & 0xFFFF,
            raw[19] & 0xFFFF,
            (raw[19] >> 16) & 0xFFFF,
        )

        if target == "24.4":
            values_24 = (
                raw[0],  # NameIndex
                raw[1],  # NamespaceIndex
                raw[2],  # ByvalTypeIndex
                raw[5],  # ByrefTypeIndex
                raw[3],  # DeclaringTypeIndex
                raw[4],  # ParentIndex
                element_type_index,
                raw[6],  # GenericContainerIndex
                raw[7],  # Flags
                raw[8],  # FirstFieldIdx
                raw[9],  # FirstMethodIdx
                raw[10],  # FirstEventId
                raw[11],  # FirstPropertyId
                raw[12],  # NestedTypesStart
                raw[13],  # InterfacesStart
                raw[14],  # VtableStart
                raw[15],  # InterfaceOffsetsStart
                *counts,
                raw[20],  # Bitfield
                raw[21],  # Token
            )
            out += struct.pack("<" + "I" * 17 + "H" * 8 + "I" * 2, *values_24)
        elif target == "27.2":
            values_27 = (
                raw[0],  # NameIndex
                raw[1],  # NamespaceIndex
                raw[2],  # ByvalTypeIndex
                raw[3],  # DeclaringTypeIndex
                raw[4],  # ParentIndex
                element_type_index,
                raw[6],  # GenericContainerIndex
                raw[7],  # Flags
                raw[8],  # FirstFieldIdx
                raw[9],  # FirstMethodIdx
                raw[10],  # FirstEventId
                raw[11],  # FirstPropertyId
                raw[12],  # NestedTypesStart
                raw[13],  # InterfacesStart
                raw[14],  # VtableStart
                raw[15],  # InterfaceOffsetsStart
                *counts,
                raw[20],  # Bitfield
                raw[21],  # Token
            )
            out += struct.pack("<" + "I" * 16 + "H" * 8 + "I" * 2, *values_27)
        else:
            raise ValueError(f"unsupported target: {target}")
    return bytes(out)


def target_config(target: str) -> tuple[int, int, list[str], int]:
    if target == "24.4":
        return 24, HEADER_SIZE_STANDARD_V24_4, STANDARD_HEADER_ORDER_V24_4, 0x5C
    if target == "27.2":
        return 27, HEADER_SIZE_STANDARD_V27_2, STANDARD_HEADER_ORDER_V27_2, 0x58
    raise ValueError(f"unsupported target: {target}")


def build_standard_candidate(
    buf: bytes,
    trailing_target: str,
    target: str,
    *,
    cpp2il_safe: bool = False,
    preserve_method_tokens: bool = False,
    recover_hidden_attribute_types: bool = False,
    clear_image_custom_ranges: bool = False,
) -> tuple[bytes, dict[str, object]]:
    if trailing_target not in TRAILING_TARGETS:
        raise ValueError(f"unsupported trailing target: {trailing_target}")
    declared_version, header_size, header_order, _type_size = target_config(target)

    custom_magic = u32(buf, 0)
    if custom_magic not in {CUSTOM_MAGIC, STANDARD_MAGIC}:
        raise ValueError(f"unexpected metadata magic 0x{custom_magic:08x}")

    sections = {name: read_section(buf, off) for name, off in CUSTOM_SECTIONS.items()}
    strings = sections["string"]
    fields = sections["fields"]

    transformed: dict[str, bytes] = {
        "methods": expand_methods(
            buf,
            sections["methods"],
            cpp2il_safe=cpp2il_safe,
            preserve_method_tokens=preserve_method_tokens,
        ),
        "typeDefinitions": expand_type_definitions(
            buf, strings, sections["typeDefinitions"], fields, target
        ),
        "images": expand_images(
            buf,
            sections["imageRanges"],
            clear_custom_attribute_ranges=cpp2il_safe or clear_image_custom_ranges,
        ),
        "assemblies": section_bytes(buf, sections["assemblySummary"]),
    }

    for name in header_order:
        if name in transformed:
            continue
        if name in CUSTOM_SECTIONS and name not in {
            "imageRanges",
            "assemblySummary",
            "trailingTypeSystemData",
        }:
            transformed[name] = section_bytes(buf, sections[name])
        else:
            transformed[name] = b""

    if trailing_target != "drop":
        transformed[trailing_target] = section_bytes(
            buf, sections["trailingTypeSystemData"]
        )

    hidden_tail_offset = max(section.end for section in sections.values())
    hidden_tail = buf[hidden_tail_offset:]
    if recover_hidden_attribute_types and hidden_tail:
        transformed["attributeTypes"] = hidden_tail

    if cpp2il_safe:
        transformed["parameterDefaultValues"] = b""
        transformed["fieldDefaultValues"] = b""
        transformed["fieldAndParameterDefaultValueData"] = b""
        transformed["attributesInfo"] = b""
        if not recover_hidden_attribute_types:
            transformed["attributeTypes"] = b""

    out = bytearray(header_size)
    struct.pack_into("<II", out, 0, STANDARD_MAGIC, declared_version)

    cursor = header_size
    emitted: dict[str, Section] = {}
    for index, name in enumerate(header_order):
        data = transformed[name]
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
        emitted[name] = Section(offset, len(data))
        struct.pack_into("<II", out, 0x08 + index * 8, offset, len(data))

    report = build_report(buf, sections, emitted, transformed, trailing_target, target)
    report["cpp2il_safe"] = cpp2il_safe
    report["preserve_method_tokens"] = preserve_method_tokens
    report["recover_hidden_attribute_types"] = recover_hidden_attribute_types
    report["clear_image_custom_ranges"] = cpp2il_safe or clear_image_custom_ranges
    report["hidden_tail"] = {
        "offset": f"0x{hidden_tail_offset:08X}",
        "size": f"0x{len(hidden_tail):08X}",
        "used_as_attributeTypes": bool(recover_hidden_attribute_types and hidden_tail),
    }
    if cpp2il_safe:
        report["safe_mode_changes"] = [
            (
                "method tokens are preserved for real code-registration exports"
                if preserve_method_tokens
                else "method tokens are normalized to 0x06000001 so synthetic zero method-pointer arrays can be size 1"
            ),
            "image customAttributeStart/customAttributeCount are cleared",
            "field/parameter default value sections are omitted to avoid unresolved default-value payloads",
            "custom attribute sections are omitted",
        ]
    return bytes(out), report


def standardize_custom_layout(
    restored_metadata: bytes,
) -> tuple[bytes, dict[str, object]]:
    standard_metadata, report = build_standard_candidate(
        restored_metadata,
        trailing_target="fieldRefs",
        target="27.2",
    )
    report["candidate_validation"] = validate_candidate(standard_metadata)
    return standard_metadata, report


def build_report(
    source: bytes,
    source_sections: dict[str, Section],
    emitted: dict[str, Section],
    transformed: dict[str, bytes],
    trailing_target: str,
    target: str,
) -> dict[str, object]:
    declared_version, _header_size, _header_order, type_size = target_config(target)
    method_count = source_sections["methods"].size // 0x24
    type_count = source_sections["typeDefinitions"].size // 0x58
    field_count = source_sections["fields"].size // 0x0C
    parameter_count = source_sections["parameters"].size // 0x0C
    image_count = source_sections["imageRanges"].size // 0x28
    assembly_count = source_sections["assemblySummary"].size // 0x40
    enum_element_inferred = count_enum_element_inferences(source, source_sections)

    return {
        "source_sha256": sha256_hex(source),
        "source_magic": f"0x{u32(source, 0):08X}",
        "declared_standard_magic": f"0x{STANDARD_MAGIC:08X}",
        "declared_standard_version": declared_version,
        "target": target,
        "intended_actual_version": (
            "24.4 when read with Unity >= 2020.1.11 in Cpp2IL"
            if target == "24.4"
            else "27.2 when read with Unity >= 2021.1 in Cpp2IL"
        ),
        "trailing_target": trailing_target,
        "counts": {
            "methods_custom": method_count,
            "methods_standard": len(transformed["methods"]) // 0x20,
            "typeDefinitions_custom": type_count,
            "typeDefinitions_standard": len(transformed["typeDefinitions"])
            // type_size,
            "fields": field_count,
            "parameters": parameter_count,
            "images": image_count,
            "assemblies": assembly_count,
            "enum_element_inferred": enum_element_inferred,
        },
        "row_sizes": {
            "methods": {
                "custom": "0x24",
                f"standard_v{target.replace('.', '_')}": "0x20",
            },
            "typeDefinitions": {
                "custom": "0x58",
                f"standard_v{target.replace('.', '_')}": f"0x{type_size:X}",
            },
            "fields": f"0x0C unchanged for {target}",
            "parameters": f"0x0C unchanged for {target}",
            "properties": f"0x14 unchanged for {target}",
            "events": f"0x18 unchanged for {target}",
            "images": f"0x28 unchanged for {target}",
            "assemblies": f"0x40 unchanged for {target}",
        },
        "emitted_sections": {
            name: {"offset": f"0x{section.offset:08X}", "size": f"0x{section.size:08X}"}
            for name, section in emitted.items()
        },
        "known_uncertainties": [
            "method compact packed_a is preserved only in the report, not represented in the 24.4 method row",
            "standard target has no metadata rgctxEntries header slot; RGCTX is resolved from the binary/codegen modules",
            "custom trailingTypeSystemData is shape-compatible with several 8-byte pair sections, so its destination is selectable",
        ],
    }


def count_enum_element_inferences(source: bytes, sections: dict[str, Section]) -> int:
    strings = sections["string"]
    fields = sections["fields"]
    types = sections["typeDefinitions"]
    total = 0
    for idx in range(types.size // 0x58):
        raw = struct.unpack_from("<22I", source, types.offset + idx * 0x58)
        if (raw[20] & 0x2) == 0:
            continue
        if (
            infer_type_element_index(
                source, strings, fields, raw[8], raw[17] & 0xFFFF, raw[20]
            )
            != 0xFFFFFFFF
        ):
            total += 1
    return total


def validate_candidate(buf: bytes) -> dict[str, object]:
    if u32(buf, 0) != STANDARD_MAGIC:
        raise ValueError("candidate does not have standard metadata magic")
    declared_version = u32(buf, 4)
    if declared_version == 24:
        target = "24.4"
    elif declared_version == 27:
        target = "27.2"
    else:
        raise ValueError(
            f"candidate declares unsupported metadata version {declared_version}"
        )
    _declared_version, _header_size, header_order, type_size = target_config(target)

    sections = {}
    for index, name in enumerate(header_order):
        section = read_section(buf, 0x08 + index * 8)
        if section.size and section.end > len(buf):
            raise ValueError(f"section {name} out of range")
        sections[name] = section

    checks = {
        "methods_div_0x20": sections["methods"].size % 0x20 == 0,
        f"typeDefinitions_div_0x{type_size:x}": sections["typeDefinitions"].size
        % type_size
        == 0,
        "images_div_0x28": sections["images"].size % 0x28 == 0,
        "assemblies_div_0x40": sections["assemblies"].size % 0x40 == 0,
        "fields_div_0x0c": sections["fields"].size % 0x0C == 0,
        "parameters_div_0x0c": sections["parameters"].size % 0x0C == 0,
        "properties_div_0x14": sections["properties"].size % 0x14 == 0,
        "events_div_0x18": sections["events"].size % 0x18 == 0,
    }
    return {
        "sha256": sha256_hex(buf),
        "size": len(buf),
        "declared_version": declared_version,
        "target": target,
        "checks": checks,
        "counts": {
            "methods": sections["methods"].size // 0x20,
            "typeDefinitions": sections["typeDefinitions"].size // type_size,
            "images": sections["images"].size // 0x28,
            "assemblies": sections["assemblies"].size // 0x40,
        },
    }
