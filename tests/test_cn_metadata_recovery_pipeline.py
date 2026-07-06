from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.infrastructure.tools.cn_metadata_recovery import (
    CnMetadataRecoveryError,
    CnMetadataRecoveryPipeline,
    CnMetadataRecoveryResult,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery import (
    __all__ as cn_metadata_recovery_exports,
)
from ba_downloader.infrastructure.tools.cn_metadata_recovery.pipeline import (
    CnMetadataRecoveryState,
    CnMetadataRecoveryStepSpec,
)

EXPECTED_STEP_ORDER = [
    "restore_runtime_metadata_view",
    "standardize_custom_layout",
    "apply_codegen_module_order",
    "sanitize_default_values",
    "restore_legacy_attribute_sections",
    "build_standard_v29_metadata",
    "validate_standard_v29_metadata",
]


def test_cn_metadata_recovery_pipeline_runs_steps_in_memory(tmp_path: Path) -> None:
    calls: list[str] = []

    def make_step(name: str):
        def step(state: CnMetadataRecoveryState) -> None:
            calls.append(name)
            state.current_metadata = state.current_metadata + f"|{name}".encode("ascii")
            if name == "build_standard_v29_metadata":
                state.standard_v29_metadata = b"standard-v29"
            if name == "validate_standard_v29_metadata":
                state.validation_summary = {
                    "valid": True,
                    "errorCount": 0,
                    "warningCount": 0,
                }

        return step

    binary_path = tmp_path / "libil2cpp.so"
    binary_path.write_bytes(b"binary")
    pipeline = CnMetadataRecoveryPipeline(
        steps=[
            CnMetadataRecoveryStepSpec(name, make_step(name))
            for name in EXPECTED_STEP_ORDER
        ]
    )

    result = pipeline.run(
        protected_metadata=b"protected",
        binary_path=binary_path,
    )

    assert isinstance(result, CnMetadataRecoveryResult)
    assert calls == EXPECTED_STEP_ORDER
    assert result.standard_v29_metadata == b"standard-v29"
    assert result.validation_summary == {
        "valid": True,
        "errorCount": 0,
        "warningCount": 0,
    }
    assert not hasattr(result, "step_summaries")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["libil2cpp.so"]


def test_cn_metadata_recovery_pipeline_stops_with_step_name_on_failure(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def first_step(state: CnMetadataRecoveryState) -> None:
        calls.append("restore_runtime_metadata_view")
        state.current_metadata = b"restored"

    def failing_step(state: CnMetadataRecoveryState) -> None:
        calls.append("sanitize_default_values")
        raise CnMetadataRecoveryError(
            "sanitize_default_values",
            "default value section is invalid",
        )

    binary_path = tmp_path / "libil2cpp.so"
    binary_path.write_bytes(b"binary")
    pipeline = CnMetadataRecoveryPipeline(
        steps=[
            CnMetadataRecoveryStepSpec(
                "restore_runtime_metadata_view",
                first_step,
            ),
            CnMetadataRecoveryStepSpec(
                "sanitize_default_values",
                failing_step,
            ),
        ]
    )

    with pytest.raises(CnMetadataRecoveryError, match="sanitize_default_values") as exc:
        pipeline.run(protected_metadata=b"protected", binary_path=binary_path)

    assert exc.value.step == "sanitize_default_values"
    assert "default value section is invalid" in str(exc.value)
    assert not hasattr(exc.value, "summary")
    assert calls == ["restore_runtime_metadata_view", "sanitize_default_values"]


def test_cn_metadata_recovery_runtime_package_does_not_expose_probe_or_ylda_names() -> (
    None
):
    package_root = Path("src/ba_downloader/infrastructure/tools/cn_metadata_recovery")
    source_names = {path.name for path in package_root.rglob("*.py")}

    assert package_root.exists()
    assert all("probe" not in name.lower() for name in source_names)
    assert not Path("src/ba_downloader/infrastructure/tools/ylda").exists()


def test_cn_metadata_recovery_public_package_exposes_only_production_api() -> None:
    assert set(cn_metadata_recovery_exports) == {
        "CnMetadataRecoveryError",
        "CnMetadataRecoveryPipeline",
        "CnMetadataRecoveryResult",
    }


def test_cn_metadata_recovery_algorithms_are_library_only() -> None:
    algorithms_root = Path(
        "src/ba_downloader/infrastructure/tools/cn_metadata_recovery/algorithms"
    )
    forbidden_patterns = (
        "argparse",
        "parse_args",
        "def main(",
        '__name__ == "__main__"',
        "G:\\",
        "test_ba",
        ".write_text(",
        ".write_bytes(",
        "print(",
    )
    violations: list[str] = []

    for path in sorted(algorithms_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in text:
                violations.append(f"{path}: contains {pattern!r}")

    assert not violations, "\n".join(violations)


def test_cn_metadata_recovery_algorithms_are_in_static_checks() -> None:
    blocked_config_files = [
        Path("pyproject.toml"),
        Path("tests/test_architecture_boundaries.py"),
    ]
    violations = [
        str(path)
        for path in blocked_config_files
        if "cn_metadata_recovery/algorithms" in path.read_text(encoding="utf-8")
    ]

    assert not violations, "\n".join(violations)


def test_cn_metadata_recovery_algorithms_use_one_standard_layout_module() -> None:
    algorithms_root = Path(
        "src/ba_downloader/infrastructure/tools/cn_metadata_recovery/algorithms"
    )
    section_definitions = [
        path
        for path in sorted(algorithms_root.rglob("*.py"))
        if "class Section" in path.read_text(encoding="utf-8")
    ]

    assert section_definitions == [
        algorithms_root / "standard_metadata.py",
    ]


def test_cn_metadata_recovery_pipeline_uses_explicit_step_specs() -> None:
    source = Path(
        "src/ba_downloader/infrastructure/tools/cn_metadata_recovery/pipeline.py"
    ).read_text(encoding="utf-8")

    assert "CnMetadataRecoveryStepSpec" in source
    assert ".__name__ =" not in source
