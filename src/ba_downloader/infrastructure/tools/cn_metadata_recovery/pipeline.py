from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.codegen_registration import (
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


@dataclass(slots=True)
class CnMetadataRecoveryResult:
    standard_v29_metadata: bytes
    validation_summary: dict[str, object]


@dataclass(slots=True)
class CnMetadataRecoveryState:
    protected_metadata: bytes
    binary_path: Path
    current_metadata: bytes
    restored_metadata: bytes = b""
    parameters: CnMetadataRecoveryParameters | None = None
    standard_v29_metadata: bytes = b""
    validation_summary: dict[str, object] | None = None


class CnMetadataRecoveryStep(Protocol):
    def __call__(self, state: CnMetadataRecoveryState) -> None: ...


@dataclass(frozen=True, slots=True)
class CnMetadataRecoveryStepSpec:
    name: str
    action: CnMetadataRecoveryStep


class CnMetadataRecoveryError(RuntimeError):
    def __init__(
        self,
        step: str,
        message: str,
        parameters: CnMetadataRecoveryParameters | None = None,
    ) -> None:
        self.step = step
        self.detail = message
        self.parameters = parameters
        parameter_text = (
            f" Parameters: {parameters.describe()}." if parameters is not None else ""
        )
        super().__init__(
            f"CN metadata recovery step '{step}' failed: {message}{parameter_text}"
        )


def _restore_runtime_metadata_view_step(state: CnMetadataRecoveryState) -> None:
    restored, _summary = restore_runtime_metadata_view(state.current_metadata)
    state.restored_metadata = restored
    state.current_metadata = restored


def _standardize_custom_layout_step(state: CnMetadataRecoveryState) -> None:
    standardized, _summary = standardize_custom_layout(state.current_metadata)
    state.current_metadata = standardized


def _apply_codegen_module_order_step(state: CnMetadataRecoveryState) -> None:
    reordered, _summary = apply_codegen_module_order(
        state.binary_path,
        state.current_metadata,
    )
    state.current_metadata = reordered


def _resolve_dynamic_parameters_step(state: CnMetadataRecoveryState) -> None:
    state.parameters = resolve_cn_metadata_recovery_parameters(
        state.restored_metadata,
        state.current_metadata,
        state.binary_path,
    )


def _require_parameters(
    state: CnMetadataRecoveryState,
    step: str,
) -> CnMetadataRecoveryParameters:
    if state.parameters is None:
        raise CnMetadataRecoveryError(
            step,
            "dynamic recovery parameters were not resolved",
        )
    return state.parameters


def _sanitize_default_values_step(state: CnMetadataRecoveryState) -> None:
    parameters = _require_parameters(state, "sanitize_default_values")
    sanitized, _summary = sanitize_default_values(
        state.binary_path,
        state.current_metadata,
        parameters.metadata_registration_va,
    )
    state.current_metadata = sanitized


def _restore_pre29_attribute_sections_step(state: CnMetadataRecoveryState) -> None:
    parameters = _require_parameters(state, "restore_pre29_attribute_sections")
    restored, _summary = restore_pre29_attribute_sections(
        state.restored_metadata,
        state.current_metadata,
        state.binary_path,
        parameters.metadata_registration_va,
        tail_offset=parameters.tail_offset,
        blob_start=parameters.blob_start,
        exported_types_offset=parameters.exported_types_offset,
    )
    state.current_metadata = restored


def _build_standard_v29_metadata_step(state: CnMetadataRecoveryState) -> None:
    parameters = _require_parameters(state, "build_standard_v29_metadata")
    standard_v29, _summary = build_standard_v29_metadata(
        state.restored_metadata,
        state.current_metadata,
        state.binary_path,
        parameters.metadata_registration_va,
        tail_offset=parameters.tail_offset,
        blob_start=parameters.blob_start,
    )
    state.standard_v29_metadata = standard_v29
    state.current_metadata = standard_v29


def _validate_standard_v29_metadata_step(state: CnMetadataRecoveryState) -> None:
    parameters = _require_parameters(state, "validate_standard_v29_metadata")
    report = validate_standard_metadata(
        state.standard_v29_metadata,
        binary=state.binary_path,
        metadata_registration_va=parameters.metadata_registration_va,
    )
    summary = dict(report.get("summary", {}))
    state.validation_summary = summary
    if not summary.get("valid") or summary.get("warningCount", 0):
        raise CnMetadataRecoveryError(
            "validate_standard_v29_metadata",
            f"standard v29 metadata validation failed: {summary}",
            parameters,
        )


DEFAULT_STEPS: tuple[CnMetadataRecoveryStepSpec, ...] = (
    CnMetadataRecoveryStepSpec(
        "restore_runtime_metadata_view",
        _restore_runtime_metadata_view_step,
    ),
    CnMetadataRecoveryStepSpec(
        "standardize_custom_layout",
        _standardize_custom_layout_step,
    ),
    CnMetadataRecoveryStepSpec(
        "apply_codegen_module_order",
        _apply_codegen_module_order_step,
    ),
    CnMetadataRecoveryStepSpec(
        "resolve_dynamic_parameters",
        _resolve_dynamic_parameters_step,
    ),
    CnMetadataRecoveryStepSpec(
        "sanitize_default_values",
        _sanitize_default_values_step,
    ),
    CnMetadataRecoveryStepSpec(
        "restore_pre29_attribute_sections",
        _restore_pre29_attribute_sections_step,
    ),
    CnMetadataRecoveryStepSpec(
        "build_standard_v29_metadata",
        _build_standard_v29_metadata_step,
    ),
    CnMetadataRecoveryStepSpec(
        "validate_standard_v29_metadata",
        _validate_standard_v29_metadata_step,
    ),
)


class CnMetadataRecoveryPipeline:
    def __init__(
        self,
        *,
        steps: Sequence[CnMetadataRecoveryStepSpec] | None = None,
    ) -> None:
        self.steps = tuple(steps or DEFAULT_STEPS)

    def run(
        self,
        *,
        protected_metadata: bytes,
        binary_path: Path,
    ) -> CnMetadataRecoveryResult:
        if not binary_path.is_file():
            raise CnMetadataRecoveryError(
                "prepare_inputs",
                f"CN metadata recovery binary does not exist: {binary_path}",
            )
        if not protected_metadata:
            raise CnMetadataRecoveryError(
                "prepare_inputs",
                "protected metadata input is empty",
            )

        state = CnMetadataRecoveryState(
            protected_metadata=protected_metadata,
            binary_path=binary_path,
            current_metadata=protected_metadata,
        )
        for step in self.steps:
            try:
                step.action(state)
            except CnMetadataRecoveryError as exc:
                if exc.parameters is None and state.parameters is not None:
                    raise CnMetadataRecoveryError(
                        exc.step,
                        exc.detail,
                        state.parameters,
                    ) from exc
                raise
            except Exception as exc:
                raise CnMetadataRecoveryError(
                    step.name,
                    str(exc) or exc.__class__.__name__,
                    state.parameters,
                ) from exc

        if not state.standard_v29_metadata:
            raise CnMetadataRecoveryError(
                "build_standard_v29_metadata",
                "pipeline completed without final standard v29 metadata",
            )
        if not state.validation_summary:
            raise CnMetadataRecoveryError(
                "validate_standard_v29_metadata",
                "pipeline completed without validation summary",
            )

        return CnMetadataRecoveryResult(
            standard_v29_metadata=state.standard_v29_metadata,
            validation_summary=state.validation_summary,
        )
