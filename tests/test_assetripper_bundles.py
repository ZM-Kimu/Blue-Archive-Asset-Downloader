from __future__ import annotations

import hashlib
import json
import shutil
import threading
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

import pytest

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.assetripper.bundles import (
    AssetRipperBundleWorkflow,
)
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
    BundleEntryScan,
    SerializedFileScan,
)
from ba_downloader.infrastructure.extraction.assetripper.events import (
    SERIALIZE_REFERENCE_UNSUPPORTED_MESSAGE,
    AssetRipperHeartbeatEvent,
    AssetRipperLogEvent,
    AssetRipperPhaseEvent,
    AssetRipperProcessEvent,
    AssetRipperProgressEvent,
    AssetRipperScanProgressEvent,
)
from ba_downloader.infrastructure.extraction.assetripper.exporter import (
    AssetRipperExportedFile,
    AssetRipperExportError,
    AssetRipperExportInput,
    AssetRipperExportResult,
    AssetRipperToolError,
)
from ba_downloader.infrastructure.extraction.assetripper.scheduler import (
    BundleBatchScheduler,
    SystemResourceSnapshot,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    ASSETRIPPER_COMMIT,
    ASSETRIPPER_OVERLAY_VERSION,
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.extraction.threaded_runner import (
    ExtractionFailureError,
)
from support.fixtures import RecordingLogger, build_execution_context


def _context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="jp",
        platform="android",
        version="1",
        max_retries=0,
    )


class FakeExporter:
    def __init__(
        self,
        *,
        fail: bool = False,
        serialize_reference_count: int = 0,
    ) -> None:
        self.fail = fail
        self.serialize_reference_count = serialize_reference_count
        self.calls: list[tuple[bytes, ...]] = []

    def export(
        self,
        context: ExecutionContext,
        inputs: list[AssetRipperExportInput],
        output_directory: Path,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> AssetRipperExportResult:
        _ = context
        self.calls.append(tuple(item.path.read_bytes() for item in inputs))
        if event_callback is not None:
            event_callback(AssetRipperPhaseEvent("loading"))
            for stage in (
                "extracting_inputs",
                "loading_files",
                "creating_collections",
                "resolving_dependencies",
            ):
                event_callback(AssetRipperProgressEvent("loading", 1, 1, stage))
            event_callback(AssetRipperPhaseEvent("processing"))
            event_callback(AssetRipperHeartbeatEvent("processing", 12.5))
            for _ in range(self.serialize_reference_count):
                event_callback(
                    AssetRipperLogEvent(
                        "error",
                        "Import",
                        SERIALIZE_REFERENCE_UNSUPPORTED_MESSAGE,
                    )
                )
            event_callback(AssetRipperPhaseEvent("exporting"))
            event_callback(AssetRipperProgressEvent("exporting", 3, 7))
            event_callback(AssetRipperLogEvent("warning", "Export", "skipped item"))
        if self.fail:
            raise AssetRipperExportError("invalid bundle")
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / "asset.bin").write_bytes(b"asset")
        targets = tuple(item.node_id for item in inputs if item.target)
        return AssetRipperExportResult(
            (AssetRipperExportedFile("asset.bin", 5),),
            targets,
            targets,
            targets,
        )


class ScriptedExporter:
    def __init__(
        self,
        responses: list[dict[str, bytes] | Exception],
        *,
        coverage_mismatch_calls: set[int] | None = None,
    ) -> None:
        self._responses = responses
        self._coverage_mismatch_calls = coverage_mismatch_calls or set()
        self.calls: list[tuple[bytes, ...]] = []

    def export(
        self,
        context: ExecutionContext,
        inputs: list[AssetRipperExportInput],
        output_directory: Path,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> AssetRipperExportResult:
        _ = (context, event_callback)
        self.calls.append(tuple(item.path.read_bytes() for item in inputs))
        response = self._responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response

        exported: list[AssetRipperExportedFile] = []
        for relative_path, payload in response.items():
            destination = output_directory.joinpath(*PurePosixPath(relative_path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            exported.append(AssetRipperExportedFile(relative_path, len(payload)))
        targets = tuple(item.node_id for item in inputs if item.target)
        exported_targets = (
            () if len(self.calls) in self._coverage_mismatch_calls else targets
        )
        return AssetRipperExportResult(
            tuple(exported),
            targets,
            targets,
            exported_targets,
        )


class FakeDependencyScanner:
    def __init__(
        self,
        dependencies: dict[str, tuple[str, ...]] | None = None,
        *,
        errors: dict[str, str] | None = None,
        corrupt_hash: bool = False,
    ) -> None:
        self.dependencies = dependencies or {}
        self.errors = errors or {}
        self.corrupt_hash = corrupt_hash
        self.calls: list[tuple[str, ...]] = []

    def scan(
        self,
        context: ExecutionContext,
        archives: list[BundleArchiveInput],
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> tuple[BundleArchiveScan, ...]:
        _ = context
        self.calls.append(tuple(item.archive_id for item in archives))
        scans = []
        for current, archive in enumerate(archives, start=1):
            if event_callback is not None:
                event_callback(
                    AssetRipperScanProgressEvent(
                        current,
                        len(archives),
                        archive.archive_id,
                    )
                )
            entries: list[BundleEntryScan] = []
            with zipfile.ZipFile(archive.path) as bundle_archive:
                for entry in bundle_archive.infolist():
                    if entry.is_dir():
                        continue
                    payload = bundle_archive.read(entry)
                    node_id = f"{archive.archive_id}::{entry.filename}"
                    entries.append(
                        BundleEntryScan(
                            entry_path=entry.filename,
                            sha256=(
                                "f" * 64
                                if self.corrupt_hash
                                else hashlib.sha256(payload).hexdigest()
                            ),
                            size=len(payload),
                            serialized_files=(
                                SerializedFileScan(
                                    PurePosixPath(entry.filename).name,
                                    self.dependencies.get(
                                        node_id,
                                        self.dependencies.get(archive.archive_id, ()),
                                    ),
                                ),
                            ),
                        )
                    )
            scans.append(
                BundleArchiveScan(
                    archive_id=archive.archive_id,
                    sha256=hashlib.sha256(archive.path.read_bytes()).hexdigest(),
                    entries=tuple(entries),
                    error=self.errors.get(archive.archive_id),
                )
            )
        return tuple(scans)


class _ParallelResourceProbe:
    def snapshot(self) -> SystemResourceSnapshot:
        return SystemResourceSnapshot(8, 32 * 1024**3)


class _SerialResourceProbe:
    def snapshot(self) -> SystemResourceSnapshot:
        return SystemResourceSnapshot(2, 32 * 1024**3)


class _ConstrainedResourceProbe:
    def snapshot(self) -> SystemResourceSnapshot:
        return SystemResourceSnapshot(8, 10_171_887_616)


class _ConcurrentExporter:
    def __init__(self) -> None:
        self._barrier = threading.Barrier(2, timeout=5)
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def export(
        self,
        context: ExecutionContext,
        inputs: list[AssetRipperExportInput],
        output_directory: Path,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> AssetRipperExportResult:
        _ = (context, event_callback)
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        self._barrier.wait()
        target_ids = tuple(item.node_id for item in inputs if item.target)
        output_directory.mkdir(parents=True, exist_ok=True)
        output_name = hashlib.sha256("\n".join(target_ids).encode()).hexdigest()
        output = output_directory / f"{output_name}.bin"
        output.write_bytes(b"output")
        with self._lock:
            self.active -= 1
        return AssetRipperExportResult(
            (AssetRipperExportedFile(output.name, 6),),
            target_ids,
            target_ids,
            target_ids,
        )


def _bundle(
    tmp_path: Path,
    name: str,
    size: int = 4,
    *,
    entries: dict[str, bytes] | None = None,
) -> Path:
    path = tmp_path / name
    payloads = entries or {f"{path.stem}.bundle": path.stem[:1].encode("ascii") * size}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for entry_path, payload in payloads.items():
            archive.writestr(entry_path, payload)
    return path


def test_workflow_sorts_inputs_and_calls_exporter_once(tmp_path: Path) -> None:
    exporter = FakeExporter()
    scanner = FakeDependencyScanner()
    workflow = AssetRipperBundleWorkflow(exporter, scanner, RecordingLogger())

    workflow.run(
        _context(tmp_path),
        [_bundle(tmp_path, "c.zip"), _bundle(tmp_path, "a.zip")],
    )

    assert exporter.calls == [(b"a" * 4, b"c" * 4)]
    assert scanner.calls == [("a.zip", "c.zip")]
    assert (
        _context(tmp_path).workspace.extracted_bundles / "content" / "asset.bin"
    ).is_file()


def test_workflow_runs_memory_safe_batches_concurrently(tmp_path: Path) -> None:
    exporter = _ConcurrentExporter()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
        batch_scheduler=BundleBatchScheduler(_ParallelResourceProbe()),
    )

    report = workflow.run(
        _context(tmp_path),
        [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")],
    )

    assert exporter.max_active == 2
    assert report.succeeded_batches == 2


def test_workflow_does_not_start_queued_batches_after_fatal_tool_error(
    tmp_path: Path,
) -> None:
    exporter = ScriptedExporter(
        [
            AssetRipperToolError("protocol unavailable"),
            {"Assets/b.bin": b"b"},
            {"Assets/c.bin": b"c"},
        ]
    )
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
        batch_scheduler=BundleBatchScheduler(_SerialResourceProbe()),
    )

    with pytest.raises(ExtractionFailureError):
        workflow.run(
            _context(tmp_path),
            [
                _bundle(tmp_path, "a.zip"),
                _bundle(tmp_path, "b.zip"),
                _bundle(tmp_path, "c.zip"),
            ],
        )

    assert len(exporter.calls) == 1


def test_workflow_continues_serially_when_parallel_memory_reserve_is_unavailable(
    tmp_path: Path,
) -> None:
    exporter = ScriptedExporter(
        [
            {"Assets/a.bin": b"a"},
            {"Assets/b.bin": b"b"},
            {"Assets/c.bin": b"c"},
        ]
    )
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        logger,
        max_batch_bytes=4,
        batch_scheduler=BundleBatchScheduler(
            _ConstrainedResourceProbe(),
            memory_reserve_bytes=10 * 1024**3,
        ),
    )

    report = workflow.run(
        _context(tmp_path),
        [
            _bundle(tmp_path, "a.zip"),
            _bundle(tmp_path, "b.zip"),
            _bundle(tmp_path, "c.zip"),
        ],
    )

    assert report.succeeded_batches == 3
    assert len(exporter.calls) == 3
    assert logger.by_level("warn")


def test_workflow_aggregates_serialize_reference_errors(tmp_path: Path) -> None:
    exporter = FakeExporter(serialize_reference_count=122)
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(exporter, FakeDependencyScanner(), logger)

    workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert logger.by_level("warn")


def test_workflow_flushes_serialize_reference_warning_on_failure(
    tmp_path: Path,
) -> None:
    exporter = FakeExporter(fail=True, serialize_reference_count=2)
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(exporter, FakeDependencyScanner(), logger)

    with pytest.raises(ExtractionFailureError):
        workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert logger.by_level("warn")


def test_workflow_surfaces_the_underlying_assetripper_failure(tmp_path: Path) -> None:
    workflow = AssetRipperBundleWorkflow(
        FakeExporter(fail=True),
        FakeDependencyScanner(),
        RecordingLogger(),
    )

    with pytest.raises(ExtractionFailureError):
        workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])


def test_workflow_failure_does_not_publish_partial_output(tmp_path: Path) -> None:
    exporter = FakeExporter(fail=True)
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(exporter, FakeDependencyScanner(), logger)
    output_root = _context(tmp_path).workspace.extracted_bundles
    output_root.mkdir(parents=True)
    (output_root / "old-batch").mkdir()
    (output_root / "old-batch" / "asset.bin").write_bytes(b"old")

    with pytest.raises(ExtractionFailureError):
        workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert (output_root / "old-batch" / "asset.bin").read_bytes() == b"old"
    assert not (output_root / "content").exists()
    assert exporter.calls == [(b"a" * 4,)]


def test_workflow_replaces_old_batch_layout_with_content_manifest(
    tmp_path: Path,
) -> None:
    exporter = FakeExporter()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
    )
    output_root = _context(tmp_path).workspace.extracted_bundles
    old_batch = output_root / "batch-old"
    old_batch.mkdir(parents=True)
    (old_batch / "asset.bin").write_bytes(b"old")

    workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert not old_batch.exists()
    manifest = json.loads(
        (output_root / "content" / "manifest.json").read_text(encoding="utf8")
    )
    assert manifest["schema_version"] == 7
    assert manifest["layout"] == "content"
    assert [item["name"] for item in manifest["inputs"]] == ["a.zip"]
    assert manifest["entries"] == [
        {
            "aliases": [],
            "entry_path": "a.bundle",
            "node_id": "a.zip::a.bundle",
            "sha256": hashlib.sha256(b"a" * 4).hexdigest(),
            "size": 4,
            "source_archive": "a.zip",
        }
    ]
    assert manifest["assetripper"]["commit"] == ASSETRIPPER_COMMIT
    assert manifest["assetripper"]["overlay_version"] == ASSETRIPPER_OVERLAY_VERSION
    assert manifest["assetripper"]["overlay_hash"] == (
        AssetRipperSourceResolver.overlay_hash()
    )


def test_workflow_skips_complete_output_with_same_fingerprint(
    tmp_path: Path,
) -> None:
    exporter = FakeExporter()
    scanner = FakeDependencyScanner()
    workflow = AssetRipperBundleWorkflow(exporter, scanner, RecordingLogger())
    bundle = _bundle(tmp_path, "a.zip")

    first = workflow.run(_context(tmp_path), [bundle])
    second = workflow.run(_context(tmp_path), [bundle])

    assert first.complete is True
    assert second.complete is True
    assert len(exporter.calls) == 1
    assert len(scanner.calls) == 1


@pytest.mark.parametrize("damage", ["missing", "wrong_size"])
def test_workflow_rebuilds_complete_output_when_inventory_is_damaged(
    tmp_path: Path,
    damage: str,
) -> None:
    exporter = FakeExporter()
    scanner = FakeDependencyScanner()
    workflow = AssetRipperBundleWorkflow(exporter, scanner, RecordingLogger())
    bundle = _bundle(tmp_path, "a.zip")

    workflow.run(_context(tmp_path), [bundle])
    output = _context(tmp_path).workspace.extracted_bundles / "content" / "asset.bin"
    if damage == "missing":
        output.unlink()
    else:
        output.write_bytes(b"damaged")

    report = workflow.run(_context(tmp_path), [bundle])

    assert report.complete is True
    assert output.read_bytes() == b"asset"
    assert len(exporter.calls) == 2
    assert len(scanner.calls) == 2


def test_workflow_resumes_only_failed_batches_for_matching_partial_output(
    tmp_path: Path,
) -> None:
    bundles = [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")]
    first_exporter = ScriptedExporter(
        [
            {"Assets/a.bin": b"a"},
            AssetRipperExportError("temporary failure"),
        ]
    )
    first = AssetRipperBundleWorkflow(
        first_exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    ).run(_context(tmp_path), bundles)
    resumed_exporter = ScriptedExporter([{"Assets/b.bin": b"b"}])

    resumed = AssetRipperBundleWorkflow(
        resumed_exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    ).run(_context(tmp_path), bundles)

    content_root = _context(tmp_path).workspace.extracted_bundles / "content"
    assert first.complete is False
    assert resumed.complete is True
    assert resumed_exporter.calls == [(b"b" * 4,)]
    assert (content_root / "Assets" / "a.bin").read_bytes() == b"a"
    assert (content_root / "Assets" / "b.bin").read_bytes() == b"b"
    manifest = json.loads((content_root / "manifest.json").read_text(encoding="utf8"))
    assert [batch["status"] for batch in manifest["batches"]] == [
        "succeeded",
        "succeeded",
    ]


def test_workflow_partial_resume_preserves_existing_conflict_variants(
    tmp_path: Path,
) -> None:
    bundles = [
        _bundle(tmp_path, "a.zip"),
        _bundle(tmp_path, "b.zip"),
        _bundle(tmp_path, "c.zip"),
    ]
    first = AssetRipperBundleWorkflow(
        ScriptedExporter(
            [
                {"Assets/shared.bin": b"canonical"},
                {"Assets/shared.bin": b"variant"},
                AssetRipperExportError("temporary failure"),
            ]
        ),
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    ).run(_context(tmp_path), bundles)

    resumed = AssetRipperBundleWorkflow(
        ScriptedExporter([{"Assets/c.bin": b"c"}]),
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    ).run(_context(tmp_path), bundles)

    content_root = _context(tmp_path).workspace.extracted_bundles / "content"
    conflict_hash = hashlib.sha256(b"variant").hexdigest()
    conflict = content_root / "_baad_conflicts" / conflict_hash / "Assets/shared.bin"
    manifest = json.loads((content_root / "manifest.json").read_text(encoding="utf8"))
    assert first.complete is False
    assert resumed.complete is False
    assert (content_root / "Assets" / "shared.bin").read_bytes() == b"canonical"
    assert conflict.read_bytes() == b"variant"
    assert (content_root / "Assets" / "c.bin").read_bytes() == b"c"
    assert manifest["summary"]["conflict_paths"] == 1
    assert manifest["summary"]["conflict_variants"] == 1


def test_workflow_rebuilds_partial_output_with_damaged_conflict_variant(
    tmp_path: Path,
) -> None:
    bundles = [
        _bundle(tmp_path, "a.zip"),
        _bundle(tmp_path, "b.zip"),
        _bundle(tmp_path, "c.zip"),
    ]
    AssetRipperBundleWorkflow(
        ScriptedExporter(
            [
                {"Assets/shared.bin": b"canonical"},
                {"Assets/shared.bin": b"variant"},
                AssetRipperExportError("temporary failure"),
            ]
        ),
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    ).run(_context(tmp_path), bundles)
    conflict_hash = hashlib.sha256(b"variant").hexdigest()
    conflict = (
        _context(tmp_path).workspace.extracted_bundles
        / "content"
        / "_baad_conflicts"
        / conflict_hash
        / "Assets/shared.bin"
    )
    conflict.write_bytes(b"changed")
    exporter = ScriptedExporter(
        [
            {"Assets/shared.bin": b"canonical"},
            {"Assets/shared.bin": b"variant"},
            {"Assets/c.bin": b"c"},
        ]
    )

    report = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    ).run(_context(tmp_path), bundles)

    assert report.succeeded_batches == 3
    assert len(exporter.calls) == 3
    assert conflict.read_bytes() == b"variant"


def test_workflow_does_not_hash_outputs_without_path_conflicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = AssetRipperBundleWorkflow(
        ScriptedExporter([{"Assets/a.bin": b"a"}]),
        FakeDependencyScanner(),
        RecordingLogger(),
    )

    def unexpected_hash(_path: Path, **_kwargs: object) -> str:
        raise AssertionError("uncontested output was hashed")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.assetripper.bundles.calculate_sha256",
        unexpected_hash,
    )

    report = workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert report.complete is True


def test_workflow_batches_only_between_dependency_components(tmp_path: Path) -> None:
    exporter = FakeExporter()
    scanner = FakeDependencyScanner({"a.zip": ("b.bundle",)})
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        scanner,
        logger,
        max_batch_bytes=7,
    )

    workflow.run(
        _context(tmp_path),
        [
            _bundle(tmp_path, "c.zip"),
            _bundle(tmp_path, "b.zip"),
            _bundle(tmp_path, "a.zip"),
        ],
    )

    assert exporter.calls == [(b"a" * 4, b"b" * 4), (b"c" * 4,)]
    assert logger.by_level("warn")
    manifest = json.loads(
        (
            _context(tmp_path).workspace.extracted_bundles / "content" / "manifest.json"
        ).read_text(encoding="utf8")
    )
    assert [item["entries"] for item in manifest["batches"]] == [
        ["a.zip::a.bundle", "b.zip::b.bundle"],
        ["c.zip::c.bundle"],
    ]


def test_workflow_rejects_incomplete_dependency_scan_before_export(
    tmp_path: Path,
) -> None:
    exporter = FakeExporter()
    scanner = FakeDependencyScanner({"a.zip": ("missing-cab",)})
    workflow = AssetRipperBundleWorkflow(
        exporter,
        scanner,
        RecordingLogger(),
    )

    with pytest.raises(ExtractionFailureError) as captured:
        workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert "missing-cab" in str(captured.value.failures[0].error)
    assert exporter.calls == []
    assert not (_context(tmp_path).workspace.extracted_bundles).exists()


def test_workflow_extracts_only_entries_selected_for_each_batch(
    tmp_path: Path,
) -> None:
    exporter = FakeExporter()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    )

    workflow.run(
        _context(tmp_path),
        [
            _bundle(
                tmp_path,
                "a.zip",
                entries={"first.bundle": b"1111", "second.bundle": b"2222"},
            )
        ],
    )

    assert exporter.calls == [(b"1111",), (b"2222",)]


def test_workflow_reloads_shared_dependency_from_entry_cache(
    tmp_path: Path,
) -> None:
    exporter = FakeExporter()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(
            {
                "a.zip": ("shared.bundle",),
                "b.zip": ("shared.bundle",),
            }
        ),
        RecordingLogger(),
        max_batch_bytes=8,
    )

    workflow.run(
        _context(tmp_path),
        [
            _bundle(tmp_path, "a.zip"),
            _bundle(tmp_path, "b.zip"),
            _bundle(tmp_path, "shared.zip"),
        ],
    )

    assert exporter.calls == [
        (b"a" * 4, b"s" * 4),
        (b"b" * 4, b"s" * 4),
    ]
    manifest = json.loads(
        (
            _context(tmp_path).workspace.extracted_bundles / "content" / "manifest.json"
        ).read_text(encoding="utf8")
    )
    assert [item["targets"] for item in manifest["batches"]] == [
        ["a.zip::a.bundle", "shared.zip::shared.bundle"],
        ["b.zip::b.bundle"],
    ]
    assert manifest["entry_cache"] == {
        "bytes_written": 12,
        "hits": 1,
        "misses": 3,
    }
    cached_payloads = [
        path
        for path in (
            _context(tmp_path).workspace.cache_state / "assetripper" / "entries"
        ).rglob("*")
        if path.is_file() and path.suffix != ".json"
    ]
    assert len(cached_payloads) == 3


def test_workflow_rejects_archive_entry_that_no_longer_matches_scan(
    tmp_path: Path,
) -> None:
    exporter = FakeExporter()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(corrupt_hash=True),
        RecordingLogger(),
    )

    with pytest.raises(ExtractionFailureError) as captured:
        workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert "changed after dependency scanning" in str(captured.value.failures[0].error)
    assert exporter.calls == []


def test_workflow_preserves_conflicting_variants_and_tracks_all_sources(
    tmp_path: Path,
) -> None:
    first = b"first"
    second = b"second"
    exporter = ScriptedExporter(
        [
            {"Assets/shared.bin": first},
            {"Assets/shared.bin": second},
            {"Assets/shared.bin": second},
        ]
    )
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        logger,
        max_batch_bytes=4,
    )

    report = workflow.run(
        _context(tmp_path),
        [
            _bundle(tmp_path, "a.zip"),
            _bundle(tmp_path, "b.zip"),
            _bundle(tmp_path, "c.zip"),
        ],
    )

    content_root = _context(tmp_path).workspace.extracted_bundles / "content"
    second_sha256 = hashlib.sha256(second).hexdigest()
    assert (content_root / "Assets" / "shared.bin").read_bytes() == first
    assert (
        content_root / "_baad_conflicts" / second_sha256 / "Assets" / "shared.bin"
    ).read_bytes() == second
    assert report.complete is False
    assert report.conflict_paths == 1
    assert report.conflict_variants == 1

    manifest = json.loads((content_root / "manifest.json").read_text(encoding="utf8"))
    assert manifest["schema_version"] == 7
    assert manifest["complete"] is False
    assert manifest["summary"]["conflict_paths"] == 1
    assert manifest["summary"]["conflict_variants"] == 1
    assert manifest["conflicts"] == [
        {
            "canonical": {
                "sha256": hashlib.sha256(first).hexdigest(),
                "size": len(first),
                "source_batches": ["batch-1"],
                "stored_path": "Assets/shared.bin",
            },
            "original_path": "Assets/shared.bin",
            "variants": [
                {
                    "sha256": second_sha256,
                    "size": len(second),
                    "source_batches": ["batch-2", "batch-3"],
                    "stored_path": (
                        f"_baad_conflicts/{second_sha256}/Assets/shared.bin"
                    ),
                }
            ],
        }
    ]


def test_workflow_aggregates_multiple_conflicts_per_batch(tmp_path: Path) -> None:
    exporter = ScriptedExporter(
        [
            {"Assets/a.bin": b"a1", "Assets/b.bin": b"b1"},
            {"Assets/a.bin": b"a2", "Assets/b.bin": b"b2"},
        ]
    )
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        logger,
        max_batch_bytes=4,
    )

    report = workflow.run(
        _context(tmp_path),
        [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")],
    )

    assert report.complete is False
    assert report.conflict_paths == 2
    assert report.conflict_variants == 2


def test_workflow_continues_after_batch_failure_and_publishes_partial_output(
    tmp_path: Path,
) -> None:
    exporter = ScriptedExporter(
        [
            AssetRipperExportError("broken first batch"),
            {"Assets/succeeded.bin": b"ok"},
        ]
    )
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        logger,
        max_batch_bytes=4,
    )

    report = workflow.run(
        _context(tmp_path),
        [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")],
    )

    content_root = _context(tmp_path).workspace.extracted_bundles / "content"
    assert (content_root / "Assets" / "succeeded.bin").read_bytes() == b"ok"
    assert report.complete is False
    assert report.succeeded_batches == 1
    assert report.failed_batches == 1
    assert any("[BUNDLE_BATCH_FAILED]" in warning for warning in report.warnings)
    manifest = json.loads((content_root / "manifest.json").read_text(encoding="utf8"))
    assert [batch["status"] for batch in manifest["batches"]] == [
        "failed",
        "succeeded",
    ]
    assert manifest["batches"][0]["error"] == {
        "type": "AssetRipperExportError",
        "message": "broken first batch",
    }


def test_workflow_skips_batch_when_selective_export_coverage_is_incomplete(
    tmp_path: Path,
) -> None:
    exporter = ScriptedExporter(
        [
            {"Assets/incomplete.bin": b"incomplete"},
            {"Assets/succeeded.bin": b"ok"},
        ],
        coverage_mismatch_calls={1},
    )
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    )

    report = workflow.run(
        _context(tmp_path),
        [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")],
    )

    content_root = _context(tmp_path).workspace.extracted_bundles / "content"
    assert not (content_root / "Assets" / "incomplete.bin").exists()
    assert (content_root / "Assets" / "succeeded.bin").read_bytes() == b"ok"
    assert report.succeeded_batches == 1
    assert report.failed_batches == 1
    assert any("target coverage" in warning for warning in report.warnings)


def test_workflow_all_failed_batches_preserve_existing_output(tmp_path: Path) -> None:
    exporter = ScriptedExporter(
        [
            AssetRipperExportError("broken first batch"),
            AssetRipperExportError("broken second batch"),
        ]
    )
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    )
    output_root = _context(tmp_path).workspace.extracted_bundles
    old_output = output_root / "content" / "old.bin"
    old_output.parent.mkdir(parents=True)
    old_output.write_bytes(b"old")

    with pytest.raises(ExtractionFailureError):
        workflow.run(
            _context(tmp_path),
            [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")],
        )

    assert old_output.read_bytes() == b"old"
    assert not (output_root / "content" / "manifest.json").exists()


def test_workflow_treats_staging_permission_error_as_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = ScriptedExporter([{"Assets/a.bin": b"a"}])
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
        max_batch_bytes=4,
    )

    def deny_staging(*_args: object, **_kwargs: object) -> object:
        raise PermissionError("staging denied")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.assetripper.entry_store."
        "BundleEntryStore.resolve_many",
        deny_staging,
    )

    with pytest.raises(PermissionError):
        workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert exporter.calls == []
    assert not (_context(tmp_path).workspace.extracted_bundles).exists()


def test_workflow_treats_batch_cleanup_error_as_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = AssetRipperBundleWorkflow(
        ScriptedExporter([{"Assets/a.bin": b"a"}]),
        FakeDependencyScanner(),
        RecordingLogger(),
    )
    real_rmtree = shutil.rmtree

    def fail_batch_cleanup(
        path: str | Path,
        ignore_errors: bool = False,
        **kwargs: object,
    ) -> None:
        if Path(path).name == "batch-1":
            if ignore_errors:
                return
            raise PermissionError("batch cleanup denied")
        real_rmtree(path, ignore_errors=ignore_errors, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.assetripper.bundles.shutil.rmtree",
        fail_batch_cleanup,
    )

    with pytest.raises(PermissionError):
        workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert not (_context(tmp_path).workspace.extracted_bundles).exists()


def test_workflow_skips_invalid_component_and_transitive_dependents(
    tmp_path: Path,
) -> None:
    exporter = ScriptedExporter([{"Assets/c.bin": b"c"}])
    logger = RecordingLogger()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(
            {
                "a.zip": ("missing-cab",),
                "b.zip": ("a.bundle",),
            }
        ),
        logger,
        max_batch_bytes=4,
    )

    report = workflow.run(
        _context(tmp_path),
        [
            _bundle(tmp_path, "a.zip"),
            _bundle(tmp_path, "b.zip"),
            _bundle(tmp_path, "c.zip"),
        ],
    )

    assert exporter.calls == [(b"c" * 4,)]
    assert report.complete is False
    assert report.skipped_components == 2
    manifest_path = (
        _context(tmp_path).workspace.extracted_bundles / "content" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    skipped_entries = {
        entry
        for component in manifest["skipped_components"]
        for entry in component["entries"]
    }
    assert skipped_entries == {"a.zip::a.bundle", "b.zip::b.bundle"}
    assert manifest["summary"]["skipped_components"] == 2
    assert any(
        "missing-cab" in item["reason"] for item in manifest["skipped_components"]
    )
    assert any(
        "depends on skipped component" in item["reason"]
        for item in manifest["skipped_components"]
    )


def test_workflow_records_archive_scan_failure_and_extracts_other_components(
    tmp_path: Path,
) -> None:
    exporter = ScriptedExporter([{"Assets/b.bin": b"b"}])
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(errors={"a.zip": "archive is corrupt"}),
        RecordingLogger(),
        max_batch_bytes=4,
    )

    report = workflow.run(
        _context(tmp_path),
        [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")],
    )

    assert exporter.calls == [(b"b" * 4,)]
    assert report.complete is False
    assert report.skipped_archives == 1
    assert any(
        "1 scan source(s) skipped" in warning
        for warning in report.warnings
        if "[BUNDLE_EXTRACTION_PARTIAL]" in warning
    )
    manifest_path = (
        _context(tmp_path).workspace.extracted_bundles / "content" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    assert manifest["skipped_archives"] == [
        {"archive": "a.zip", "entry": None, "reason": "archive is corrupt"}
    ]
    assert manifest["summary"]["skipped_archives"] == 1


def test_workflow_rejects_exporter_use_of_conflict_namespace(tmp_path: Path) -> None:
    exporter = ScriptedExporter([{"_baad_conflicts/owned-by-exporter.bin": b"unsafe"}])
    workflow = AssetRipperBundleWorkflow(
        exporter,
        FakeDependencyScanner(),
        RecordingLogger(),
    )

    with pytest.raises(ExtractionFailureError):
        workflow.run(_context(tmp_path), [_bundle(tmp_path, "a.zip")])

    assert not (_context(tmp_path).workspace.extracted_bundles).exists()


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "../outside.bin",
        "Assets/../../outside.bin",
        "Assets\\outside.bin",
        "Assets/file.bin:stream",
        "C:/outside.bin",
    ),
)
def test_workflow_rejects_unsafe_export_paths(unsafe_path: str) -> None:
    with pytest.raises(AssetRipperExportError):
        AssetRipperBundleWorkflow._validate_output_path(unsafe_path)
