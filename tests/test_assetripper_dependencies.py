from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from ba_downloader.domain.models.asset import ChecksumSpec
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
    BundleDependencyPlanner,
    BundleEntryScan,
    SerializedFileScan,
    StreamedResourceScan,
)
from ba_downloader.infrastructure.extraction.assetripper.events import (
    AssetRipperProcessEvent,
)
from ba_downloader.infrastructure.extraction.assetripper.exporter import (
    assetripper_dependency_scan_cache_key,
    assetripper_exporter_cache_key,
)
from ba_downloader.infrastructure.extraction.assetripper.scan_cache import (
    BundleDependencyScanCache,
)
from ba_downloader.infrastructure.extraction.assetripper.scanner import (
    CachedBundleDependencyScanner,
)
from support.fixtures import build_execution_context


def _archive(tmp_path: Path, archive_id: str) -> BundleArchiveInput:
    path = tmp_path / archive_id
    path.write_bytes(archive_id.encode("ascii"))
    return BundleArchiveInput.from_path(path, archive_id=archive_id)


def _context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="jp",
        platform="android",
        version="1",
        max_retries=0,
    )


def _scan(
    archive_id: str,
    *,
    size: int | None = None,
    serialized_files: tuple[SerializedFileScan, ...] = (),
    resource_files: tuple[str, ...] = (),
    streamed_resources: tuple[StreamedResourceScan, ...] = (),
    error: str | None = None,
) -> BundleArchiveScan:
    if error is not None:
        return BundleArchiveScan(
            archive_id=archive_id,
            error=error,
        )
    return BundleArchiveScan(
        archive_id=archive_id,
        entries=(
            BundleEntryScan(
                entry_path=f"{archive_id}.bundle",
                sha256=hashlib.sha256(f"entry:{archive_id}".encode()).hexdigest(),
                size=size if size is not None else len(archive_id),
                serialized_files=serialized_files,
                resource_files=resource_files,
                streamed_resources=streamed_resources,
            ),
        ),
    )


def test_planner_groups_serialized_and_streamed_dependencies(tmp_path: Path) -> None:
    archives = (
        _archive(tmp_path, "a.zip"),
        _archive(tmp_path, "b.zip"),
        _archive(tmp_path, "c.zip"),
    )
    scans = (
        _scan(
            "a.zip",
            serialized_files=(SerializedFileScan("cab-a", ("archive:/CAB-B",)),),
        ),
        _scan(
            "b.zip",
            serialized_files=(SerializedFileScan("cab-b"),),
            streamed_resources=(
                StreamedResourceScan("cab-b", "resources/c.resS", "Texture2D"),
            ),
        ),
        _scan(
            "c.zip",
            serialized_files=(SerializedFileScan("cab-c"),),
            resource_files=("c.ress",),
        ),
    )

    plan = BundleDependencyPlanner().build(archives, scans)

    assert [component.archive_ids for component in plan.components] == [
        ("a.zip",),
        ("b.zip",),
        ("c.zip",),
    ]
    component_by_archive = {
        component.archive_ids[0]: component for component in plan.components
    }
    assert component_by_archive["a.zip"].dependency_component_ids == (
        component_by_archive["b.zip"].component_id,
    )
    assert component_by_archive["b.zip"].dependency_component_ids == (
        component_by_archive["c.zip"].component_id,
    )
    assert plan.unresolved_dependencies == ()
    assert plan.ambiguous_dependencies == ()


def test_planner_connects_every_duplicate_owner_and_records_ambiguity(
    tmp_path: Path,
) -> None:
    archives = tuple(
        _archive(tmp_path, name) for name in ("source.zip", "left.zip", "right.zip")
    )
    scans = (
        _scan(
            "source.zip",
            serialized_files=(SerializedFileScan("source", ("shared",)),),
        ),
        _scan(
            "left.zip",
            serialized_files=(SerializedFileScan("shared"),),
        ),
        _scan(
            "right.zip",
            serialized_files=(SerializedFileScan("SHARED"),),
        ),
    )

    plan = BundleDependencyPlanner().build(archives, scans)

    assert [component.archive_ids for component in plan.components] == [
        ("left.zip",),
        ("right.zip",),
        ("source.zip",),
    ]
    assert len(plan.ambiguous_dependencies) == 1
    ambiguity = plan.ambiguous_dependencies[0]
    assert ambiguity.logical_name == "shared"
    assert ambiguity.owner_node_ids == (
        "left.zip::left.zip.bundle",
        "right.zip::right.zip.bundle",
    )
    assert all(component.complete for component in plan.components)


def test_planner_prefers_local_owner_over_duplicate_archive_copies(
    tmp_path: Path,
) -> None:
    archives = tuple(
        _archive(tmp_path, name) for name in ("source.zip", "duplicate.zip")
    )
    scans = (
        _scan(
            "source.zip",
            serialized_files=(SerializedFileScan("shared", ("shared",)),),
        ),
        _scan(
            "duplicate.zip",
            serialized_files=(SerializedFileScan("shared"),),
        ),
    )

    plan = BundleDependencyPlanner().build(archives, scans)

    assert [component.archive_ids for component in plan.components] == [
        ("duplicate.zip",),
        ("source.zip",),
    ]
    assert plan.ambiguous_dependencies == ()


def test_planner_marks_missing_dependencies_but_ignores_engine_resources(
    tmp_path: Path,
) -> None:
    archives = (_archive(tmp_path, "source.zip"),)
    scans = (
        _scan(
            "source.zip",
            serialized_files=(SerializedFileScan("source", ("missing-cab",)),),
            streamed_resources=(
                StreamedResourceScan("source", "unity default resources", "Texture2D"),
                StreamedResourceScan("source", "missing.resS", "AudioClip"),
            ),
        ),
    )

    plan = BundleDependencyPlanner().build(archives, scans)

    assert [item.logical_name for item in plan.unresolved_dependencies] == [
        "missing-cab",
        "missing.ress",
    ]
    assert plan.components[0].complete is False


def test_planner_keeps_failed_scan_as_incomplete_singleton(tmp_path: Path) -> None:
    archives = (
        _archive(tmp_path, "good.zip"),
        _archive(tmp_path, "failed.zip"),
    )
    scans = (
        _scan(
            "good.zip",
            serialized_files=(SerializedFileScan("good"),),
        ),
        _scan("failed.zip", error="InvalidDataException: broken archive"),
    )

    plan = BundleDependencyPlanner().build(archives, scans)

    assert [component.archive_ids for component in plan.components] == [
        ("good.zip",),
    ]
    assert plan.scan_failures[0].archive_id == "failed.zip"


def test_planner_rejects_missing_or_duplicate_scan_records(tmp_path: Path) -> None:
    archives = (_archive(tmp_path, "a.zip"),)
    planner = BundleDependencyPlanner()

    try:
        planner.build(archives, ())
    except ValueError as exc:
        assert str(exc) == "Dependency scan results do not match bundle inputs."
    else:
        raise AssertionError("missing scan record was accepted")

    duplicate = (_scan("a.zip"), _scan("a.zip"))
    try:
        planner.build(archives, duplicate)
    except ValueError as exc:
        assert str(exc) == "Dependency scan results do not match bundle inputs."
    else:
        raise AssertionError("duplicate scan record was accepted")


def test_dependency_scan_cache_key_uses_exporter_build_fingerprint() -> None:
    scan_key = assetripper_dependency_scan_cache_key()
    export_key = assetripper_exporter_cache_key()

    assert scan_key == export_key
    assert len(scan_key) == 64


def test_planner_keeps_dependency_cycle_in_one_component(tmp_path: Path) -> None:
    archives = (_archive(tmp_path, "a.zip"), _archive(tmp_path, "b.zip"))
    scans = (
        _scan(
            "a.zip",
            serialized_files=(SerializedFileScan("a", ("b",)),),
        ),
        _scan(
            "b.zip",
            serialized_files=(SerializedFileScan("b", ("a",)),),
        ),
    )

    plan = BundleDependencyPlanner().build(archives, scans)

    assert [component.archive_ids for component in plan.components] == [
        ("a.zip", "b.zip")
    ]
    assert plan.components[0].dependency_component_ids == ()


def test_scan_cache_uses_catalog_checksum_identity(tmp_path: Path) -> None:
    path = tmp_path / "FullPatch.zip"
    path.write_bytes(b"archive")
    archive = BundleArchiveInput.from_path(
        path,
        archive_id="FullPatch.zip",
        checksum=ChecksumSpec("crc", "12345"),
    )
    cache = BundleDependencyScanCache(tmp_path / "cache")
    scan = _scan(
        archive.archive_id,
        serialized_files=(SerializedFileScan("cab-a", ("cab-b",)),),
    )

    cache.store(archive, scan, tool_key="tool-v1")
    path.touch()
    touched = BundleArchiveInput.from_path(
        path,
        archive_id=archive.archive_id,
        checksum=archive.checksum,
    )

    assert cache.load(touched, tool_key="tool-v1") == scan
    assert cache.load(touched, tool_key="tool-v2") is None


def test_scan_cache_rejects_a_different_content_fingerprint(
    tmp_path: Path,
) -> None:
    archive = _archive(tmp_path, "legacy.zip")
    cache = BundleDependencyScanCache(tmp_path / "cache")
    scan = _scan(archive.archive_id)
    old_key = "a" * 64
    current_key = "b" * 64
    cache.store(archive, scan, tool_key=old_key)
    old_path = cache.path_for(archive, tool_key=old_key)
    assert cache.load(archive, tool_key=current_key) is None
    cache.store(archive, scan, tool_key=current_key)
    current_path = cache.path_for(archive, tool_key=current_key)

    assert cache.load(archive, tool_key=current_key) == scan
    assert old_path != current_path
    assert old_path.is_file()
    assert current_path.is_file()


def test_scan_cache_invalidates_local_input_changes(tmp_path: Path) -> None:
    archive = _archive(tmp_path, "local.zip")
    cache = BundleDependencyScanCache(tmp_path / "cache")
    scan = _scan(archive.archive_id)
    cache.store(archive, scan, tool_key="tool-v1")

    archive.path.write_bytes(b"changed payload")
    changed = BundleArchiveInput.from_path(
        archive.path,
        archive_id=archive.archive_id,
    )

    assert cache.load(changed, tool_key="tool-v1") is None


def test_scan_cache_ignores_malformed_payload(tmp_path: Path) -> None:
    archive = _archive(tmp_path, "local.zip")
    cache = BundleDependencyScanCache(tmp_path / "cache")
    cache_path = cache.path_for(archive, tool_key="tool-v1")
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("not-json", encoding="utf8")

    assert cache.load(archive, tool_key="tool-v1") is None


class _RecordingScanBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def scan(
        self,
        context: ExecutionContext,
        archives: list[BundleArchiveInput],
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> tuple[BundleArchiveScan, ...]:
        _ = (context, event_callback)
        self.calls.append(tuple(item.archive_id for item in archives))
        results = []
        for archive in archives:
            results.append(
                _scan(
                    archive.archive_id,
                    serialized_files=(SerializedFileScan(archive.archive_id),),
                )
            )
        return tuple(results)


def test_cached_scanner_only_sends_cache_misses(
    tmp_path: Path,
) -> None:
    first = _archive(tmp_path, "a.zip")
    second = _archive(tmp_path, "b.zip")
    cache = BundleDependencyScanCache(tmp_path / "cache")
    cache.store(first, _scan(first.archive_id), tool_key="tool-v1")
    backend = _RecordingScanBackend()
    scanner = CachedBundleDependencyScanner(backend, cache, tool_key="tool-v1")
    scans = scanner.scan(_context(tmp_path), [first, second])

    assert [item.archive_id for item in scans] == ["a.zip", "b.zip"]
    assert backend.calls == [("b.zip",)]

    scanner.scan(_context(tmp_path), [first, second])
    assert backend.calls == [("b.zip",)]
