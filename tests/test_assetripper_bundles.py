from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.progress import ProgressMeasure, ProgressState
from ba_downloader.infrastructure.extraction.assetripper.bundles import (
    AssetRipperBundleWorkflow,
    _AssetRipperLogAggregator,
    _BundleProgressTracker,
)
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
    BundleComponent,
    BundleDependencyPlan,
    BundleEntryInput,
    BundleEntryScan,
    SerializedFileScan,
)
from ba_downloader.infrastructure.extraction.assetripper.entry_store import (
    bundle_entry_cache_identity,
)
from ba_downloader.infrastructure.extraction.assetripper.events import (
    AssetRipperAssetLifecycleEvent,
    AssetRipperEntryCacheProgressEvent,
    AssetRipperGroupCompletedEvent,
    AssetRipperGroupContext,
    AssetRipperGroupStartedEvent,
    AssetRipperLogEvent,
    AssetRipperProcessEvent,
    AssetRipperProcessorProgressEvent,
    AssetRipperProgressEvent,
    AssetRipperScanProgressEvent,
)
from ba_downloader.infrastructure.extraction.assetripper.exporter import (
    AssetRipperCollectionFailure,
    AssetRipperExportedAsset,
    AssetRipperExportedFile,
    AssetRipperExportGroup,
    AssetRipperExportResult,
    AssetRipperOutOfMemoryError,
    AssetRipperToolError,
)
from ba_downloader.infrastructure.extraction.errors import BundleExtractionError
from ba_downloader.infrastructure.files.atomic import write_json_atomic
from support.fixtures import build_execution_context


class RecordingLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def info(self, message: str) -> None:
        _ = message

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        _ = message


class RecordingProgress:
    def __init__(self) -> None:
        self.updates: list[ProgressState] = []
        self.failures: list[str] = []

    def __enter__(self) -> RecordingProgress:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def update(self, state: ProgressState) -> None:
        self.updates.append(state)
        if state.stage in {"failed", "cancelled"}:
            self.failures.append(state.message or state.stage)

    def stop(self) -> None:
        return None


class RecordingProgressFactory:
    def __init__(self) -> None:
        self.reporter = RecordingProgress()

    def create(self, *_args: object, **_kwargs: object) -> RecordingProgress:
        return self.reporter


class RecordingScanner:
    def __init__(self) -> None:
        self.calls = 0

    def scan(
        self,
        context: ExecutionContext,
        archives: list[BundleArchiveInput],
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> tuple[BundleArchiveScan, ...]:
        _ = context
        self.calls += 1
        result: list[BundleArchiveScan] = []
        for index, archive in enumerate(archives, start=1):
            with ZipFile(archive.path) as source:
                info = next(item for item in source.infolist() if not item.is_dir())
                payload = source.read(info)
            result.append(
                BundleArchiveScan(
                    archive.archive_id,
                    (
                        BundleEntryScan(
                            info.filename,
                            hashlib.sha256(payload).hexdigest(),
                            len(payload),
                            serialized_files=(
                                SerializedFileScan(f"cab-{archive.archive_id}"),
                            ),
                            crc32=info.CRC,
                        ),
                    ),
                )
            )
            if event_callback is not None:
                event_callback(
                    AssetRipperScanProgressEvent(
                        index,
                        len(archives),
                        archive.archive_id,
                    )
                )
        return tuple(result)


class RecordingExporter:
    def __init__(self, *, readable_name: str | None = None) -> None:
        self.readable_name = readable_name
        self.materialize_calls = 0
        self.materialized_node_ids: list[tuple[str, ...]] = []
        self.export_calls = 0
        self.prepare_calls = 0
        self.export_concurrency: list[int] = []
        self.export_groups: list[tuple[tuple[str, ...], ...]] = []
        self.oom_calls: set[int] = set()
        self.cancel_calls: set[int] = set()
        self.fatal_calls: set[int] = set()
        self.failed_targets: set[str] = set()
        self.unsafe_path = False

    def prepare(self, context: ExecutionContext) -> None:
        _ = context
        self.prepare_calls += 1

    def materialize_entries(
        self,
        context: ExecutionContext,
        entries: list[BundleEntryInput],
        destinations: dict[str, Path],
        *,
        concurrency: int,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> dict[str, int]:
        _ = (context, concurrency)
        self.materialize_calls += 1
        self.materialized_node_ids.append(tuple(entry.node_id for entry in entries))
        result: dict[str, int] = {}
        for index, entry in enumerate(entries, start=1):
            destination = destinations[entry.node_id]
            destination.parent.mkdir(parents=True, exist_ok=True)
            with ZipFile(entry.archive.path) as archive:
                payload = archive.read(entry.entry_path)
            destination.write_bytes(payload)
            stat = destination.stat()
            write_json_atomic(
                destination.with_suffix(f"{destination.suffix}.json"),
                {
                    "schema_version": 0,
                    "identity": bundle_entry_cache_identity(entry),
                    "mtime_ns": stat.st_mtime_ns,
                },
            )
            result[entry.node_id] = len(payload)
            if event_callback is not None:
                event_callback(
                    AssetRipperEntryCacheProgressEvent(
                        index,
                        len(entries),
                        entry.node_id,
                    )
                )
        return result

    def export_grouped(
        self,
        context: ExecutionContext,
        groups: list[AssetRipperExportGroup],
        output_directory: Path,
        *,
        concurrency: int,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> AssetRipperExportResult:
        _ = context
        self.export_calls += 1
        self.export_concurrency.append(concurrency)
        self.export_groups.append(
            tuple(tuple(item.node_id for item in group.inputs) for group in groups)
        )
        if self.export_calls in self.cancel_calls:
            raise OperationCancelledError("cancelled")
        if self.export_calls in self.oom_calls:
            raise AssetRipperOutOfMemoryError("out of memory", kind="out_of_memory")
        if self.export_calls in self.fatal_calls:
            raise AssetRipperToolError("protocol failure")
        targets = tuple(
            item.node_id for group in groups for item in group.inputs if item.target
        )
        exported: list[str] = []
        assets: list[AssetRipperExportedAsset] = []
        failures: list[AssetRipperCollectionFailure] = []
        total_groups = len(groups)
        completed_assets = 0
        for group_index, group in enumerate(groups, start=1):
            if event_callback is not None:
                event_callback(
                    AssetRipperGroupStartedEvent(
                        AssetRipperGroupContext(
                            group.group_id, group_index, total_groups
                        )
                    )
                )
            group_targets = [item for item in group.inputs if item.target]
            for item in group_targets:
                if event_callback is not None:
                    event_callback(
                        AssetRipperAssetLifecycleEvent(
                            "started",
                            hashlib.sha256(item.node_id.encode()).hexdigest()[:20],
                            Path(item.node_id.split("::", 1)[-1]).stem,
                            completed_assets,
                            len(targets),
                            AssetRipperGroupContext(
                                group.group_id, group_index, total_groups
                            ),
                        )
                    )
                completed_assets += 1
                if event_callback is not None:
                    event_callback(
                        AssetRipperAssetLifecycleEvent(
                            "completed",
                            hashlib.sha256(item.node_id.encode()).hexdigest()[:20],
                            Path(item.node_id.split("::", 1)[-1]).stem,
                            completed_assets,
                            len(targets),
                            AssetRipperGroupContext(
                                group.group_id, group_index, total_groups
                            ),
                        )
                    )
            if event_callback is not None:
                event_callback(
                    AssetRipperGroupCompletedEvent(
                        AssetRipperGroupContext(
                            group.group_id, group_index, total_groups
                        )
                    )
                )
        for index, target in enumerate(targets, start=1):
            collection = f"collection-{target}".replace("\\", "/")
            normalized = collection.strip().lower()
            class_id = 49
            path_id = int(hashlib.sha256(target.encode()).hexdigest()[:8], 16)
            identity = f"{normalized}\n{class_id}\n{path_id}"
            stable_id = hashlib.sha256(identity.encode()).hexdigest()[:20]
            if target in self.failed_targets:
                failures.append(
                    AssetRipperCollectionFailure(
                        stable_id,
                        (target,),
                        "simulated collection failure",
                    )
                )
                continue
            readable = self.readable_name or Path(target.split("::", 1)[1]).stem
            relative = (
                "../outside.bin" if self.unsafe_path else f"Assets/_MX/{readable}.bin"
            )
            output = output_directory.joinpath(*Path(relative).parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            payload = target.encode()
            output.write_bytes(payload)
            stat = output.stat()
            file = AssetRipperExportedFile(
                relative.replace("\\", "/"),
                len(payload),
                stat.st_mtime_ns - 74,
            )
            assets.append(
                AssetRipperExportedAsset(
                    stable_id,
                    "TextAsset",
                    readable,
                    collection,
                    normalized,
                    path_id,
                    class_id,
                    (target,),
                    (file,),
                )
            )
            exported.append(target)
            if event_callback is not None:
                event_callback(
                    AssetRipperProcessorProgressEvent(1, 6, "SceneDefinitionProcessor")
                )
                event_callback(
                    AssetRipperProgressEvent(
                        "exporting", index, len(targets), "exporting_assets"
                    )
                )
        return AssetRipperExportResult(
            (),
            targets,
            targets,
            tuple(exported),
            tuple(assets),
            tuple(failures),
        )


def _context(tmp_path: Path, version: str = "1") -> ExecutionContext:
    return build_execution_context(tmp_path, region="jp", version=version)


def _bundle(tmp_path: Path, name: str, payload: bytes | None = None) -> Path:
    path = tmp_path / name
    with ZipFile(path, "w") as archive:
        archive.writestr(
            f"{Path(name).stem}.bundle",
            payload if payload is not None else name.encode(),
        )
    return path


def _workflow(
    exporter: RecordingExporter,
    scanner: RecordingScanner,
    *,
    progress: RecordingProgressFactory | None = None,
) -> AssetRipperBundleWorkflow:
    return AssetRipperBundleWorkflow(
        exporter,
        scanner,
        RecordingLogger(),
        progress_factory=progress,
    )


def _manifest(context: ExecutionContext) -> dict[str, object]:
    return json.loads(
        (context.workspace.extracted_bundles / "manifest.json").read_text(
            encoding="utf8"
        )
    )


def test_full_export_uses_one_process_and_readable_assets_layout(
    tmp_path: Path,
) -> None:
    exporter = RecordingExporter()
    scanner = RecordingScanner()
    progress = RecordingProgressFactory()
    context = _context(tmp_path)

    report = _workflow(exporter, scanner, progress=progress).run(
        context,
        [_bundle(tmp_path, "b.zip"), _bundle(tmp_path, "a.zip")],
        concurrency=7,
    )

    manifest = _manifest(context)
    assert exporter.export_calls == 1
    assert exporter.export_concurrency == [7]
    assert exporter.materialize_calls == 1
    assert report.total_batches == 1
    assert report.succeeded_batches == 1
    assert manifest["schema_version"] == 0
    assert manifest["layout"] == "assetripper-readable"
    assert "runs" not in manifest
    assert "current_revision" not in json.dumps(manifest)
    assert (context.workspace.extracted_bundles / "Assets/_MX/a.bin").is_file()
    assert (context.workspace.extracted_bundles / "Assets/_MX/b.bin").is_file()
    assert not any(
        path.name == "assets" for path in context.workspace.extracted_bundles.iterdir()
    )
    assert {item.stage for item in progress.reporter.updates} >= {
        "scanning",
        "cache_fill",
        "processing",
        "exporting",
    }
    assert any(
        item.stage == "processing"
        and item.current is not None
        and item.current.unit == "processors"
        for item in progress.reporter.updates
    )


def test_filtered_export_resolves_dependencies_only_between_direct_members(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    direct_path = _bundle(tmp_path, "direct.zip", b"direct")
    dependency_path = _bundle(tmp_path, "dependency.zip", b"dependency")
    archives = (
        BundleArchiveInput.from_path(
            direct_path,
            archive_id="Bundle/FullPatch_044.zip#direct.bundle",
        ),
        BundleArchiveInput.from_path(
            dependency_path,
            archive_id="Bundle/FullPatch_044.zip#dependency.bundle",
        ),
    )

    class DependencyScanner:
        def scan(
            self,
            _context: ExecutionContext,
            inputs: list[BundleArchiveInput],
            _event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
        ) -> tuple[BundleArchiveScan, ...]:
            payloads = {
                "Bundle/FullPatch_044.zip#direct.bundle": (
                    "direct.bundle",
                    b"direct",
                    SerializedFileScan("cab-direct", ("cab-dependency",)),
                ),
                "Bundle/FullPatch_044.zip#dependency.bundle": (
                    "dependency.bundle",
                    b"dependency",
                    SerializedFileScan("cab-dependency"),
                ),
            }
            return tuple(
                BundleArchiveScan(
                    item.archive_id,
                    (
                        BundleEntryScan(
                            payloads[item.archive_id][0],
                            hashlib.sha256(payloads[item.archive_id][1]).hexdigest(),
                            len(payloads[item.archive_id][1]),
                            serialized_files=(payloads[item.archive_id][2],),
                        ),
                    ),
                )
                for item in inputs
            )

    exporter = RecordingExporter()
    workflow = AssetRipperBundleWorkflow(
        exporter,
        DependencyScanner(),  # type: ignore[arg-type]
        RecordingLogger(),
    )

    workflow.run(context, archives, concurrency=2, filtered=True)

    materialized = set(exporter.materialized_node_ids[0])
    assert materialized == {
        "Bundle/FullPatch_044.zip#direct.bundle::direct.bundle",
        "Bundle/FullPatch_044.zip#dependency.bundle::dependency.bundle",
    }
    manifest = _manifest(context)
    assert manifest["status"] == "complete"
    assert len(manifest["assets"]) == 2


def test_filtered_log_aggregator_summarizes_missing_dependencies() -> None:
    logger = RecordingLogger()
    aggregator = _AssetRipperLogAggregator(logger, filtered=True)
    first = "Dependency 'archive:/CAB-first/CAB-first' wasn't found"
    second = "Dependency 'archive:/CAB-second/CAB-second' wasn't found"

    aggregator.handle(AssetRipperLogEvent("warning", "Import", first))
    aggregator.handle(AssetRipperLogEvent("warning", "Import", second))
    aggregator.handle(AssetRipperLogEvent("warning", "Import", first))
    aggregator.handle(AssetRipperLogEvent("warning", "Import", "another warning"))
    aggregator.flush()

    assert logger.warnings == [
        "AssetRipper Import: another warning",
        "AssetRipper Import: 2 unique external dependencies were not found "
        "(3 reports suppressed); this is expected in filtered bundle extraction "
        "because only directly selected bundle members are loaded.",
    ]


def test_full_log_aggregator_keeps_missing_dependency_warning() -> None:
    logger = RecordingLogger()
    aggregator = _AssetRipperLogAggregator(logger)
    message = "Dependency 'archive:/CAB-first/CAB-first' wasn't found"

    aggregator.handle(AssetRipperLogEvent("warning", "Import", message))
    aggregator.flush()

    assert logger.warnings == [f"AssetRipper Import: {message}"]


def test_group_progress_uses_completed_groups_for_eta_and_oldest_active_asset() -> None:
    progress = RecordingProgress()
    clock_value = 0.0

    def clock() -> float:
        return clock_value

    tracker = _BundleProgressTracker(
        progress,
        _AssetRipperLogAggregator(RecordingLogger()),
        total_groups=3,
        clock=clock,
    )
    first = AssetRipperGroupContext("group-01", 1, 3)
    second = AssetRipperGroupContext("group-02", 2, 3)
    third = AssetRipperGroupContext("group-03", 3, 3)

    tracker.handle(AssetRipperGroupStartedEvent(first))
    tracker.handle(AssetRipperProgressEvent("loading", 5, 10, "loading_files", first))
    assert progress.updates[-1].overall == ProgressMeasure(0, 3, "groups")
    assert progress.updates[-1].eta_seconds is None

    clock_value = 10.0
    tracker.handle(AssetRipperGroupCompletedEvent(first))
    assert progress.updates[-1].overall == ProgressMeasure(1, 3, "groups")
    assert progress.updates[-1].eta_seconds == 20.0

    tracker.handle(AssetRipperGroupStartedEvent(second))
    tracker.handle(
        AssetRipperAssetLifecycleEvent(
            "started", "asset-a", "Cafe_CH0347", 0, 2, second
        )
    )
    tracker.handle(
        AssetRipperAssetLifecycleEvent(
            "started", "asset-b", "Cafe_CH0348", 0, 2, second
        )
    )
    tracker.handle(
        AssetRipperAssetLifecycleEvent(
            "completed", "asset-a", "Cafe_CH0347", 1, 2, second
        )
    )
    state = progress.updates[-1]
    assert state.overall == ProgressMeasure(1, 3, "groups")
    assert state.current == ProgressMeasure(1, 2, "assets")
    assert state.item == "Cafe_CH0348"
    assert state.eta_seconds == 20.0

    clock_value = 20.0
    tracker.handle(AssetRipperGroupCompletedEvent(second))
    assert progress.updates[-1].overall == ProgressMeasure(2, 3, "groups")
    assert progress.updates[-1].eta_seconds == 10.0
    tracker.handle(AssetRipperGroupStartedEvent(third))
    clock_value = 30.0
    tracker.handle(AssetRipperGroupCompletedEvent(third))
    assert progress.updates[-1].overall == ProgressMeasure(3, 3, "groups")
    assert progress.updates[-1].eta_seconds is None


def test_stream_groups_keep_components_whole_at_measured_limit(
    tmp_path: Path,
) -> None:
    archive = BundleArchiveInput.from_path(_bundle(tmp_path, "source.zip"))
    components = tuple(
        BundleComponent(
            f"component-{index:03d}",
            (
                BundleEntryInput(
                    archive,
                    f"entry-{index:03d}.bundle",
                    f"{index:064x}",
                    1,
                ),
            ),
            (),
            (),
            (),
        )
        for index in range(513)
    )
    plan = BundleDependencyPlan(components, (), (), ())

    batches = _workflow(RecordingExporter(), RecordingScanner())._stream_batches(plan)

    assert [len(batch.target_entries) for batch in batches] == [512, 1]
    assert {
        component.component_id
        for batch in batches
        for component in batch.target_components
    } == {component.component_id for component in components}


def test_dependency_topology_reduces_repeated_closure_bytes(tmp_path: Path) -> None:
    archive = BundleArchiveInput.from_path(_bundle(tmp_path, "source.zip"))

    def component(
        component_id: str,
        *,
        size: int = 1,
        dependencies: tuple[str, ...] = (),
    ) -> BundleComponent:
        return BundleComponent(
            component_id,
            (
                BundleEntryInput(
                    archive,
                    f"{component_id}.bundle",
                    hashlib.sha256(component_id.encode()).hexdigest(),
                    size,
                ),
            ),
            dependencies,
            (),
            (),
        )

    shared = component("shared", size=100)
    dependents = tuple(
        component(name, dependencies=(shared.component_id,))
        for name in ("a", "c", "e", "g")
    )
    independent = tuple(component(name) for name in ("b", "d", "f", "h"))
    plan = BundleDependencyPlan(
        (*dependents, *independent, shared),
        (),
        (),
        (),
    )
    workflow = _workflow(RecordingExporter(), RecordingScanner())
    lexical = tuple(
        sorted(
            plan.components,
            key=lambda item: item.entries[0].node_id.casefold(),
        )
    )
    lexical_batches = workflow._group_components(
        plan,
        lexical,
        target_entry_limit=2,
    )
    optimized = workflow._stream_batches(plan, target_entry_limit=2)
    reordered = workflow._stream_batches(
        BundleDependencyPlan(tuple(reversed(plan.components)), (), (), ()),
        target_entry_limit=2,
    )

    assert sum(batch.total_bytes for batch in optimized) < sum(
        batch.total_bytes for batch in lexical_batches
    )
    assert tuple(batch.target_node_ids for batch in optimized) == tuple(
        batch.target_node_ids for batch in reordered
    )
    target_ids = [node_id for batch in optimized for node_id in batch.target_node_ids]
    assert len(target_ids) == len(set(target_ids))
    assert {
        component.component_id
        for batch in optimized
        for component in batch.target_components
    } == {component.component_id for component in plan.components}
    for batch in optimized:
        loaded_ids = {item.component_id for item in batch.loaded_components}
        for target in batch.target_components:
            assert set(target.dependency_component_ids) <= loaded_ids


def test_warm_run_validates_output_and_skips_every_tool(tmp_path: Path) -> None:
    exporter = RecordingExporter()
    scanner = RecordingScanner()
    context = _context(tmp_path)
    archive = _bundle(tmp_path, "a.zip")
    workflow = _workflow(exporter, scanner)

    workflow.run(context, [archive], concurrency=2)
    workflow.run(context, [archive], concurrency=8)

    assert scanner.calls == 1
    assert exporter.materialize_calls == 1
    assert exporter.prepare_calls == 1
    assert exporter.export_calls == 1


def test_nonzero_manifest_is_rebuilt_without_reuse(tmp_path: Path) -> None:
    exporter = RecordingExporter()
    scanner = RecordingScanner()
    context = _context(tmp_path)
    archive = _bundle(tmp_path, "a.zip")
    workflow = _workflow(exporter, scanner)

    workflow.run(context, [archive], concurrency=2)
    legacy = _manifest(context)
    legacy["schema_version"] = 10
    write_json_atomic(
        context.workspace.extracted_bundles / "manifest.json",
        legacy,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    workflow.run(context, [archive], concurrency=8)

    rebuilt = _manifest(context)
    assert rebuilt["schema_version"] == 0
    assert "content_fingerprint" in rebuilt
    assert scanner.calls == 2
    assert exporter.export_calls == 2


def test_actual_oom_fails_once_and_preserves_old_output(tmp_path: Path) -> None:
    exporter = RecordingExporter()
    exporter.oom_calls.add(1)
    context = _context(tmp_path)
    old_output = context.workspace.extracted_bundles / "Assets/old.bin"
    old_output.parent.mkdir(parents=True)
    old_output.write_bytes(b"old")

    with pytest.raises(BundleExtractionError):
        _workflow(exporter, RecordingScanner()).run(
            context,
            [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")],
            concurrency=12,
        )

    assert exporter.export_calls == 1
    assert exporter.export_concurrency == [12]
    assert old_output.read_bytes() == b"old"
    assert not (context.workspace.extracted_bundles / "manifest.json").exists()


def test_fatal_export_failure_preserves_incompatible_layout(tmp_path: Path) -> None:
    context = _context(tmp_path)
    output_root = context.workspace.extracted_bundles
    previous = output_root / "assets/previous/file.bin"
    previous.parent.mkdir(parents=True)
    previous.write_bytes(b"old")
    write_json_atomic(output_root / "manifest.json", {"schema_version": 11})
    exporter = RecordingExporter()
    exporter.fatal_calls.add(1)

    with pytest.raises(BundleExtractionError):
        _workflow(exporter, RecordingScanner()).run(
            context,
            [_bundle(tmp_path, "a.zip")],
            concurrency=1,
        )

    assert previous.read_bytes() == b"old"
    assert not any(path.name == "Assets" for path in output_root.iterdir())
    assert _manifest(context)["schema_version"] == 11


def test_success_replaces_incompatible_lowercase_layout(tmp_path: Path) -> None:
    context = _context(tmp_path)
    previous = context.workspace.extracted_bundles / "assets/previous/file.bin"
    previous.parent.mkdir(parents=True)
    previous.write_bytes(b"old")

    _workflow(RecordingExporter(), RecordingScanner()).run(
        context,
        [_bundle(tmp_path, "a.zip")],
        concurrency=1,
    )

    assert not previous.exists()
    assert (context.workspace.extracted_bundles / "Assets/_MX/a.bin").is_file()


def test_success_replaces_unitypy_handler_output(tmp_path: Path) -> None:
    context = _context(tmp_path)
    output_root = context.workspace.extracted_bundles
    previous = output_root / "Assets/Texture2D/previous.png"
    previous.parent.mkdir(parents=True)
    previous.write_bytes(b"old")
    write_json_atomic(
        output_root / "manifest.json",
        {
            "schema_version": 0,
            "layout": "unitypy-readable",
            "assets": {},
            "failures": [],
        },
    )

    _workflow(RecordingExporter(), RecordingScanner()).run(
        context,
        [_bundle(tmp_path, "a.zip")],
        concurrency=1,
        filtered=True,
    )

    assert not previous.exists()
    assert (output_root / "Assets/_MX/a.bin").is_file()
    assert _manifest(context)["layout"] == "assetripper-readable"


def test_first_filtered_run_replaces_nonzero_public_output(tmp_path: Path) -> None:
    context = _context(tmp_path)
    output_root = context.workspace.extracted_bundles
    previous = output_root / "Assets/_MX/previous.bin"
    previous.parent.mkdir(parents=True)
    previous.write_bytes(b"old")
    write_json_atomic(output_root / "manifest.json", {"schema_version": 11})

    _workflow(RecordingExporter(), RecordingScanner()).run(
        context,
        [_bundle(tmp_path, "a.zip")],
        concurrency=1,
        filtered=True,
    )

    assert not previous.exists()
    assert (output_root / "Assets/_MX/a.bin").is_file()
    assert _manifest(context)["schema_version"] == 0


def test_filtered_merge_preserves_existing_and_allocates_native_suffix(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    first = RecordingExporter(readable_name="shared")
    _workflow(first, RecordingScanner()).run(
        context,
        [_bundle(tmp_path, "a.zip")],
        concurrency=1,
    )
    second = RecordingExporter(readable_name="shared")

    _workflow(second, RecordingScanner()).run(
        context,
        [_bundle(tmp_path, "b.zip")],
        concurrency=3,
        filtered=True,
    )

    assets_root = context.workspace.extracted_bundles / "Assets/_MX"
    assert (assets_root / "shared.bin").is_file()
    assert (assets_root / "shared_0.bin").is_file()
    assert len(_manifest(context)["assets"]) == 2


def test_collection_failure_publishes_partial_result(tmp_path: Path) -> None:
    context = _context(tmp_path)
    a = _bundle(tmp_path, "a.zip")
    b = _bundle(tmp_path, "b.zip")
    exporter = RecordingExporter()
    exporter.failed_targets.add("a.zip::a.bundle")
    progress = RecordingProgressFactory()

    report = _workflow(exporter, RecordingScanner(), progress=progress).run(
        context,
        [a, b],
        concurrency=2,
    )

    manifest = _manifest(context)
    assert manifest["status"] == "partial"
    assert len(manifest["failures"]) == 1
    assert len(manifest["assets"]) == 1
    assert report.warnings
    assert progress.reporter.updates[-1].stage == "complete"
    assert progress.reporter.updates[-1].failures == 1
    assert not (context.workspace.extracted_bundles / "Assets/_MX/a.bin").exists()
    assert (context.workspace.extracted_bundles / "Assets/_MX/b.bin").is_file()


def test_modified_output_invalidates_warm_run_and_is_replaced(tmp_path: Path) -> None:
    context = _context(tmp_path)
    archive = _bundle(tmp_path, "a.zip")
    exporter = RecordingExporter()
    workflow = _workflow(exporter, RecordingScanner())
    workflow.run(context, [archive], concurrency=1)
    output = context.workspace.extracted_bundles / "Assets/_MX/a.bin"
    output.write_bytes(b"tampered")

    workflow.run(context, [archive], concurrency=1)

    assert exporter.export_calls == 2
    assert output.read_bytes() == b"a.zip::a.bundle"


def test_manifest_commit_failure_rolls_back_directory_swap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    archive = _bundle(tmp_path, "a.zip", b"one")
    workflow = _workflow(RecordingExporter(), RecordingScanner())
    workflow.run(context, [archive], concurrency=1)
    output = context.workspace.extracted_bundles / "Assets/_MX/a.bin"
    old_output = output.read_bytes()
    old_manifest = (context.workspace.extracted_bundles / "manifest.json").read_bytes()
    _bundle(tmp_path, "a.zip", b"two")

    from ba_downloader.infrastructure.extraction.assetripper import bundles

    real_write = bundles.write_json_atomic

    def fail_manifest(path: Path, payload: object, **kwargs: object) -> None:
        if path.name == "manifest.json":
            raise OSError("simulated manifest failure")
        real_write(path, payload, **kwargs)

    monkeypatch.setattr(bundles, "write_json_atomic", fail_manifest)
    with pytest.raises(BundleExtractionError):
        workflow.run(context, [archive], concurrency=1)

    assert output.read_bytes() == old_output
    assert (
        context.workspace.extracted_bundles / "manifest.json"
    ).read_bytes() == old_manifest


def test_cancelled_export_cleans_staging_and_preserves_output(tmp_path: Path) -> None:
    context = _context(tmp_path)
    output = context.workspace.extracted_bundles / "Assets/old.bin"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"old")
    exporter = RecordingExporter()
    exporter.cancel_calls.add(1)

    with pytest.raises(OperationCancelledError):
        _workflow(exporter, RecordingScanner()).run(
            context,
            [_bundle(tmp_path, "a.zip")],
            concurrency=1,
        )

    assert output.read_bytes() == b"old"
    assert not list(context.workspace.extracted.parent.glob(".bundles-staging-*"))


def test_unsafe_export_path_is_rejected_before_publish(tmp_path: Path) -> None:
    context = _context(tmp_path)
    exporter = RecordingExporter()
    exporter.unsafe_path = True

    with pytest.raises(BundleExtractionError):
        _workflow(exporter, RecordingScanner()).run(
            context,
            [_bundle(tmp_path, "a.zip")],
            concurrency=1,
        )

    assert not (context.workspace.extracted_bundles / "manifest.json").exists()


def test_manifest_uses_file_metadata_without_content_hash(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _workflow(RecordingExporter(), RecordingScanner()).run(
        context,
        [_bundle(tmp_path, "a.zip")],
        concurrency=1,
    )
    manifest = json.loads(
        (context.workspace.extracted_bundles / "manifest.json").read_text(
            encoding="utf8"
        )
    )
    files = next(iter(manifest["assets"].values()))["files"]

    assert all("sha256" not in item for item in files)


def test_publish_writes_one_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from ba_downloader.infrastructure.extraction.assetripper import bundles

    real_write = bundles.write_json_atomic
    writes: list[str] = []

    def record_write(path: Path, payload: object, **kwargs: object) -> None:
        writes.append(path.name)
        real_write(path, payload, **kwargs)

    monkeypatch.setattr(bundles, "write_json_atomic", record_write)
    _workflow(RecordingExporter(), RecordingScanner()).run(
        _context(tmp_path),
        [_bundle(tmp_path, "a.zip"), _bundle(tmp_path, "b.zip")],
        concurrency=2,
    )

    assert writes.count("manifest.json") == 1
