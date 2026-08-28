from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
    BundleDependencyPlanner,
    BundleEntryScan,
    SerializedFileScan,
)
from ba_downloader.infrastructure.extraction.errors import BundleExtractionError
from ba_downloader.infrastructure.extraction.unitypy.bundles import (
    UnityPyBundleWorkflow,
)


def test_dependency_planner_keeps_direct_scc_and_reports_missing_external_dependency(
    tmp_path: Path,
) -> None:
    first = _input(tmp_path / "ibuki.bundle", "direct/ibuki.bundle")
    second = _input(tmp_path / "shared.bundle", "direct/shared.bundle")
    scans = (
        BundleArchiveScan(
            first.archive_id,
            (
                BundleEntryScan(
                    "ibuki.bundle",
                    "1" * 64,
                    1,
                    serialized_files=(
                        SerializedFileScan(
                            "ibuki",
                            ("shared", "missing-outside-direct-set"),
                        ),
                    ),
                ),
            ),
        ),
        BundleArchiveScan(
            second.archive_id,
            (
                BundleEntryScan(
                    "shared.bundle",
                    "2" * 64,
                    1,
                    serialized_files=(SerializedFileScan("shared", ("ibuki",)),),
                ),
            ),
        ),
    )

    plan = BundleDependencyPlanner().build((first, second), scans)

    assert len(plan.components) == 1
    assert set(plan.components[0].archive_ids) == {
        "direct/ibuki.bundle",
        "direct/shared.bundle",
    }
    assert [issue.logical_name for issue in plan.unresolved_dependencies] == [
        "missing-outside-direct-set"
    ]


def test_unitypy_processes_only_supplied_direct_member_files(
    context_factory: object,
    recording_logger: object,
    tmp_path: Path,
) -> None:
    context = context_factory()  # type: ignore[operator]
    direct_paths = [tmp_path / "ibuki.bundle", tmp_path / "portrait.bundle"]
    for path in direct_paths:
        path.write_bytes(path.name.encode())
    loaded: list[Path] = []

    def load_environment(path: Path) -> object:
        loaded.append(path)
        obj = SimpleNamespace(
            type=SimpleNamespace(name="TextAsset", value=49),
            assets_file=SimpleNamespace(name=path.name),
            path_id=1,
            read=lambda: SimpleNamespace(
                m_Name=path.stem,
                m_Script=f"content:{path.name}".encode(),
            ),
        )
        return SimpleNamespace(objects=[obj])

    workflow = UnityPyBundleWorkflow(
        recording_logger,  # type: ignore[arg-type]
        environment_loader=load_environment,
    )
    inputs = [
        BundleArchiveInput.from_path(path, archive_id=f"direct/{path.name}")
        for path in direct_paths
    ]

    report = workflow.run(context, inputs, concurrency=2, filtered=True)

    assert loaded == direct_paths
    assert report.succeeded_batches == 2
    exported = sorted(
        path.read_bytes()
        for path in context.workspace.extracted_bundles.joinpath("Assets").rglob("*")
        if path.is_file()
    )
    assert exported == [b"content:ibuki.bundle", b"content:portrait.bundle"]


def test_unitypy_fatal_failure_preserves_existing_output(
    context_factory: object,
    recording_logger: object,
    tmp_path: Path,
) -> None:
    context = context_factory()  # type: ignore[operator]
    source = tmp_path / "broken.bundle"
    source.write_bytes(b"broken")
    output = context.workspace.extracted_bundles
    output.mkdir(parents=True)
    marker = output / "existing.txt"
    marker.write_text("keep", encoding="utf8")
    workflow = UnityPyBundleWorkflow(
        recording_logger,  # type: ignore[arg-type]
        environment_loader=lambda path: (_ for _ in ()).throw(
            RuntimeError(f"cannot load {path.name}")
        ),
    )

    with pytest.raises(BundleExtractionError, match="could not load any"):
        workflow.run(
            context,
            [BundleArchiveInput.from_path(source, archive_id="direct/broken.bundle")],
            concurrency=1,
            filtered=True,
        )

    assert marker.read_text(encoding="utf8") == "keep"


def _input(path: Path, archive_id: str) -> BundleArchiveInput:
    path.write_bytes(b"x")
    return BundleArchiveInput.from_path(path, archive_id=archive_id)
