from __future__ import annotations

import string
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from elftools.elf.elffile import ELFFile

from .standard_metadata import HEADER_V27_2, Section, section_map

STANDARD_HEADER_ORDER_V27_2 = HEADER_V27_2

CODE_REG_STRUCT_QWORDS_V27_2 = 15
CODEGEN_MODULE_QWORDS_V27_2 = 18
MANUAL_NAMES_BY_CODEGEN_INDEX = {
    # These entries have protected or misleading moduleName strings in CN samples.
    # Treat them as candidates only: a name is accepted only when its metadata
    # method count matches the codegen module's methodPointerCount.
    0: ["Animancer.dll"],
    1: ["Animancer.FSM.dll"],
    2: ["Antlr3.Runtime.dll"],
    3: ["AutoMapper.dll"],
    8: ["BlueArchive.System.dll"],
    10: ["CommunityToolkit.HighPerformance.dll"],
    21: ["MX.Shader.dll"],
    22: ["MX.Shader.dll"],
    23: ["MackySoft.SerializeReferenceExtensions.dll"],
    31: ["System.dll"],
    36: ["System.IO.Compression.dll", "System.Numerics.dll"],
    46: ["UnityEngine.AnimationModule.dll", "UnityEngine.AIModule.dll"],
    48: ["UnityEngine.AnimationModule.dll"],
    54: ["UnityEngine.InputLegacyModule.dll"],
    55: ["UnityEngine.ImageConversionModule.dll"],
    63: ["UnityEngine.SubsystemsModule.dll"],
    65: ["UnityEngine.TextRenderingModule.dll"],
    67: ["UnityEngine.UI.dll"],
    73: ["UnityEngine.VideoModule.dll"],
    82: ["Unity.Notifications.Android.dll"],
    86: ["Unity.RenderPipelines.Universal.Runtime.dll"],
    88: ["Unity.Timeline.dll"],
    90: ["ZString.dll", "Unity.RenderPipelines.Core.Runtime.dll"],
    97: ["spine-unity.dll"],
}


@dataclass(frozen=True)
class LoadSegment:
    vaddr: int
    memsz: int
    offset: int
    filesz: int
    flags: int

    @property
    def vend(self) -> int:
        return self.vaddr + self.memsz

    @property
    def oend(self) -> int:
        return self.offset + self.filesz


class RelocatedElf:
    def __init__(self, path: Path):
        self.path = path
        self.data = bytearray(path.read_bytes())
        self.loads: list[LoadSegment] = []
        self.relocation_counts: dict[int, int] = {}
        self.applied_relocations = 0

        with path.open("rb") as f:
            self.elf = ELFFile(f)
            for segment in self.elf.iter_segments():
                if segment["p_type"] != "PT_LOAD":
                    continue
                self.loads.append(
                    LoadSegment(
                        int(segment["p_vaddr"]),
                        int(segment["p_memsz"]),
                        int(segment["p_offset"]),
                        int(segment["p_filesz"]),
                        int(segment["p_flags"]),
                    )
                )

            self._apply_relocations()

    def va_to_offset(self, va: int) -> int | None:
        for segment in self.loads:
            if segment.vaddr <= va < segment.vend:
                raw = segment.offset + (va - segment.vaddr)
                if raw < segment.oend:
                    return raw
        return None

    def offset_to_va(self, offset: int) -> int | None:
        for segment in self.loads:
            if segment.offset <= offset < segment.oend:
                return segment.vaddr + (offset - segment.offset)
        return None

    def is_mapped_va(self, va: int) -> bool:
        return self.va_to_offset(va) is not None

    def read_u64_offset(self, offset: int) -> int:
        return struct.unpack_from("<Q", self.data, offset)[0]

    def read_bytes_va(self, va: int, size: int) -> bytes:
        offset = self.va_to_offset(va)
        if offset is None:
            return b""
        return bytes(self.data[offset : offset + size])

    def _apply_relocations(self) -> None:
        for raw_section in self.elf.iter_sections():
            section = cast(Any, raw_section)
            if not section.name.startswith(".rela"):
                continue

            symtab = (
                cast(Any, self.elf.get_section(section["sh_link"]))
                if section["sh_link"]
                else None
            )
            for relocation in section.iter_relocations():
                rel_type = int(relocation["r_info_type"])
                self.relocation_counts[rel_type] = (
                    self.relocation_counts.get(rel_type, 0) + 1
                )

                target_offset = self.va_to_offset(int(relocation["r_offset"]))
                if target_offset is None or target_offset + 8 > len(self.data):
                    continue

                addend = int(relocation["r_addend"]) if relocation.is_RELA() else 0
                value: int | None
                if rel_type in {1027, 1032}:  # R_AARCH64_RELATIVE / IRELATIVE
                    value = addend
                elif rel_type in {257, 1025, 1026}:  # ABS64 / GLOB_DAT / JUMP_SLOT
                    symbol = (
                        symtab.get_symbol(relocation["r_info_sym"]) if symtab else None
                    )
                    value = (int(symbol["st_value"]) if symbol else 0) + addend
                else:
                    value = None

                if value is None:
                    continue

                struct.pack_into(
                    "<Q", self.data, target_offset, value & 0xFFFFFFFFFFFFFFFF
                )
                self.applied_relocations += 1


class StandardMetadata:
    def __init__(self, source: bytes):
        self.source_label = "<memory>"
        self.data = bytearray(source)
        target, sections = section_map(bytes(self.data))
        if target not in {"27.2", "29"}:
            raise ValueError(
                f"expected a standardized v27.2 or v29 metadata candidate, got {target}"
            )
        self.target = target
        self.sections = {
            name: Section(section.offset, section.size)
            for name, section in sections.items()
        }
        self.images = self._read_images()
        self.image_method_counts = self._read_image_method_counts()

    def u32(self, offset: int) -> int:
        return struct.unpack_from("<I", self.data, offset)[0]

    def read_string(self, index: int) -> str:
        strings = self.sections["string"]
        if index >= strings.size:
            return ""
        start = strings.offset + index
        end = self.data.find(b"\0", start, strings.end)
        if end < 0:
            return ""
        return bytes(self.data[start:end]).decode("utf-8", "replace")

    def _read_images(self) -> list[dict[str, Any]]:
        images = []
        section = self.sections["images"]
        for index in range(section.size // 0x28):
            row_offset = section.offset + index * 0x28
            row = struct.unpack_from("<10I", self.data, row_offset)
            images.append(
                {
                    "index": index,
                    "name": self.read_string(row[0]),
                    "row": row,
                    "row_offset": row_offset,
                    "firstTypeIndex": row[2],
                    "typeCount": row[3],
                    "assemblyIndex": row[1],
                }
            )
        return images

    def _read_image_method_counts(self) -> list[int]:
        type_section = self.sections["typeDefinitions"]
        counts = []
        for image in self.images:
            total = 0
            for type_index in range(
                image["firstTypeIndex"], image["firstTypeIndex"] + image["typeCount"]
            ):
                row_offset = type_section.offset + type_index * 0x58
                values = struct.unpack_from("<16I8H2I", self.data, row_offset)
                total += values[16]
            counts.append(total)
        return counts

    def reorder_codegen_modules(
        self, codegen_order: list[str]
    ) -> tuple[bytes, dict[str, Any]]:
        if self.target != "27.2":
            raise ValueError(
                "metadata reordering is only implemented for v27.2 candidates"
            )
        if sorted(codegen_order) != sorted(image["name"] for image in self.images):
            raise ValueError(
                "codegen order does not contain exactly the metadata image names"
            )

        images_section = self.sections["images"]
        assemblies_section = self.sections["assemblies"]
        if images_section.size != 0x28 * len(codegen_order):
            raise ValueError("unexpected image section size")
        if assemblies_section.size != 0x40 * len(codegen_order):
            raise ValueError("unexpected assembly section size")

        by_name = {image["name"]: image for image in self.images}
        old_assembly_rows = [
            bytes(
                self.data[
                    assemblies_section.offset + i * 0x40 : assemblies_section.offset
                    + (i + 1) * 0x40
                ]
            )
            for i in range(len(codegen_order))
        ]

        new_images = bytearray()
        new_assemblies = bytearray()
        for new_index, name in enumerate(codegen_order):
            image = by_name[name]
            image_row = list(image["row"])
            old_assembly_index = image_row[1]
            image_row[1] = new_index
            new_images += struct.pack("<10I", *image_row)

            assembly_row = bytearray(old_assembly_rows[old_assembly_index])
            struct.pack_into("<I", assembly_row, 0, new_index)
            new_assemblies += assembly_row

        out = bytearray(self.data)
        out[images_section.offset : images_section.end] = new_images
        out[assemblies_section.offset : assemblies_section.end] = new_assemblies

        report = {
            "image_order": codegen_order,
            "updated_images": len(codegen_order),
            "updated_assemblies": len(codegen_order),
            "referencedAssemblies_size": self.sections["referencedAssemblies"].size,
        }
        return bytes(out), report


def c_string(raw: bytes) -> str | None:
    end = raw.find(b"\0")
    if end < 0:
        return None
    try:
        value = raw[:end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if value and all(ch in string.printable and ch not in "\x0b\x0c" for ch in value):
        return value
    return None


def xor_cd_string(raw: bytes) -> str | None:
    out = bytearray()
    for byte in raw:
        decoded = byte ^ 0xCD
        if decoded == 0:
            break
        out.append(decoded)
    if not out:
        return None
    try:
        value = bytes(out).decode("utf-8")
    except UnicodeDecodeError:
        return None
    if value and all(ch in string.printable and ch not in "\x0b\x0c" for ch in value):
        return value
    return None


def decode_module_name(image: RelocatedElf, name_va: int) -> tuple[str | None, str]:
    raw = image.read_bytes_va(name_va, 160)
    plain = c_string(raw)
    if plain and (plain.endswith(".dll") or plain == "__Generated"):
        return plain, "plain"
    xored = xor_cd_string(raw)
    if xored and (xored.endswith(".dll") or xored == "__Generated"):
        return xored, "xor_cd"
    return None, "unresolved"


def module_record(image: RelocatedElf, ptr: int, index: int) -> dict[str, Any]:
    offset = image.va_to_offset(ptr)
    if offset is None or offset + CODEGEN_MODULE_QWORDS_V27_2 * 8 > len(image.data):
        raise ValueError(f"codegen module pointer is not mapped: 0x{ptr:X}")
    values = struct.unpack_from("<18Q", image.data, offset)
    decoded_name, name_mode = decode_module_name(image, values[0])
    return {
        "codegen_index": index,
        "module_va": f"0x{ptr:X}",
        "moduleName_va": f"0x{values[0]:X}",
        "decoded_name": decoded_name,
        "name_mode": name_mode,
        "methodPointerCount": values[1],
        "methodPointers": f"0x{values[2]:X}",
        "invokerIndices": f"0x{values[5]:X}",
        "rgctxRangesCount": values[8],
        "pRgctxRanges": f"0x{values[9]:X}",
        "rgctxsCount": values[10],
        "rgctxs": f"0x{values[11]:X}",
    }


def score_module_array(image: RelocatedElf, array_va: int, module_count: int) -> int:
    array_offset = image.va_to_offset(array_va)
    if array_offset is None or array_offset + module_count * 8 > len(image.data):
        return 0

    score = 0
    for index in range(module_count):
        module_va = struct.unpack_from("<Q", image.data, array_offset + index * 8)[0]
        module_offset = image.va_to_offset(module_va)
        if (
            module_offset is None
            or module_offset + CODEGEN_MODULE_QWORDS_V27_2 * 8 > len(image.data)
        ):
            continue
        values = struct.unpack_from("<18Q", image.data, module_offset)
        method_count = values[1]
        method_pointers = values[2]
        if method_count > 300000:
            continue
        if method_count == 0 or image.is_mapped_va(method_pointers):
            score += 1
    return score


def find_code_registration(image: RelocatedElf, module_count: int) -> tuple[int, int]:
    candidates: list[tuple[int, int, int]] = []
    module_count_bytes = struct.pack("<Q", module_count)
    for segment in image.loads:
        if segment.flags & 1:
            continue
        end = min(segment.oend, len(image.data) - 16)
        offset = image.data.find(module_count_bytes, segment.offset, end)
        while offset >= 0:
            if (offset - segment.offset) % 8:
                offset = image.data.find(module_count_bytes, offset + 1, end)
                continue
            array_va = image.read_u64_offset(offset + 8)
            array_offset = image.va_to_offset(array_va)
            if array_offset is None or array_offset + module_count * 8 > len(
                image.data
            ):
                offset = image.data.find(module_count_bytes, offset + 1, end)
                continue
            start_offset = offset - 13 * 8
            if start_offset >= 0:
                start_va = image.offset_to_va(start_offset)
                if start_va is not None:
                    score = score_module_array(image, array_va, module_count)
                    if score:
                        candidates.append((score, start_va, array_va))
            offset = image.data.find(module_count_bytes, offset + 1, end)

    if not candidates:
        raise ValueError("failed to find a v27.2-shaped Il2CppCodeRegistration")
    candidates.sort(reverse=True)
    _score, code_reg_va, array_va = candidates[0]
    return code_reg_va, array_va


def resolve_module_names(
    modules: list[dict[str, Any]], metadata: StandardMetadata
) -> list[dict[str, Any]]:
    names_by_count: dict[int, list[str]] = {}
    count_by_name: dict[str, int] = {}
    for image, method_count in zip(
        metadata.images,
        metadata.image_method_counts,
        strict=True,
    ):
        image_name = str(image["name"])
        names_by_count.setdefault(method_count, []).append(image_name)
        count_by_name[image_name] = method_count

    used: set[str] = set()

    def assign(module: dict[str, Any], name: str | None, resolution: str) -> bool:
        if not name:
            return False
        expected_count = count_by_name.get(name)
        actual_count = int(module["methodPointerCount"])
        if expected_count is None:
            module.setdefault("rejected_names", []).append(
                {
                    "name": name,
                    "resolution": resolution,
                    "reason": "not_in_metadata",
                }
            )
            return False
        if expected_count != actual_count:
            module.setdefault("rejected_names", []).append(
                {
                    "name": name,
                    "resolution": resolution,
                    "reason": "method_count_mismatch",
                    "metadata_method_count": expected_count,
                    "module_methodPointerCount": actual_count,
                }
            )
            return False
        if name in used:
            module.setdefault("rejected_names", []).append(
                {
                    "name": name,
                    "resolution": resolution,
                    "reason": "duplicate_name",
                }
            )
            return False
        module["resolved_name"] = name
        module["resolution"] = resolution
        used.add(name)
        return True

    for module in modules:
        if assign(module, module["decoded_name"], module["name_mode"]):
            continue

    for module in modules:
        if module.get("resolved_name"):
            continue

        for manual in MANUAL_NAMES_BY_CODEGEN_INDEX.get(module["codegen_index"], []):
            if assign(module, manual, "manual_index_count_context"):
                break
        if module.get("resolved_name"):
            continue

        candidates = [
            name
            for name in names_by_count.get(int(module["methodPointerCount"]), [])
            if name not in used
        ]
        module["candidate_names"] = candidates
        if len(candidates) == 1:
            module["resolved_name"] = candidates[0]
            module["resolution"] = "unique_method_count"
            used.add(candidates[0])
        else:
            module["resolved_name"] = None
            module["resolution"] = "unresolved"

    return modules


def _build_report_from_metadata(
    binary: Path,
    metadata: StandardMetadata,
    relocated_elf: RelocatedElf | None = None,
) -> dict[str, Any]:
    elf_image = relocated_elf or RelocatedElf(binary)
    code_reg_va, modules_array_va = find_code_registration(
        elf_image, len(metadata.images)
    )

    modules = []
    modules_array_offset = elf_image.va_to_offset(modules_array_va)
    if modules_array_offset is None:
        raise ValueError("codegen module array is not mapped")
    for index in range(len(metadata.images)):
        module_ptr = struct.unpack_from(
            "<Q", elf_image.data, modules_array_offset + index * 8
        )[0]
        modules.append(module_record(elf_image, module_ptr, index))

    modules = resolve_module_names(modules, metadata)
    resolved_order = [module["resolved_name"] for module in modules]
    unresolved = [module for module in modules if not module["resolved_name"]]
    count_mismatches = []
    count_by_name = {
        str(image["name"]): count
        for image, count in zip(
            metadata.images,
            metadata.image_method_counts,
            strict=True,
        )
    }
    for module in modules:
        if not module["resolved_name"]:
            continue
        expected = count_by_name[module["resolved_name"]]
        if expected != module["methodPointerCount"]:
            count_mismatches.append(
                {
                    "name": module["resolved_name"],
                    "metadata_method_count": expected,
                    "module_methodPointerCount": module["methodPointerCount"],
                }
            )

    code_reg_offset = elf_image.va_to_offset(code_reg_va)
    if code_reg_offset is None:
        raise ValueError("code registration is not mapped")
    code_reg_values = struct.unpack_from("<15Q", elf_image.data, code_reg_offset)
    report: dict[str, Any] = {
        "binary": str(binary),
        "metadata": metadata.source_label,
        "metadata_target": metadata.target,
        "applied_relocations": elf_image.applied_relocations,
        "relocation_types": {
            str(k): v for k, v in sorted(elf_image.relocation_counts.items())
        },
        "code_registration": {
            "va": f"0x{code_reg_va:X}",
            "reversePInvokeWrapperCount": code_reg_values[0],
            "reversePInvokeWrappers": f"0x{code_reg_values[1]:X}",
            "genericMethodPointersCount": code_reg_values[2],
            "genericMethodPointers": f"0x{code_reg_values[3]:X}",
            "genericAdjustorThunks": f"0x{code_reg_values[4]:X}",
            "invokerPointersCount": code_reg_values[5],
            "invokerPointers": f"0x{code_reg_values[6]:X}",
            "unresolvedVirtualCallCount": code_reg_values[7],
            "unresolvedVirtualCallPointers": f"0x{code_reg_values[8]:X}",
            "interopDataCount": code_reg_values[9],
            "interopData": f"0x{code_reg_values[10]:X}",
            "windowsRuntimeFactoryCount": code_reg_values[11],
            "windowsRuntimeFactoryTable": f"0x{code_reg_values[12]:X}",
            "codeGenModulesCount": code_reg_values[13],
            "addrCodeGenModulePtrs": f"0x{code_reg_values[14]:X}",
        },
        "metadata_image_count": len(metadata.images),
        "resolved_module_count": sum(
            1 for module in modules if module["resolved_name"]
        ),
        "unresolved_module_count": len(unresolved),
        "method_count_mismatches": count_mismatches,
        "metadata_original_order": [image["name"] for image in metadata.images],
        "codegen_order": resolved_order,
        "modules": modules,
    }

    return report


def apply_codegen_module_order(
    binary: Path,
    metadata_bytes: bytes,
    *,
    relocated_elf: RelocatedElf | None = None,
) -> tuple[bytes, dict[str, Any]]:
    metadata = StandardMetadata(metadata_bytes)
    report = _build_report_from_metadata(binary, metadata, relocated_elf)
    if report["unresolved_module_count"]:
        raise ValueError(
            "cannot reorder metadata while codegen module names are unresolved"
        )
    reordered, reorder_report = metadata.reorder_codegen_modules(
        [str(name) for name in report["codegen_order"]]
    )
    report["reordered_metadata"] = reorder_report
    return reordered, report
