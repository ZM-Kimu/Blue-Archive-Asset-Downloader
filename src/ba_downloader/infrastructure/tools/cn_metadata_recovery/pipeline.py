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
from ba_downloader.infrastructure.tools.cn_metadata_recovery.algorithms.legacy_attributes import (
    restore_legacy_attribute_sections,
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
    standard_v29_metadata: bytes = b""
    validation_summary: dict[str, object] | None = None


class CnMetadataRecoveryStep(Protocol):
    def __call__(self, state: CnMetadataRecoveryState) -> None: ...


@dataclass(frozen=True, slots=True)
class CnMetadataRecoveryStepSpec:
    name: str
    action: CnMetadataRecoveryStep


class CnMetadataRecoveryError(RuntimeError):
    def __init__(self, step: str, message: str) -> None:
        self.step = step
        super().__init__(f"CN metadata recovery step '{step}' failed: {message}")


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


def _sanitize_default_values_step(state: CnMetadataRecoveryState) -> None:
    sanitized, _summary = sanitize_default_values(
        state.binary_path,
        state.current_metadata,
    )
    state.current_metadata = sanitized


def _restore_legacy_attribute_sections_step(state: CnMetadataRecoveryState) -> None:
    restored, _summary = restore_legacy_attribute_sections(
        state.restored_metadata,
        state.current_metadata,
        state.binary_path,
    )
    state.current_metadata = restored


def _build_standard_v29_metadata_step(state: CnMetadataRecoveryState) -> None:
    standard_v29, _summary = build_standard_v29_metadata(
        state.restored_metadata,
        state.current_metadata,
        state.binary_path,
    )
    state.standard_v29_metadata = standard_v29
    state.current_metadata = standard_v29


def _validate_standard_v29_metadata_step(state: CnMetadataRecoveryState) -> None:
    report = validate_standard_metadata(
        state.standard_v29_metadata,
        binary=state.binary_path,
    )
    summary = dict(report.get("summary", {}))
    state.validation_summary = summary
    if not summary.get("valid") or summary.get("warningCount", 0):
        raise CnMetadataRecoveryError(
            "validate_standard_v29_metadata",
            f"standard v29 metadata validation failed: {summary}",
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
        "sanitize_default_values",
        _sanitize_default_values_step,
    ),
    CnMetadataRecoveryStepSpec(
        "restore_legacy_attribute_sections",
        _restore_legacy_attribute_sections_step,
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
            except CnMetadataRecoveryError:
                raise
            except Exception as exc:
                raise CnMetadataRecoveryError(
                    step.name,
                    str(exc) or exc.__class__.__name__,
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
