from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from .codegen_registration import RelocatedElf
from .default_values import BinaryTypeTable
from .standard_metadata import (
    ROW_SIZES,
    Section,
    i32,
    read_i32,
    section_count,
    section_map,
    sha256_hex,
    valid_index,
    valid_range,
    valid_string_index,
)
from .validator_defaults import validate_defaults, validate_misc_index_sections


@dataclass
class IssueSink:
    max_examples: int
    errors: Counter[str]
    warnings: Counter[str]
    examples: dict[str, list[dict[str, Any]]]

    @classmethod
    def create(cls, max_examples: int) -> IssueSink:
        return cls(max_examples, Counter(), Counter(), {})

    def error(self, kind: str, **detail: Any) -> None:
        self.errors[kind] += 1
        self._example(f"error:{kind}", detail)

    def warning(self, kind: str, **detail: Any) -> None:
        self.warnings[kind] += 1
        self._example(f"warning:{kind}", detail)

    def _example(self, key: str, detail: dict[str, Any]) -> None:
        bucket = self.examples.setdefault(key, [])
        if len(bucket) < self.max_examples:
            bucket.append(detail)


def validate_standard_metadata(
    metadata: bytes,
    max_examples: int = 8,
    *,
    binary: Path | None = None,
    metadata_registration_va: int = 0xA3D18A0,
) -> dict[str, Any]:
    target, sections = section_map(metadata)

    issues = IssueSink.create(max_examples)
    header_size = 0x100

    for name, section in sections.items():
        if section.size == 0:
            continue
        if section.offset < header_size:
            issues.error(
                "section_starts_inside_header",
                section=name,
                offset=f"0x{section.offset:X}",
            )
        if section.end > len(metadata):
            issues.error(
                "section_out_of_file",
                section=name,
                end=f"0x{section.end:X}",
                fileSize=len(metadata),
            )
        if section.offset & 3:
            issues.warning(
                "section_offset_unaligned", section=name, offset=f"0x{section.offset:X}"
            )
        row_size = ROW_SIZES.get(name)
        if row_size and section.size % row_size:
            issues.error(
                "section_size_not_divisible",
                section=name,
                size=section.size,
                rowSize=row_size,
            )

    live_sections = sorted(
        (
            (section.offset, section.end, name)
            for name, section in sections.items()
            if section.size
        ),
        key=lambda item: item[0],
    )
    for (_start_a, end_a, name_a), (start_b, _end_b, name_b) in pairwise(live_sections):
        if end_a > start_b:
            issues.error(
                "section_overlap",
                previous=name_a,
                next=name_b,
                previousEnd=f"0x{end_a:X}",
                nextStart=f"0x{start_b:X}",
            )

    string_size = sections["string"].size
    counts = {
        "events": section_count(sections, "events", 0x18),
        "properties": section_count(sections, "properties", 0x14),
        "methods": section_count(sections, "methods", 0x20),
        "parameterDefaultValues": section_count(
            sections, "parameterDefaultValues", 0x0C
        ),
        "fieldDefaultValues": section_count(sections, "fieldDefaultValues", 0x0C),
        "parameters": section_count(sections, "parameters", 0x0C),
        "fields": section_count(sections, "fields", 0x0C),
        "genericParameters": section_count(sections, "genericParameters", 0x10),
        "genericParameterConstraints": section_count(
            sections, "genericParameterConstraints", 4
        ),
        "genericContainers": section_count(sections, "genericContainers", 0x10),
        "nestedTypes": section_count(sections, "nestedTypes", 4),
        "interfaces": section_count(sections, "interfaces", 4),
        "vtableMethods": section_count(sections, "vtableMethods", 4),
        "interfaceOffsets": section_count(sections, "interfaceOffsets", 8),
        "typeDefinitions": section_count(sections, "typeDefinitions", 0x58),
        "images": section_count(sections, "images", 0x28),
        "assemblies": section_count(sections, "assemblies", 0x40),
        "fieldRefs": section_count(sections, "fieldRefs", 8),
        "referencedAssemblies": section_count(sections, "referencedAssemblies", 4),
        "attributesInfo": section_count(sections, "attributesInfo", 0x0C),
        "attributeTypes": section_count(sections, "attributeTypes", 4),
        "attributeDataRange": section_count(sections, "attributeDataRange", 8),
        "exportedTypeDefinitions": section_count(
            sections, "exportedTypeDefinitions", 4
        ),
    }

    validate_type_definitions(metadata, sections, counts, string_size, issues)
    validate_methods(metadata, sections, counts, string_size, issues)
    validate_fields(metadata, sections, counts, string_size, issues)
    validate_parameters(metadata, sections, counts, string_size, issues)
    validate_properties(metadata, sections, counts, string_size, issues)
    validate_events(metadata, sections, counts, string_size, issues)
    validate_images(metadata, sections, counts, string_size, issues)
    validate_assemblies(metadata, sections, counts, string_size, issues)
    validate_generic_tables(metadata, sections, counts, string_size, issues)
    if target == "29":
        validate_v29_attributes(metadata, sections, counts, issues)
    else:
        validate_pre29_attributes(metadata, sections, counts, issues)
    default_type_table = None
    if binary is not None:
        default_type_table = BinaryTypeTable(
            RelocatedElf(binary), metadata_registration_va
        )
    validate_defaults(
        metadata, sections, counts, issues, target=target, type_table=default_type_table
    )
    validate_misc_index_sections(metadata, sections, counts, issues)

    return {
        "metadata": "<memory>",
        "sha256": sha256_hex(metadata),
        "size": len(metadata),
        "target": target,
        "counts": counts,
        "sectionExtents": {
            name: {
                "offset": f"0x{section.offset:X}",
                "size": section.size,
                "end": f"0x{section.end:X}",
            }
            for name, section in sections.items()
        },
        "summary": {
            "errorCount": sum(issues.errors.values()),
            "warningCount": sum(issues.warnings.values()),
            "errorKinds": dict(issues.errors.most_common()),
            "warningKinds": dict(issues.warnings.most_common()),
            "valid": not issues.errors,
        },
        "examples": issues.examples,
    }


def validate_type_definitions(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    sec = sections["typeDefinitions"]
    for index in range(counts["typeDefinitions"]):
        off = sec.offset + index * 0x58
        values = struct.unpack_from("<16I8H2I", metadata, off)
        (
            name,
            namespace,
            _byval,
            _declaring,
            _parent,
            _element,
            generic_container,
            _flags,
        ) = values[:8]
        first_field, first_method, first_event, first_property = values[8:12]
        nested_start, interfaces_start, vtable_start, interface_offsets_start = values[
            12:16
        ]
        (
            method_count,
            property_count,
            field_count,
            event_count,
            nested_count,
            vtable_count,
            interfaces_count,
            interface_offsets_count,
        ) = values[16:24]

        if not valid_string_index(i32(name), string_size):
            issues.error("type_name_string_oob", row=index, value=i32(name))
        if not valid_string_index(i32(namespace), string_size, allow_empty=True):
            issues.error("type_namespace_string_oob", row=index, value=i32(namespace))
        # byval/declaring/parent/element are Il2CppType indices from the binary-side type
        # table, not TypeDefinition indices from the metadata file.
        for field_name, value, total in (
            ("genericContainer", i32(generic_container), counts["genericContainers"]),
        ):
            if total is not None and not valid_index(value, total):
                issues.error(
                    "type_index_oob",
                    row=index,
                    field=field_name,
                    value=value,
                    total=total,
                )

        if not valid_range(i32(first_field), field_count, counts["fields"]):
            issues.error(
                "type_field_range_oob",
                row=index,
                start=i32(first_field),
                count=field_count,
            )
        if not valid_range(i32(first_method), method_count, counts["methods"]):
            issues.error(
                "type_method_range_oob",
                row=index,
                start=i32(first_method),
                count=method_count,
            )
        if not valid_range(i32(first_event), event_count, counts["events"]):
            issues.error(
                "type_event_range_oob",
                row=index,
                start=i32(first_event),
                count=event_count,
            )
        if not valid_range(i32(first_property), property_count, counts["properties"]):
            issues.error(
                "type_property_range_oob",
                row=index,
                start=i32(first_property),
                count=property_count,
            )
        if not valid_range(i32(nested_start), nested_count, counts["nestedTypes"]):
            issues.error(
                "type_nested_range_oob",
                row=index,
                start=i32(nested_start),
                count=nested_count,
            )
        if not valid_range(
            i32(interfaces_start), interfaces_count, counts["interfaces"]
        ):
            issues.error(
                "type_interfaces_range_oob",
                row=index,
                start=i32(interfaces_start),
                count=interfaces_count,
            )
        if not valid_range(i32(vtable_start), vtable_count, counts["vtableMethods"]):
            issues.error(
                "type_vtable_range_oob",
                row=index,
                start=i32(vtable_start),
                count=vtable_count,
            )
        if not valid_range(
            i32(interface_offsets_start),
            interface_offsets_count,
            counts["interfaceOffsets"],
        ):
            issues.error(
                "type_interface_offsets_range_oob",
                row=index,
                start=i32(interface_offsets_start),
                count=interface_offsets_count,
            )


def validate_methods(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    sec = sections["methods"]
    for index in range(counts["methods"]):
        off = sec.offset + index * 0x20
        name, declaring, ret, parameter_start, generic_container, _token = (
            struct.unpack_from("<6I", metadata, off)
        )
        param_count = struct.unpack_from("<H", metadata, off + 0x1E)[0]
        if not valid_string_index(i32(name), string_size):
            issues.error("method_name_string_oob", row=index, value=i32(name))
        if not valid_index(
            i32(declaring), counts["typeDefinitions"], allow_minus_one=False
        ):
            issues.error("method_declaring_type_oob", row=index, value=i32(declaring))
        if i32(ret) < 0:
            issues.error("method_return_type_negative", row=index, value=i32(ret))
        if not valid_index(i32(generic_container), counts["genericContainers"]):
            issues.error(
                "method_generic_container_oob", row=index, value=i32(generic_container)
            )
        if not valid_range(i32(parameter_start), param_count, counts["parameters"]):
            issues.error(
                "method_parameter_range_oob",
                row=index,
                start=i32(parameter_start),
                count=param_count,
            )


def validate_fields(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    sec = sections["fields"]
    for index in range(counts["fields"]):
        name, type_index, _token = struct.unpack_from(
            "<III", metadata, sec.offset + index * 0x0C
        )
        if not valid_string_index(i32(name), string_size):
            issues.error("field_name_string_oob", row=index, value=i32(name))
        if i32(type_index) < 0:
            issues.error("field_type_negative", row=index, value=i32(type_index))


def validate_parameters(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    sec = sections["parameters"]
    for index in range(counts["parameters"]):
        name, _token, type_index = struct.unpack_from(
            "<III", metadata, sec.offset + index * 0x0C
        )
        if not valid_string_index(i32(name), string_size, allow_empty=True):
            issues.error("parameter_name_string_oob", row=index, value=i32(name))
        if i32(type_index) < 0:
            issues.error("parameter_type_negative", row=index, value=i32(type_index))


def validate_properties(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    sec = sections["properties"]
    for index in range(counts["properties"]):
        name, get_method, set_method, attrs, token = struct.unpack_from(
            "<IIIII", metadata, sec.offset + index * 0x14
        )
        _ = attrs, token
        if not valid_string_index(i32(name), string_size):
            issues.error("property_name_string_oob", row=index, value=i32(name))
        if not valid_index(i32(get_method), counts["methods"]):
            issues.error("property_get_method_oob", row=index, value=i32(get_method))
        if not valid_index(i32(set_method), counts["methods"]):
            issues.error("property_set_method_oob", row=index, value=i32(set_method))


def validate_events(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    sec = sections["events"]
    for index in range(counts["events"]):
        name, type_index, add, remove, raise_method, token = struct.unpack_from(
            "<IIIIII", metadata, sec.offset + index * 0x18
        )
        _ = token
        if not valid_string_index(i32(name), string_size):
            issues.error("event_name_string_oob", row=index, value=i32(name))
        if i32(type_index) < 0:
            issues.error("event_type_negative", row=index, value=i32(type_index))
        for field_name, value in (
            ("add", i32(add)),
            ("remove", i32(remove)),
            ("raise", i32(raise_method)),
        ):
            if not valid_index(value, counts["methods"]):
                issues.error(
                    "event_method_oob", row=index, field=field_name, value=value
                )


def validate_images(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    sec = sections["images"]
    for index in range(counts["images"]):
        values = struct.unpack_from("<10I", metadata, sec.offset + index * 0x28)
        (
            name,
            assembly,
            first_type,
            type_count,
            exported_start,
            exported_count,
            entry,
        ) = values[:7]
        custom_start, custom_count = values[8:10]
        if not valid_string_index(i32(name), string_size):
            issues.error("image_name_string_oob", row=index, value=i32(name))
        if not valid_index(i32(assembly), counts["assemblies"], allow_minus_one=False):
            issues.error("image_assembly_oob", row=index, value=i32(assembly))
        if not valid_range(i32(first_type), type_count, counts["typeDefinitions"]):
            issues.error(
                "image_type_range_oob",
                row=index,
                start=i32(first_type),
                count=type_count,
            )
        if not valid_range(
            i32(exported_start),
            exported_count,
            counts.get("exportedTypeDefinitions", 0),
        ):
            issues.warning(
                "image_exported_type_range_oob",
                row=index,
                start=i32(exported_start),
                count=exported_count,
            )
        if not valid_index(i32(entry), counts["methods"]):
            issues.error("image_entry_method_oob", row=index, value=i32(entry))
        attribute_range_total = counts["attributesInfo"] or counts["attributeDataRange"]
        if not valid_range(i32(custom_start), custom_count, attribute_range_total):
            issues.error(
                "image_custom_attribute_range_oob",
                row=index,
                start=i32(custom_start),
                count=custom_count,
            )


def validate_assemblies(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    sec = sections["assemblies"]
    for index in range(counts["assemblies"]):
        values = struct.unpack_from("<16I", metadata, sec.offset + index * 0x40)
        (
            image_index,
            _token,
            referenced_start,
            referenced_count,
            aname_name,
            aname_culture,
            aname_public_key,
        ) = values[:7]
        if not valid_index(i32(image_index), counts["images"], allow_minus_one=False):
            issues.error("assembly_image_oob", row=index, value=i32(image_index))
        if not valid_range(
            i32(referenced_start), referenced_count, counts["referencedAssemblies"]
        ):
            issues.error(
                "assembly_referenced_range_oob",
                row=index,
                start=i32(referenced_start),
                count=referenced_count,
            )
        for field_name, value, allow_empty in (
            ("name", i32(aname_name), False),
            ("culture", i32(aname_culture), True),
            ("publicKey", i32(aname_public_key), True),
        ):
            if not valid_string_index(value, string_size, allow_empty=allow_empty):
                issues.error(
                    "assembly_string_oob", row=index, field=field_name, value=value
                )


def validate_generic_tables(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    string_size: int,
    issues: IssueSink,
) -> None:
    gen_sec = sections["genericParameters"]
    for index in range(counts["genericParameters"]):
        off = gen_sec.offset + index * 0x10
        owner, name, constraints_start, constraints_count, _num, _flags = (
            struct.unpack_from("<IIhhHH", metadata, off)
        )
        if i32(owner) < 0:
            issues.error(
                "generic_parameter_owner_negative", row=index, value=i32(owner)
            )
        if not valid_string_index(i32(name), string_size):
            issues.error(
                "generic_parameter_name_string_oob", row=index, value=i32(name)
            )
        if not valid_range(
            constraints_start, constraints_count, counts["genericParameterConstraints"]
        ):
            issues.error(
                "generic_parameter_constraint_range_oob",
                row=index,
                start=constraints_start,
                count=constraints_count,
            )

    cont_sec = sections["genericContainers"]
    for index in range(counts["genericContainers"]):
        owner, argc, is_method, start = struct.unpack_from(
            "<IIII", metadata, cont_sec.offset + index * 0x10
        )
        owner_index = i32(owner)
        if is_method not in (0, 1):
            issues.error(
                "generic_container_is_method_invalid", row=index, value=is_method
            )
        elif is_method and not valid_index(
            owner_index, counts["methods"], allow_minus_one=False
        ):
            issues.error(
                "generic_container_method_owner_oob", row=index, value=owner_index
            )
        elif not is_method and not valid_index(
            owner_index, counts["typeDefinitions"], allow_minus_one=False
        ):
            issues.error(
                "generic_container_type_owner_oob", row=index, value=owner_index
            )
        if not valid_range(i32(start), argc, counts["genericParameters"]):
            issues.error(
                "generic_container_parameter_range_oob",
                row=index,
                start=i32(start),
                count=argc,
            )


def validate_pre29_attributes(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    issues: IssueSink,
) -> None:
    info_sec = sections["attributesInfo"]
    for index in range(counts["attributesInfo"]):
        _token, start, count = struct.unpack_from(
            "<III", metadata, info_sec.offset + index * 0x0C
        )
        if not valid_range(i32(start), count, counts["attributeTypes"]):
            issues.error(
                "attribute_type_range_oob", row=index, start=i32(start), count=count
            )

    type_sec = sections["attributeTypes"]
    for index in range(counts["attributeTypes"]):
        type_index = read_i32(metadata, type_sec.offset + index * 4)
        if type_index < 0:
            issues.error("attribute_type_negative", row=index, value=type_index)


def validate_v29_attributes(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    issues: IssueSink,
) -> None:
    data_size = sections["attributeData"].size
    range_sec = sections["attributeDataRange"]
    previous_offset = -1
    for index in range(counts["attributeDataRange"]):
        token, start_offset = struct.unpack_from(
            "<II", metadata, range_sec.offset + index * 8
        )
        if start_offset > data_size:
            issues.error(
                "attribute_data_range_offset_oob",
                row=index,
                token=f"0x{token:08X}",
                offset=start_offset,
            )
        if start_offset < previous_offset:
            issues.error(
                "attribute_data_range_offset_not_monotonic",
                row=index,
                previous=previous_offset,
                current=start_offset,
            )
        previous_offset = start_offset

    images = sections["images"]
    for image_index in range(counts["images"]):
        values = struct.unpack_from(
            "<10I", metadata, images.offset + image_index * 0x28
        )
        start = struct.unpack("<i", struct.pack("<I", values[8]))[0]
        count = values[9]
        if start < 0 or count <= 1:
            continue
        previous_token = -1
        for row in range(start, start + count):
            token = struct.unpack_from("<I", metadata, range_sec.offset + row * 8)[0]
            if token < previous_token:
                issues.warning(
                    "attribute_data_range_image_tokens_not_sorted",
                    image=image_index,
                    row=row,
                    previous=f"0x{previous_token:08X}",
                    current=f"0x{token:08X}",
                )
                break
            previous_token = token
