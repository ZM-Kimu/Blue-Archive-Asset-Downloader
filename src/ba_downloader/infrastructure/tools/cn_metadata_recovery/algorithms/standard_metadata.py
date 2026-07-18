from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

MAGIC = 0xFAB11BAF

HEADER_V24_4 = [
    "stringLiteral",
    "stringLiteralData",
    "string",
    "events",
    "properties",
    "methods",
    "parameterDefaultValues",
    "fieldDefaultValues",
    "fieldAndParameterDefaultValueData",
    "fieldMarshaledSizes",
    "parameters",
    "fields",
    "genericParameters",
    "genericParameterConstraints",
    "genericContainers",
    "nestedTypes",
    "interfaces",
    "vtableMethods",
    "interfaceOffsets",
    "typeDefinitions",
    "images",
    "assemblies",
    "metadataUsageLists",
    "metadataUsagePairs",
    "fieldRefs",
    "referencedAssemblies",
    "attributesInfo",
    "attributeTypes",
    "unresolvedVirtualCallParameterTypes",
    "unresolvedVirtualCallParameterRanges",
    "windowsRuntimeTypeNames",
    "exportedTypeDefinitions",
]

HEADER_V27_2 = [
    "stringLiteral",
    "stringLiteralData",
    "string",
    "events",
    "properties",
    "methods",
    "parameterDefaultValues",
    "fieldDefaultValues",
    "fieldAndParameterDefaultValueData",
    "fieldMarshaledSizes",
    "parameters",
    "fields",
    "genericParameters",
    "genericParameterConstraints",
    "genericContainers",
    "nestedTypes",
    "interfaces",
    "vtableMethods",
    "interfaceOffsets",
    "typeDefinitions",
    "images",
    "assemblies",
    "fieldRefs",
    "referencedAssemblies",
    "attributesInfo",
    "attributeTypes",
    "unresolvedVirtualCallParameterTypes",
    "unresolvedVirtualCallParameterRanges",
    "windowsRuntimeTypeNames",
    "windowsRuntimeStrings",
    "exportedTypeDefinitions",
]

HEADER_V29 = [
    "stringLiteral",
    "stringLiteralData",
    "string",
    "events",
    "properties",
    "methods",
    "parameterDefaultValues",
    "fieldDefaultValues",
    "fieldAndParameterDefaultValueData",
    "fieldMarshaledSizes",
    "parameters",
    "fields",
    "genericParameters",
    "genericParameterConstraints",
    "genericContainers",
    "nestedTypes",
    "interfaces",
    "vtableMethods",
    "interfaceOffsets",
    "typeDefinitions",
    "images",
    "assemblies",
    "fieldRefs",
    "referencedAssemblies",
    "attributeData",
    "attributeDataRange",
    "unresolvedVirtualCallParameterTypes",
    "unresolvedVirtualCallParameterRanges",
    "windowsRuntimeTypeNames",
    "windowsRuntimeStrings",
    "exportedTypeDefinitions",
]

HEADER_BY_VERSION = {
    24: ("24.4", HEADER_V24_4),
    27: ("27.2", HEADER_V27_2),
    29: ("29", HEADER_V29),
}

ROW_SIZES = {
    "stringLiteral": 8,
    "events": 0x18,
    "properties": 0x14,
    "methods": 0x20,
    "parameterDefaultValues": 0x0C,
    "fieldDefaultValues": 0x0C,
    "fieldMarshaledSizes": 0x0C,
    "parameters": 0x0C,
    "fields": 0x0C,
    "genericParameters": 0x10,
    "genericParameterConstraints": 4,
    "genericContainers": 0x10,
    "nestedTypes": 4,
    "interfaces": 4,
    "vtableMethods": 4,
    "interfaceOffsets": 8,
    "typeDefinitions": 0x58,
    "images": 0x28,
    "assemblies": 0x40,
    "fieldRefs": 8,
    "referencedAssemblies": 4,
    "attributesInfo": 0x0C,
    "attributeTypes": 4,
    "attributeDataRange": 8,
    "unresolvedVirtualCallParameterTypes": 4,
    "unresolvedVirtualCallParameterRanges": 8,
    "windowsRuntimeTypeNames": 8,
    "windowsRuntimeStrings": 4,
    "exportedTypeDefinitions": 4,
}


@dataclass(frozen=True)
class Section:
    offset: int
    size: int

    @property
    def end(self) -> int:
        return self.offset + self.size


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def read_i32(buf: bytes, off: int) -> int:
    return i32(u32(buf, off))


def i32(value: int) -> int:
    return struct.unpack("<i", struct.pack("<I", value))[0]


def i32_to_u32(value: int) -> int:
    return value & 0xFFFFFFFF


def read_section(buf: bytes, header_off: int) -> Section:
    return Section(u32(buf, header_off), u32(buf, header_off + 4))


def section_bytes(buf: bytes | bytearray, section: Section) -> bytes:
    if section.offset == 0 and section.size == 0:
        return b""
    if section.offset < 0 or section.size < 0 or section.end > len(buf):
        raise ValueError(
            f"section out of range: offset=0x{section.offset:x} size=0x{section.size:x}"
        )
    return bytes(buf[section.offset : section.end])


def section_count(sections: dict[str, Section], name: str, row_size: int) -> int:
    if name not in sections:
        return 0
    return sections[name].size // row_size


def section_map(buf: bytes) -> tuple[str, dict[str, Section]]:
    if u32(buf, 0) != MAGIC:
        raise ValueError("not a standard IL2CPP metadata candidate")
    version = u32(buf, 4)
    if version not in HEADER_BY_VERSION:
        raise ValueError(f"unsupported metadata version {version}")
    target, names = HEADER_BY_VERSION[version]
    sections = {}
    for idx, name in enumerate(names):
        off, size = struct.unpack_from("<II", buf, 0x08 + idx * 8)
        sections[name] = Section(off, size)
    return target, sections


def read_string(
    buf: bytes | bytearray,
    strings: Section,
    index: int,
    *,
    max_length: int = 512,
) -> str:
    if index < 0 or index == 0xFFFFFFFF or index >= strings.size:
        return ""
    pos = strings.offset + index
    if pos >= len(buf):
        return ""
    end = bytes(buf).find(b"\0", pos, min(len(buf), pos + max_length))
    if end < 0:
        end = min(len(buf), pos + max_length)
    return bytes(buf[pos:end]).decode("utf-8", "replace")


def valid_range(start: int, count: int, total: int) -> bool:
    if count == 0:
        return start == -1 or 0 <= start <= total
    if start < 0:
        return False
    return start + count <= total


def valid_index(index: int, total: int, *, allow_minus_one: bool = True) -> bool:
    if allow_minus_one and index == -1:
        return True
    return 0 <= index < total


def valid_string_index(
    index: int, string_size: int, *, allow_empty: bool = False
) -> bool:
    if allow_empty and index in (-1, 0xFFFFFFFF):
        return True
    return 0 <= index < string_size


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()
