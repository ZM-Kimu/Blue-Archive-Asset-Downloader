from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .attribute_blob import BinaryTypes, MetadataTypeInfo, parse_attribute_blob
from .codegen_registration import RelocatedElf
from .standard_metadata import Section, i32, section_map
from .standardize import CUSTOM_SECTIONS

CN_ATTRIBUTE_BLOB_START = 0x870
_MAX_METADATA_REGISTRATION_COUNT = 1_000_000
_MIN_METADATA_REGISTRATION_SCORE = 80
_AMBIGUOUS_METADATA_REGISTRATION_SCORE_DELTA = 10

_IL2CPP_TYPE_ENUMS = {
    0x01,
    0x02,
    0x03,
    0x04,
    0x05,
    0x06,
    0x07,
    0x08,
    0x09,
    0x0A,
    0x0B,
    0x0C,
    0x0D,
    0x0E,
    0x0F,
    0x10,
    0x11,
    0x12,
    0x13,
    0x14,
    0x15,
    0x16,
    0x17,
    0x18,
    0x19,
    0x1B,
    0x1C,
    0x1D,
    0x1E,
    0x1F,
    0x20,
    0x21,
    0x55,
}


class RelocatedElfLike(Protocol):
    @property
    def data(self) -> bytearray: ...

    @property
    def loads(self) -> Sequence[Any]: ...

    def va_to_offset(self, va: int) -> int | None: ...

    def offset_to_va(self, offset: int) -> int | None: ...

    def read_u64_offset(self, offset: int) -> int: ...


@dataclass(frozen=True, slots=True)
class CnMetadataRecoveryParameters:
    tail_offset: int
    metadata_registration_va: int
    exported_types_offset: int
    blob_start: int = CN_ATTRIBUTE_BLOB_START

    def describe(self) -> str:
        return (
            f"tail_offset=0x{self.tail_offset:X}, "
            f"blob_start=0x{self.blob_start:X}, "
            f"metadata_registration_va=0x{self.metadata_registration_va:X}, "
            f"exported_types_offset=0x{self.exported_types_offset:X}"
        )


@dataclass(frozen=True, slots=True)
class _MetadataRegistrationCandidate:
    score: int
    va: int
    type_count: int
    mapped_samples: int
    plausible_samples: int
    typedef_samples: int
    mapped_pointer_pairs: int

    def describe(self) -> str:
        return (
            f"va=0x{self.va:X} score={self.score} "
            f"type_count={self.type_count} mapped_samples={self.mapped_samples} "
            f"plausible_samples={self.plausible_samples} "
            f"typedef_samples={self.typedef_samples} "
            f"mapped_pointer_pairs={self.mapped_pointer_pairs}"
        )


def _read_custom_section(metadata: bytes, header_offset: int) -> Section:
    section_offset, section_size = struct.unpack_from("<II", metadata, header_offset)
    section = Section(section_offset, section_size)
    if section.offset < 0 or section.size < 0 or section.end > len(metadata):
        raise ValueError(
            f"custom metadata section out of range at 0x{header_offset:X}: "
            f"offset=0x{section.offset:X} size=0x{section.size:X}"
        )
    return section


def _source_image_ranges(metadata: bytes) -> Section:
    return _read_custom_section(metadata, CUSTOM_SECTIONS["imageRanges"])


def resolve_hidden_tail_offset(restored_metadata: bytes) -> int:
    sections = [
        _read_custom_section(restored_metadata, header_offset)
        for header_offset in CUSTOM_SECTIONS.values()
    ]
    tail_offset = max(section.end for section in sections)
    if tail_offset <= 0 or tail_offset > len(restored_metadata):
        raise ValueError(f"invalid CN metadata hidden tail offset: 0x{tail_offset:X}")
    return tail_offset


def resolve_exported_type_definitions_offset(
    restored_metadata: bytes,
    tail_offset: int,
) -> int:
    if tail_offset < 0 or tail_offset > len(restored_metadata):
        raise ValueError(f"hidden tail offset is outside metadata: 0x{tail_offset:X}")

    image_ranges = _source_image_ranges(restored_metadata)
    max_end = 0
    for index in range(image_ranges.size // 0x28):
        row_offset = image_ranges.offset + index * 0x28
        values = struct.unpack_from("<10I", restored_metadata, row_offset)
        start = i32(values[4])
        count = values[5]
        if count:
            if start < 0:
                raise ValueError(
                    f"image {index} exported type range has negative start: {start}"
                )
            max_end = max(max_end, start + count)

    if max_end == 0:
        return 0

    table_size = max_end * 4
    tail_size = len(restored_metadata) - tail_offset
    if table_size > tail_size:
        raise ValueError(
            f"exported type definition table is larger than hidden tail: "
            f"table=0x{table_size:X} tail=0x{tail_size:X}"
        )
    return tail_size - table_size


def resolve_attribute_blob_start(restored_metadata: bytes, tail_offset: int) -> int:
    if tail_offset < 0 or tail_offset > len(restored_metadata):
        raise ValueError(f"hidden tail offset is outside metadata: 0x{tail_offset:X}")

    assembly_summary = _read_custom_section(
        restored_metadata,
        CUSTOM_SECTIONS["assemblySummary"],
    )
    max_end = 0
    for index in range(assembly_summary.size // 0x40):
        row_offset = assembly_summary.offset + index * 0x40
        values = struct.unpack_from("<16I", restored_metadata, row_offset)
        start = i32(values[2])
        count = values[3]
        if count:
            if start < 0:
                raise ValueError(
                    f"assembly {index} referenced assembly range has negative start: {start}"
                )
            max_end = max(max_end, start + count)

    blob_start = max_end * 4
    tail_size = len(restored_metadata) - tail_offset
    if blob_start >= tail_size:
        raise ValueError(
            f"resolved CN attribute blob start is outside hidden tail: "
            f"blob_start=0x{blob_start:X} tail_size=0x{tail_size:X}"
        )
    return blob_start


def _sample_type_indices(type_count: int, type_definition_count: int) -> list[int]:
    return sorted(
        {
            index
            for index in (
                0,
                1,
                2,
                3,
                4,
                5,
                10,
                25,
                50,
                100,
                200,
                500,
                1_000,
                2_000,
                5_000,
                10_000,
                20_000,
                min(type_count - 1, type_definition_count - 1),
                type_count - 1,
            )
            if 0 <= index < type_count
        }
    )


def _mapped_pointer_pairs(elf: RelocatedElfLike, values: tuple[int, ...]) -> int:
    pairs = 0
    for count_index, pointer_index in (
        (0, 1),
        (2, 3),
        (4, 5),
        (6, 7),
        (8, 9),
        (10, 11),
        (12, 13),
    ):
        count = values[count_index]
        pointer = values[pointer_index]
        if (count == 0 and pointer == 0) or (
            0 < count < _MAX_METADATA_REGISTRATION_COUNT
            and elf.va_to_offset(pointer) is not None
        ):
            pairs += 1
    return pairs


def _score_metadata_registration_candidate(
    elf: RelocatedElfLike,
    offset: int,
    type_definition_count: int,
) -> _MetadataRegistrationCandidate | None:
    values = struct.unpack_from("<16Q", elf.data, offset)
    type_count = values[6]
    if not (type_definition_count <= type_count <= _MAX_METADATA_REGISTRATION_COUNT):
        return None

    type_ptrs_offset = elf.va_to_offset(values[7])
    if type_ptrs_offset is None or type_ptrs_offset + min(type_count, 256) * 8 > len(
        elf.data
    ):
        return None

    mapped_samples = 0
    plausible_samples = 0
    typedef_samples = 0
    for type_index in _sample_type_indices(type_count, type_definition_count):
        type_pointer_offset = type_ptrs_offset + type_index * 8
        if type_pointer_offset + 8 > len(elf.data):
            continue
        type_pointer = struct.unpack_from(
            "<Q",
            elf.data,
            type_pointer_offset,
        )[0]
        record_offset = elf.va_to_offset(type_pointer)
        if record_offset is None or record_offset + 12 > len(elf.data):
            continue
        mapped_samples += 1
        datapoint = struct.unpack_from("<Q", elf.data, record_offset)[0] & 0xFFFFFFFF
        bits = struct.unpack_from("<I", elf.data, record_offset + 8)[0]
        type_enum = (bits >> 16) & 0xFF
        if type_enum in _IL2CPP_TYPE_ENUMS:
            plausible_samples += 1
        if type_enum in {0x11, 0x12} and datapoint < type_definition_count:
            typedef_samples += 1

    mapped_pointer_pairs = _mapped_pointer_pairs(elf, values)
    score = (
        plausible_samples * 5
        + mapped_samples * 2
        + typedef_samples * 3
        + mapped_pointer_pairs * 4
    )
    va = elf.offset_to_va(offset)
    if va is None or score < _MIN_METADATA_REGISTRATION_SCORE:
        return None
    return _MetadataRegistrationCandidate(
        score=score,
        va=va,
        type_count=type_count,
        mapped_samples=mapped_samples,
        plausible_samples=plausible_samples,
        typedef_samples=typedef_samples,
        mapped_pointer_pairs=mapped_pointer_pairs,
    )


def resolve_metadata_registration_va(
    elf: RelocatedElfLike,
    type_definition_count: int,
) -> int:
    candidates: list[_MetadataRegistrationCandidate] = []
    for segment in elf.loads:
        if segment.flags & 1:
            continue
        end = min(segment.oend, len(elf.data) - 16 * 8)
        for offset in range(segment.offset, end, 8):
            candidate = _score_metadata_registration_candidate(
                elf,
                offset,
                type_definition_count,
            )
            if candidate is not None:
                candidates.append(candidate)

    if not candidates:
        raise ValueError("failed to resolve CN Il2CppMetadataRegistration from binary")

    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    best = candidates[0]
    if (
        len(candidates) > 1
        and best.score - candidates[1].score
        < _AMBIGUOUS_METADATA_REGISTRATION_SCORE_DELTA
    ):
        examples = "; ".join(candidate.describe() for candidate in candidates[:3])
        raise ValueError(
            "ambiguous CN Il2CppMetadataRegistration candidates: " + examples
        )
    return best.va


def _validate_attribute_blob_start(
    restored_metadata: bytes,
    standard_metadata: bytes,
    elf: RelocatedElf,
    parameters: CnMetadataRecoveryParameters,
) -> None:
    tail = restored_metadata[parameters.tail_offset :]
    if parameters.blob_start >= len(tail):
        raise ValueError(
            f"CN attribute blob start is outside hidden tail. {parameters.describe()}"
        )
    try:
        parse_attribute_blob(
            tail,
            parameters.blob_start,
            MetadataTypeInfo(standard_metadata).method_count,
            BinaryTypes(elf, parameters.metadata_registration_va),
            MetadataTypeInfo(standard_metadata),
        )
    except Exception as exc:
        nearby = tail[parameters.blob_start : parameters.blob_start + 32]
        raise ValueError(
            "CN attribute blob start validation failed. "
            f"{parameters.describe()}, nearby_hex={nearby.hex(' ')}. {exc}"
        ) from exc


def resolve_cn_metadata_recovery_parameters(
    restored_metadata: bytes,
    standard_metadata: bytes,
    binary_path: Path,
) -> CnMetadataRecoveryParameters:
    target, sections = section_map(standard_metadata)
    if target != "27.2":
        raise ValueError(f"expected v27.2 metadata before CN recovery, got {target}")

    tail_offset = resolve_hidden_tail_offset(restored_metadata)
    elf = RelocatedElf(binary_path)
    metadata_registration_va = resolve_metadata_registration_va(
        elf,
        sections["typeDefinitions"].size // 0x58,
    )
    exported_types_offset = resolve_exported_type_definitions_offset(
        restored_metadata,
        tail_offset,
    )
    blob_start = resolve_attribute_blob_start(restored_metadata, tail_offset)
    parameters = CnMetadataRecoveryParameters(
        tail_offset=tail_offset,
        metadata_registration_va=metadata_registration_va,
        exported_types_offset=exported_types_offset,
        blob_start=blob_start,
    )
    _validate_attribute_blob_start(
        restored_metadata,
        standard_metadata,
        elf,
        parameters,
    )
    return parameters
