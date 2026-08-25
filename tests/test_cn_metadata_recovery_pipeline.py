from __future__ import annotations

import struct
from pathlib import Path
from threading import Event

import pytest

import ba_downloader.infrastructure.tools.cn_metadata_recovery.pipeline as recovery_pipeline_module
from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.ports.execution import EventCancellation
from ba_downloader.infrastructure.tools.cn_metadata_recovery import (
    CnMetadataRecoveryError,
    CnMetadataRecoveryPipeline,
    CnMetadataRecoveryResult,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.codegen_registration import (
    LoadSegment,
    find_code_registration,
    resolve_module_names,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.parameters import (
    CnMetadataRecoveryParameters,
    resolve_attribute_blob_start,
    resolve_exported_type_definitions_offset,
    resolve_hidden_tail_offset,
    resolve_metadata_registration_va,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.standard_v29 import (
    assemble_standard_v29_sections,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.standardize import (
    CUSTOM_SECTIONS,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.pipeline import (
    CnMetadataInferResult,
    CnMetadataParseResult,
    CnMetadataRebuildResult,
    CnMetadataValidateResult,
)


class FakeRelocatedElf:
    def __init__(self, data: bytes) -> None:
        self.data = bytearray(data)
        self.loads = [LoadSegment(0x1000, len(data), 0, len(data), 4)]

    def va_to_offset(self, va: int) -> int | None:
        offset = va - 0x1000
        if 0 <= offset < len(self.data):
            return offset
        return None

    def offset_to_va(self, offset: int) -> int | None:
        if 0 <= offset < len(self.data):
            return 0x1000 + offset
        return None

    def read_u64_offset(self, offset: int) -> int:
        return struct.unpack_from("<Q", self.data, offset)[0]

    def is_mapped_va(self, va: int) -> bool:
        return self.va_to_offset(va) is not None


def test_standard_v29_assembly_precomputes_one_output_buffer() -> None:
    candidate, emitted = assemble_standard_v29_sections(
        {"stringLiteral": b"abc", "stringLiteralData": b"de"}
    )

    assert len(candidate) == 0x106
    assert candidate[0x100:0x103] == b"abc"
    assert candidate[0x104:0x106] == b"de"
    assert emitted["stringLiteral"]["offset"] == "0x100"


class FakeCodegenMetadata:
    def __init__(self, counts_by_name: dict[str, int]) -> None:
        self.images = [{"name": name} for name in counts_by_name]
        self.image_method_counts = list(counts_by_name.values())


def _fake_codegen_module(
    index: int,
    method_count: int,
    decoded_name: str | None = None,
) -> dict[str, object]:
    return {
        "codegen_index": index,
        "decoded_name": decoded_name,
        "name_mode": "plain" if decoded_name else "unresolved",
        "methodPointerCount": method_count,
    }


def _metadata_with_custom_sections(
    sections: dict[int, tuple[int, int]],
    *,
    size: int = 0x400,
) -> bytes:
    buf = bytearray(size)
    for header_offset, (section_offset, section_size) in sections.items():
        struct.pack_into("<II", buf, header_offset, section_offset, section_size)
    return bytes(buf)


def _pack_metadata_registration(
    data: bytearray,
    offset: int,
    *,
    type_count: int,
    type_ptrs_va: int,
) -> None:
    values = [0] * 16
    values[0] = 2
    values[1] = 0x1500
    values[2] = 3
    values[3] = 0x1520
    values[4] = 4
    values[5] = 0x1540
    values[6] = type_count
    values[7] = type_ptrs_va
    values[8] = 5
    values[9] = 0x1560
    values[10] = 6
    values[11] = 0x1580
    values[12] = 7
    values[13] = 0x15A0
    struct.pack_into("<16Q", data, offset, *values)


def _pack_type_table(
    data: bytearray,
    table_offset: int,
    record_offsets: list[int],
) -> None:
    for index, record_offset in enumerate(record_offsets):
        struct.pack_into("<Q", data, table_offset + index * 8, 0x1000 + record_offset)
        struct.pack_into("<Q", data, record_offset, index)
        struct.pack_into("<I", data, record_offset + 8, 0x00120000)


def test_cn_metadata_recovery_resolves_hidden_tail_offset_from_custom_sections() -> (
    None
):
    metadata = _metadata_with_custom_sections(
        {
            0x20: (0x100, 0x20),
            0x28: (0x180, 0x18),
            0xB8: (0x220, 0x30),
        }
    )

    assert resolve_hidden_tail_offset(metadata) == 0x250


def test_cn_metadata_recovery_resolves_exported_type_offset_from_tail_end() -> None:
    image_ranges_offset = 0x180
    hidden_tail_offset = 0x240
    metadata = bytearray(
        _metadata_with_custom_sections(
            {
                CUSTOM_SECTIONS["imageRanges"]: (image_ranges_offset, 0x50),
                0xB8: (hidden_tail_offset - 0x20, 0x20),
            },
            size=hidden_tail_offset + 0x120,
        )
    )
    struct.pack_into(
        "<10I", metadata, image_ranges_offset, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0
    )
    struct.pack_into(
        "<10I",
        metadata,
        image_ranges_offset + 0x28,
        0,
        0,
        0,
        0,
        4,
        6,
        0,
        0,
        0,
        0,
    )

    assert (
        resolve_exported_type_definitions_offset(bytes(metadata), hidden_tail_offset)
        == 0x120 - 40
    )


def test_cn_metadata_recovery_resolves_attribute_blob_start_from_assembly_summary() -> (
    None
):
    tail_offset = 0x300
    assembly_summary_offset = 0x180
    metadata = bytearray(
        _metadata_with_custom_sections(
            {
                CUSTOM_SECTIONS["assemblySummary"]: (assembly_summary_offset, 0xC0),
            },
            size=tail_offset + 0x400,
        )
    )
    struct.pack_into(
        "<16I",
        metadata,
        assembly_summary_offset,
        0,
        0,
        0,
        2,
        *([0] * 12),
    )
    struct.pack_into(
        "<16I",
        metadata,
        assembly_summary_offset + 0x40,
        0,
        0,
        2,
        5,
        *([0] * 12),
    )
    struct.pack_into(
        "<16I",
        metadata,
        assembly_summary_offset + 0x80,
        0,
        0,
        7,
        3,
        *([0] * 12),
    )

    assert resolve_attribute_blob_start(bytes(metadata), tail_offset) == 0x28


def test_cn_metadata_recovery_scans_metadata_registration_va() -> None:
    data = bytearray(0x2000)
    _pack_metadata_registration(data, 0x100, type_count=2, type_ptrs_va=0x1400)
    _pack_metadata_registration(data, 0x300, type_count=8, type_ptrs_va=0x1600)
    for offset in (0x1500, 0x1520, 0x1540, 0x1560, 0x1580, 0x15A0):
        struct.pack_into("<Q", data, offset - 0x1000, 1)
    _pack_type_table(
        data,
        0x600,
        [0x700, 0x710, 0x720, 0x730, 0x740, 0x750, 0x760, 0x770],
    )

    assert resolve_metadata_registration_va(FakeRelocatedElf(bytes(data)), 6) == 0x1300


def test_cn_metadata_recovery_metadata_registration_scan_requires_candidate() -> None:
    with pytest.raises(ValueError):
        resolve_metadata_registration_va(FakeRelocatedElf(bytes(bytearray(0x800))), 6)


def test_cn_metadata_recovery_metadata_registration_scan_rejects_ambiguous_candidates() -> (
    None
):
    data = bytearray(0x3000)
    _pack_metadata_registration(data, 0x300, type_count=8, type_ptrs_va=0x1600)
    _pack_metadata_registration(data, 0x500, type_count=8, type_ptrs_va=0x1800)
    for offset in (0x1500, 0x1520, 0x1540, 0x1560, 0x1580, 0x15A0):
        struct.pack_into("<Q", data, offset - 0x1000, 1)
    _pack_type_table(
        data,
        0x600,
        [0x900, 0x910, 0x920, 0x930, 0x940, 0x950, 0x960, 0x970],
    )
    _pack_type_table(
        data,
        0x800,
        [0x1100, 0x1110, 0x1120, 0x1130, 0x1140, 0x1150, 0x1160, 0x1170],
    )

    with pytest.raises(ValueError):
        resolve_metadata_registration_va(FakeRelocatedElf(bytes(data)), 6)


def test_cn_metadata_recovery_finds_aligned_code_registration() -> None:
    data = bytearray(0x1000)
    module_count = 2
    registration_offset = 0x100
    modules_array_offset = 0x300
    module_offsets = (0x400, 0x500)
    struct.pack_into(
        "<QQ",
        data,
        registration_offset + 13 * 8,
        module_count,
        0x1000 + modules_array_offset,
    )
    struct.pack_into(
        "<QQ",
        data,
        modules_array_offset,
        *(0x1000 + offset for offset in module_offsets),
    )
    for index, module_offset in enumerate(module_offsets, start=1):
        values = [0] * 18
        values[1] = index
        values[2] = 0x1000 + 0x700
        struct.pack_into("<18Q", data, module_offset, *values)
    data[0x801:0x809] = struct.pack("<Q", module_count)
    elf = FakeRelocatedElf(bytes(data))

    code_registration_va, modules_array_va = find_code_registration(elf, module_count)

    assert code_registration_va == 0x1000 + registration_offset
    assert modules_array_va == 0x1000 + modules_array_offset


def test_cn_metadata_recovery_rejects_stale_manual_codegen_module_name() -> None:
    metadata = FakeCodegenMetadata(
        {
            "System.IO.Compression.dll": 31,
            "System.Numerics.dll": 200,
        }
    )
    modules = [_fake_codegen_module(36, 200)]

    resolved = resolve_module_names(modules, metadata)  # type: ignore[arg-type]

    assert resolved[0]["resolved_name"] == "System.Numerics.dll"
    assert {
        "name": "System.IO.Compression.dll",
        "resolution": "manual_index_count_context",
        "reason": "method_count_mismatch",
        "metadata_method_count": 31,
        "module_methodPointerCount": 200,
    } in resolved[0]["rejected_names"]


def test_cn_metadata_recovery_resolves_cn_3_0_2_ambiguous_codegen_modules() -> None:
    metadata = FakeCodegenMetadata(
        {
            "MX.Shader.dll": 3,
            "UnityEngine.ImageConversionModule.dll": 3,
            "__Generated": 3,
        }
    )
    modules = [
        _fake_codegen_module(21, 3),
        _fake_codegen_module(55, 3),
        _fake_codegen_module(96, 3, "__Generated"),
    ]

    resolved = resolve_module_names(modules, metadata)  # type: ignore[arg-type]

    assert resolved[0]["resolved_name"] == "MX.Shader.dll"
    assert resolved[1]["resolved_name"] == "UnityEngine.ImageConversionModule.dll"
    assert resolved[2]["resolved_name"] == "__Generated"


def test_cn_metadata_recovery_pipeline_runs_immutable_phases(tmp_path: Path) -> None:
    calls: list[str] = []
    progress_events: list[tuple[str, int, int]] = []
    parameters = CnMetadataRecoveryParameters(
        tail_offset=0x100,
        metadata_registration_va=0x200,
        exported_types_offset=0x300,
    )

    def parse(source: memoryview, binary: Path) -> CnMetadataParseResult:
        calls.append("parse")
        assert source.readonly
        return CnMetadataParseResult(source, binary, b"restored", b"standardized")

    def infer(parsed: CnMetadataParseResult) -> CnMetadataInferResult:
        calls.append("infer")
        return CnMetadataInferResult(parsed, b"reordered", parameters)

    def rebuild(inferred: CnMetadataInferResult) -> CnMetadataRebuildResult:
        calls.append("rebuild")
        assert inferred.parameters is parameters
        return CnMetadataRebuildResult(inferred, b"standard-v29", 12)

    def validate(rebuilt: CnMetadataRebuildResult) -> CnMetadataValidateResult:
        calls.append("validate")
        return CnMetadataValidateResult(
            rebuilt,
            {"valid": True, "errorCount": 0, "warningCount": 0},
        )

    binary_path = tmp_path / "libil2cpp.so"
    binary_path.write_bytes(b"binary")
    pipeline = CnMetadataRecoveryPipeline(
        parse_phase=parse,
        infer_phase=infer,
        rebuild_phase=rebuild,
        validate_phase=validate,
    )

    result = pipeline.run(
        protected_metadata=b"protected",
        binary_path=binary_path,
        progress_callback=lambda stage, completed, total: progress_events.append(
            (stage, completed, total)
        ),
    )

    assert isinstance(result, CnMetadataRecoveryResult)
    assert calls == ["parse", "infer", "rebuild", "validate"]
    assert result.standard_v29_metadata == b"standard-v29"
    assert result.validation_summary == {
        "valid": True,
        "errorCount": 0,
        "warningCount": 0,
    }
    assert progress_events == [
        ("parse", 0, 4),
        ("infer", 1, 4),
        ("rebuild", 2, 4),
        ("validate", 3, 4),
        ("validate", 4, 4),
    ]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["libil2cpp.so"]


def test_cn_metadata_recovery_pipeline_reuses_one_relocated_elf(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    binary_path = tmp_path / "libil2cpp.so"
    binary_path.write_bytes(b"binary")
    relocated_elf = object()
    constructed: list[Path] = []
    consumers: list[object | None] = []
    parameters = CnMetadataRecoveryParameters(
        tail_offset=1,
        metadata_registration_va=2,
        exported_types_offset=3,
        blob_start=4,
    )

    def create_elf(path: Path) -> object:
        constructed.append(path)
        return relocated_elf

    def capture_elf(value: object | None) -> None:
        consumers.append(value)

    monkeypatch.setattr(recovery_pipeline_module, "RelocatedElf", create_elf)
    monkeypatch.setattr(
        recovery_pipeline_module,
        "restore_runtime_metadata_view",
        lambda _source: (b"restored", {}),
    )
    monkeypatch.setattr(
        recovery_pipeline_module,
        "standardize_custom_layout",
        lambda _metadata: (b"standardized", {}),
    )

    def reorder(
        _binary: Path,
        _metadata: bytes,
        *,
        relocated_elf: object | None = None,
    ) -> tuple[bytes, dict[str, object]]:
        capture_elf(relocated_elf)
        return b"reordered", {}

    def resolve(
        _restored: bytes,
        _standardized: bytes,
        _binary: Path,
        *,
        relocated_elf: object | None = None,
    ) -> CnMetadataRecoveryParameters:
        capture_elf(relocated_elf)
        return parameters

    def transform(*_args: object, **kwargs: object) -> tuple[bytes, dict[str, object]]:
        capture_elf(kwargs.get("relocated_elf"))
        return b"transformed", {}

    def validate(
        _metadata: bytes,
        **kwargs: object,
    ) -> dict[str, object]:
        capture_elf(kwargs.get("relocated_elf"))
        return {"summary": {"valid": True, "warningCount": 0}}

    monkeypatch.setattr(recovery_pipeline_module, "apply_codegen_module_order", reorder)
    monkeypatch.setattr(
        recovery_pipeline_module,
        "resolve_cn_metadata_recovery_parameters",
        resolve,
    )
    monkeypatch.setattr(recovery_pipeline_module, "sanitize_default_values", transform)
    monkeypatch.setattr(
        recovery_pipeline_module,
        "restore_pre29_attribute_sections",
        transform,
    )
    monkeypatch.setattr(
        recovery_pipeline_module,
        "build_standard_v29_metadata",
        transform,
    )
    monkeypatch.setattr(
        recovery_pipeline_module, "validate_standard_metadata", validate
    )

    result = CnMetadataRecoveryPipeline().run(
        protected_metadata=b"protected",
        binary_path=binary_path,
    )

    assert result.standard_v29_metadata == b"transformed"
    assert constructed == [binary_path]
    assert consumers == [relocated_elf] * 6


def test_cn_metadata_recovery_pipeline_reports_failed_phase(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def failing_parse(
        source: memoryview,
        binary: Path,
    ) -> CnMetadataParseResult:
        _ = (source, binary)
        calls.append("parse")
        raise ValueError("metadata header is invalid")

    binary_path = tmp_path / "libil2cpp.so"
    binary_path.write_bytes(b"binary")
    pipeline = CnMetadataRecoveryPipeline(
        parse_phase=failing_parse,
    )

    with pytest.raises(CnMetadataRecoveryError) as exc:
        pipeline.run(protected_metadata=b"protected", binary_path=binary_path)

    assert exc.value.stage == "parse"
    assert "metadata header is invalid" in str(exc.value)
    assert exc.value.diagnostics["metadata_sha256"]
    assert calls == ["parse"]


def test_cn_metadata_recovery_pipeline_stops_between_steps(tmp_path: Path) -> None:
    binary_path = tmp_path / "libil2cpp.so"
    binary_path.write_bytes(b"binary")
    cancellation_event = Event()
    calls: list[str] = []

    def cancel_after_parse(
        source: memoryview,
        binary: Path,
    ) -> CnMetadataParseResult:
        calls.append("parse")
        cancellation_event.set()
        return CnMetadataParseResult(source, binary, b"restored", b"standardized")

    pipeline = CnMetadataRecoveryPipeline(
        parse_phase=cancel_after_parse,
        cancellation=EventCancellation(cancellation_event),
    )

    with pytest.raises(OperationCancelledError):
        pipeline.run(protected_metadata=b"protected", binary_path=binary_path)

    assert calls == ["parse"]
