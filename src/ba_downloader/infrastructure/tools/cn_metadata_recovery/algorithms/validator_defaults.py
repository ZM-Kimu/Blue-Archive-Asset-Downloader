from __future__ import annotations

import struct
from typing import Any, Protocol

from .default_values import (
    FIXED_DEFAULT_SIZES,
    IL2CPP_TYPE_I4,
    IL2CPP_TYPE_STRING,
    IL2CPP_TYPE_U4,
    IL2CPP_TYPE_VALUETYPE,
    BinaryTypeTable,
    MetadataNames,
    read_unity_compressed_int,
    read_unity_compressed_uint,
    static_array_initializer_size,
)
from .standard_metadata import ROW_SIZES, Section, i32, read_i32, valid_index


class IssueReporter(Protocol):
    def error(self, kind: str, **detail: Any) -> None: ...


def validate_defaults(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    issues: IssueReporter,
    *,
    target: str,
    type_table: BinaryTypeTable | None,
) -> None:
    data_size = sections["fieldAndParameterDefaultValueData"].size
    tuple_sections = {
        name: (section.offset, section.size) for name, section in sections.items()
    }
    names = MetadataNames(metadata, tuple_sections) if type_table is not None else None
    for name, owner_total in (
        ("parameterDefaultValues", counts["parameters"]),
        ("fieldDefaultValues", counts["fields"]),
    ):
        sec = sections[name]
        for index in range(counts[name]):
            owner, type_index, data_index = struct.unpack_from(
                "<III", metadata, sec.offset + index * 0x0C
            )
            if not valid_index(i32(owner), owner_total, allow_minus_one=False):
                issues.error(
                    "default_owner_oob",
                    section=name,
                    row=index,
                    value=i32(owner),
                    total=owner_total,
                )
            if i32(type_index) < 0:
                issues.error(
                    "default_type_negative",
                    section=name,
                    row=index,
                    value=i32(type_index),
                )
            if data_index != 0xFFFFFFFF and not (0 <= data_index < data_size):
                issues.error(
                    "default_data_index_oob",
                    section=name,
                    row=index,
                    value=data_index,
                    dataSize=data_size,
                )
            elif type_table is not None and data_index != 0xFFFFFFFF:
                type_record = type_table.type_record(i32(type_index))
                default_type_record = (
                    type_record if isinstance(type_record, dict) else None
                )
                type_enum = (
                    None
                    if default_type_record is None
                    else default_type_record["type_enum"]
                )
                if not default_payload_shape_is_valid(
                    metadata,
                    sections,
                    names,
                    target,
                    type_enum,
                    default_type_record,
                    data_index,
                ):
                    issues.error(
                        "default_payload_invalid_for_version",
                        section=name,
                        row=index,
                        typeIndex=i32(type_index),
                        typeEnum=type_enum,
                        dataIndex=data_index,
                        target=target,
                    )


def default_payload_shape_is_valid(
    metadata: bytes,
    sections: dict[str, Section],
    names: MetadataNames | None,
    target: str,
    type_enum: int | None,
    type_record: dict[str, int] | None,
    data_index: int,
) -> bool:
    data_section = sections["fieldAndParameterDefaultValueData"]
    if type_enum is None or data_index < 0 or data_index >= data_section.size:
        return False
    absolute = data_section.offset + data_index
    limit = data_section.offset + data_section.size

    if target == "29":
        if type_enum == IL2CPP_TYPE_I4:
            return read_unity_compressed_int(metadata, absolute, limit) is not None
        if type_enum == IL2CPP_TYPE_U4:
            return read_unity_compressed_uint(metadata, absolute, limit) is not None
        if type_enum == IL2CPP_TYPE_STRING:
            result = read_unity_compressed_int(metadata, absolute, limit)
            if result is None:
                return False
            length, length_size = result
            return 0 <= length <= 64 * 1024 and absolute + length_size + length <= limit

    if type_enum == IL2CPP_TYPE_STRING:
        if absolute + 4 > limit:
            return False
        length = struct.unpack_from("<i", metadata, absolute)[0]
        return 0 <= length <= 64 * 1024 and absolute + 4 + length <= limit
    if type_enum in FIXED_DEFAULT_SIZES:
        return absolute + FIXED_DEFAULT_SIZES[type_enum] <= limit
    if (
        type_enum == IL2CPP_TYPE_VALUETYPE
        and names is not None
        and type_record is not None
    ):
        type_name = names.type_definition_name(type_record["datapoint"])
        static_size = static_array_initializer_size(type_name)
        return static_size is None or absolute + static_size <= limit
    return True


def validate_misc_index_sections(
    metadata: bytes,
    sections: dict[str, Section],
    counts: dict[str, int],
    issues: IssueReporter,
) -> None:
    for name, total in (
        ("nestedTypes", counts["typeDefinitions"]),
        ("referencedAssemblies", counts["assemblies"]),
    ):
        sec = sections[name]
        row_size = ROW_SIZES[name]
        for index in range(counts[name]):
            value = read_i32(metadata, sec.offset + index * row_size)
            if not valid_index(value, total, allow_minus_one=False):
                issues.error(
                    "index_section_oob",
                    section=name,
                    row=index,
                    value=value,
                    total=total,
                )

    sec = sections["fieldRefs"]
    for index in range(counts["fieldRefs"]):
        type_index, field_index = struct.unpack_from(
            "<II", metadata, sec.offset + index * 8
        )
        if i32(type_index) < 0:
            issues.error("field_ref_type_negative", row=index, value=i32(type_index))
        if i32(field_index) < 0:
            issues.error("field_ref_field_negative", row=index, value=i32(field_index))
