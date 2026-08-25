from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, TypeVar

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.codegen_registration import (
    RelocatedElf,
    apply_codegen_module_order,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.default_values import (
    sanitize_default_values,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.parameters import (
    CnMetadataRecoveryParameters,
    resolve_cn_metadata_recovery_parameters,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.pre29_attributes import (
    restore_pre29_attribute_sections,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.runtime_metadata import (
    restore_runtime_metadata_view,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.standard_v29 import (
    build_standard_v29_metadata,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.standardize import (
    standardize_custom_layout,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.validator import (
    validate_standard_metadata,
)

PhaseResult = TypeVar("PhaseResult")
RecoveryProgressCallback = Callable[[str, int, int], None]


class _PhaseFailure(RuntimeError):
    def __init__(self, stage: str, error: Exception) -> None:
        self.stage = stage
        self.error = error
        super().__init__(str(error))


@dataclass(frozen=True, slots=True)
class CnMetadataParseResult:
    source_metadata: memoryview
    binary_path: Path
    restored_metadata: bytes
    standardized_metadata: bytes
    relocated_elf: RelocatedElf | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True, slots=True)
class CnMetadataInferResult:
    parsed: CnMetadataParseResult
    reordered_metadata: bytes
    parameters: CnMetadataRecoveryParameters


@dataclass(frozen=True, slots=True)
class CnMetadataRebuildResult:
    inferred: CnMetadataInferResult
    standard_v29_metadata: bytes
    output_size: int


@dataclass(frozen=True, slots=True)
class CnMetadataValidateResult:
    rebuilt: CnMetadataRebuildResult
    validation_summary: dict[str, object]


@dataclass(frozen=True, slots=True)
class CnMetadataRecoveryResult:
    standard_v29_metadata: bytes
    validation_summary: dict[str, object]


class ParsePhase(Protocol):
    def __call__(
        self,
        source_metadata: memoryview,
        binary_path: Path,
    ) -> CnMetadataParseResult: ...


class InferPhase(Protocol):
    def __call__(self, parsed: CnMetadataParseResult) -> CnMetadataInferResult: ...


class RebuildPhase(Protocol):
    def __call__(self, inferred: CnMetadataInferResult) -> CnMetadataRebuildResult: ...


class ValidatePhase(Protocol):
    def __call__(
        self,
        rebuilt: CnMetadataRebuildResult,
    ) -> CnMetadataValidateResult: ...


class CnMetadataRecoveryError(RuntimeError):
    def __init__(
        self,
        stage: str,
        message: str,
        parameters: CnMetadataRecoveryParameters | None = None,
        diagnostics: dict[str, object] | None = None,
    ) -> None:
        self.stage = stage
        self.step = stage
        self.detail = message
        self.parameters = parameters
        self.diagnostics = diagnostics or {}
        parameter_text = (
            f" Parameters: {parameters.describe()}." if parameters is not None else ""
        )
        super().__init__(
            f"CN metadata recovery stage '{stage}' failed: {message}{parameter_text}"
        )


def parse_cn_metadata(
    source_metadata: memoryview,
    binary_path: Path,
) -> CnMetadataParseResult:
    if not source_metadata.readonly:
        raise ValueError("CN metadata source view must be read-only.")
    restored, _restore_summary = restore_runtime_metadata_view(source_metadata)
    standardized, _standardize_summary = standardize_custom_layout(restored)
    relocated_elf = RelocatedElf(binary_path)
    return CnMetadataParseResult(
        source_metadata,
        binary_path,
        restored,
        standardized,
        relocated_elf,
    )


def infer_cn_metadata(parsed: CnMetadataParseResult) -> CnMetadataInferResult:
    reordered, _order_summary = apply_codegen_module_order(
        parsed.binary_path,
        parsed.standardized_metadata,
        relocated_elf=parsed.relocated_elf,
    )
    parameters = resolve_cn_metadata_recovery_parameters(
        parsed.restored_metadata,
        reordered,
        parsed.binary_path,
        relocated_elf=parsed.relocated_elf,
    )
    return CnMetadataInferResult(parsed, reordered, parameters)


def rebuild_cn_metadata(inferred: CnMetadataInferResult) -> CnMetadataRebuildResult:
    parsed = inferred.parsed
    parameters = inferred.parameters
    sanitized, _default_summary = sanitize_default_values(
        parsed.binary_path,
        inferred.reordered_metadata,
        parameters.metadata_registration_va,
        relocated_elf=parsed.relocated_elf,
    )
    restored_attributes, _attribute_summary = restore_pre29_attribute_sections(
        parsed.restored_metadata,
        sanitized,
        parsed.binary_path,
        parameters.metadata_registration_va,
        tail_offset=parameters.tail_offset,
        blob_start=parameters.blob_start,
        exported_types_offset=parameters.exported_types_offset,
        relocated_elf=parsed.relocated_elf,
    )
    standard_v29, _rebuild_summary = build_standard_v29_metadata(
        parsed.restored_metadata,
        restored_attributes,
        parsed.binary_path,
        parameters.metadata_registration_va,
        tail_offset=parameters.tail_offset,
        blob_start=parameters.blob_start,
        relocated_elf=parsed.relocated_elf,
    )
    return CnMetadataRebuildResult(inferred, standard_v29, len(standard_v29))


def validate_cn_metadata(
    rebuilt: CnMetadataRebuildResult,
) -> CnMetadataValidateResult:
    parameters = rebuilt.inferred.parameters
    report = validate_standard_metadata(
        rebuilt.standard_v29_metadata,
        binary=rebuilt.inferred.parsed.binary_path,
        metadata_registration_va=parameters.metadata_registration_va,
        relocated_elf=rebuilt.inferred.parsed.relocated_elf,
    )
    summary = dict(report.get("summary", {}))
    if not summary.get("valid") or summary.get("warningCount", 0):
        raise CnMetadataRecoveryError(
            "validate",
            f"standard v29 metadata validation failed: {summary}",
            parameters,
        )
    return CnMetadataValidateResult(rebuilt, summary)


class CnMetadataRecoveryPipeline:
    def __init__(
        self,
        *,
        parse_phase: ParsePhase = parse_cn_metadata,
        infer_phase: InferPhase = infer_cn_metadata,
        rebuild_phase: RebuildPhase = rebuild_cn_metadata,
        validate_phase: ValidatePhase = validate_cn_metadata,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.parse_phase = parse_phase
        self.infer_phase = infer_phase
        self.rebuild_phase = rebuild_phase
        self.validate_phase = validate_phase
        self.cancellation = cancellation or NeverCancelled()

    def run(
        self,
        *,
        protected_metadata: bytes,
        binary_path: Path,
        progress_callback: RecoveryProgressCallback | None = None,
    ) -> CnMetadataRecoveryResult:
        self.cancellation.raise_if_cancelled()
        diagnostics = self._input_diagnostics(protected_metadata, binary_path)
        if not binary_path.is_file():
            raise CnMetadataRecoveryError(
                "parse",
                f"CN metadata recovery binary does not exist: {binary_path}",
                diagnostics=diagnostics,
            )
        if not protected_metadata:
            raise CnMetadataRecoveryError(
                "parse",
                "protected metadata input is empty",
                diagnostics=diagnostics,
            )

        source = memoryview(protected_metadata).toreadonly()
        parameters: CnMetadataRecoveryParameters | None = None
        try:
            self._report_progress(progress_callback, "parse", 0)
            parsed = self._run_phase(
                "parse", lambda: self.parse_phase(source, binary_path)
            )
            self._report_progress(progress_callback, "infer", 1)
            inferred = self._run_phase("infer", lambda: self.infer_phase(parsed))
            parameters = inferred.parameters
            self._report_progress(progress_callback, "rebuild", 2)
            rebuilt = self._run_phase("rebuild", lambda: self.rebuild_phase(inferred))
            self._report_progress(progress_callback, "validate", 3)
            validated = self._run_phase(
                "validate", lambda: self.validate_phase(rebuilt)
            )
            self._report_progress(progress_callback, "validate", 4)
        except OperationCancelledError:
            raise
        except CnMetadataRecoveryError as exc:
            if not exc.diagnostics:
                exc.diagnostics.update(diagnostics)
            raise
        except _PhaseFailure as exc:
            raise CnMetadataRecoveryError(
                exc.stage,
                str(exc.error) or exc.error.__class__.__name__,
                parameters,
                diagnostics,
            ) from exc.error
        except Exception as exc:
            raise CnMetadataRecoveryError(
                "unknown",
                str(exc) or exc.__class__.__name__,
                parameters,
                diagnostics,
            ) from exc

        return CnMetadataRecoveryResult(
            validated.rebuilt.standard_v29_metadata,
            validated.validation_summary,
        )

    @staticmethod
    def _report_progress(
        callback: RecoveryProgressCallback | None,
        stage: str,
        completed: int,
    ) -> None:
        if callback is not None:
            callback(stage, completed, 4)

    def _run_phase(
        self,
        stage: str,
        action: Callable[[], PhaseResult],
    ) -> PhaseResult:
        self.cancellation.raise_if_cancelled()
        try:
            result = action()
        except (OperationCancelledError, CnMetadataRecoveryError):
            raise
        except Exception as exc:
            raise _PhaseFailure(stage, exc) from exc
        self.cancellation.raise_if_cancelled()
        return result

    @staticmethod
    def _input_diagnostics(
        protected_metadata: bytes,
        binary_path: Path,
    ) -> dict[str, object]:
        diagnostics: dict[str, object] = {
            "metadata_size": len(protected_metadata),
            "metadata_sha256": hashlib.sha256(protected_metadata).hexdigest(),
        }
        if binary_path.is_file():
            diagnostics["binary_size"] = binary_path.stat().st_size
            diagnostics["binary_sha256"] = hashlib.sha256(
                binary_path.read_bytes()
            ).hexdigest()
        return diagnostics
