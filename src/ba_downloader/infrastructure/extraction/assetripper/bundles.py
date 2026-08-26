from __future__ import annotations

import hashlib
import heapq
import json
import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from time import monotonic
from typing import Protocol
from uuid import uuid4

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import (
    CancellationPort,
    NeverCancelled,
    OperationCancelledError,
)
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import (
    ProgressGroup,
    ProgressMeasure,
    ProgressReporterFactoryPort,
    ProgressReporterPort,
    ProgressStage,
    ProgressState,
)
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
    BundleComponent,
    BundleDependencyPlan,
    BundleDependencyPlanner,
    BundleEntryInput,
    BundleExportBatch,
)
from ba_downloader.infrastructure.extraction.assetripper.entry_store import (
    BundleEntryMaterializerPort,
    BundleEntryStore,
    BundleEntryStoreResult,
    BundleEntryStoreSpaceError,
    bundle_entry_store_root,
)
from ba_downloader.infrastructure.extraction.assetripper.events import (
    SERIALIZE_REFERENCE_UNSUPPORTED_MESSAGE,
    AssetRipperAssetLifecycleEvent,
    AssetRipperEntryCacheProgressEvent,
    AssetRipperGroupCompletedEvent,
    AssetRipperGroupContext,
    AssetRipperGroupStartedEvent,
    AssetRipperHeartbeatEvent,
    AssetRipperLogEvent,
    AssetRipperPhaseEvent,
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
    AssetRipperExportInput,
    AssetRipperExportResult,
    AssetRipperToolError,
    assetripper_dependency_scan_cache_key,
    assetripper_exported_content_fingerprint,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    AssetRipperSourceError,
)
from ba_downloader.infrastructure.extraction.errors import BundleExtractionError
from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    recover_replaced_directory,
    write_json_atomic,
)
from ba_downloader.infrastructure.files.lock import (
    InterprocessFileLock,
    InterprocessLockBusyError,
)
from ba_downloader.infrastructure.progress import NullProgressReporterFactory

_BUNDLE_MANIFEST_SCHEMA_VERSION = 0
_BUNDLE_LAYOUT = "assetripper-readable"
_PROCESSING_PROFILE = "readable-playable"
_STREAM_GROUP_TARGET_ENTRY_LIMIT = 512
_STREAM_GROUPING_PROFILE = "dependency-topology"


def bundle_extraction_lock_path(context: ExecutionContext) -> Path:
    return (
        context.workspace.locks
        / context.region
        / context.platform
        / "bundle-extraction.lock"
    )


@dataclass(frozen=True, slots=True)
class BundleExtractionReport:
    warnings: tuple[str, ...] = ()
    total_batches: int = 0
    succeeded_batches: int = 0
    failed_batches: int = 0
    skipped_archives: int = 0
    skipped_components: int = 0


@dataclass(frozen=True, slots=True)
class _PreparedDependencyPlan:
    executable: BundleDependencyPlan
    skipped: tuple[tuple[BundleComponent, str], ...]


class _BundleExporter(BundleEntryMaterializerPort, Protocol):
    def prepare(self, context: ExecutionContext) -> None: ...

    def export_grouped(
        self,
        context: ExecutionContext,
        groups: list[AssetRipperExportGroup],
        output_directory: Path,
        *,
        concurrency: int,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> AssetRipperExportResult: ...


class _DependencyScanner(Protocol):
    def scan(
        self,
        context: ExecutionContext,
        archives: list[BundleArchiveInput],
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> tuple[BundleArchiveScan, ...]: ...


class _AssetRipperLogAggregator:
    def __init__(self, logger: LoggerPort) -> None:
        self._logger = logger
        self._serialize_reference_count = 0

    def handle(self, event: AssetRipperLogEvent) -> None:
        if event.message == SERIALIZE_REFERENCE_UNSUPPORTED_MESSAGE:
            self._serialize_reference_count += 1
            return
        message = f"AssetRipper {event.category}: {event.message}"
        if event.level == "warning":
            self._logger.warn(message)
        else:
            self._logger.error(message)

    def flush(self) -> None:
        if self._serialize_reference_count:
            self._logger.warn(
                "AssetRipper Import: SerializeReference is not supported for "
                f"{self._serialize_reference_count} MonoBehaviour assets; "
                "structured fields were not parsed."
            )


class _BundleProgressTracker:
    _LABEL = "Bundles"

    def __init__(
        self,
        progress: ProgressReporterPort,
        logs: _AssetRipperLogAggregator,
        *,
        total_groups: int,
        clock: Callable[[], float],
    ) -> None:
        self._progress = progress
        self._logs = logs
        self._total = total_groups
        self._clock = clock
        self._completed = 0
        self._started_at: dict[int, float] = {}
        self._durations: list[float] = []
        self._active_assets: dict[str, tuple[int, str]] = {}
        self._asset_sequence = 0
        self._group: AssetRipperGroupContext | None = None
        self._current: ProgressMeasure | None = None
        self._item: str | None = None
        self._stage = "loading"
        self._failures = 0

    def handle(self, event: AssetRipperProcessEvent) -> None:
        if isinstance(event, AssetRipperLogEvent):
            self._logs.handle(event)
            return
        if isinstance(event, AssetRipperGroupStartedEvent):
            self._group = event.group
            self._started_at.setdefault(event.group.index, self._clock())
            self._active_assets.clear()
            self._emit("loading", group=event.group)
            return
        if isinstance(event, AssetRipperGroupCompletedEvent):
            started = self._started_at.pop(event.group.index, None)
            if started is not None:
                self._durations.append(max(self._clock() - started, 0.0))
            self._completed = max(self._completed, min(event.group.index, self._total))
            self._active_assets.clear()
            self._emit("exporting", group=event.group)
            return
        group = getattr(event, "group", None) or self._group
        if isinstance(event, AssetRipperAssetLifecycleEvent):
            if event.lifecycle == "started":
                self._asset_sequence += 1
                self._active_assets.setdefault(
                    event.stable_id, (self._asset_sequence, event.item)
                )
            else:
                self._active_assets.pop(event.stable_id, None)
            oldest = min(self._active_assets.values(), default=None)
            self._emit(
                "exporting",
                current=ProgressMeasure(event.current, event.total, "assets"),
                group=event.group,
                item=oldest[1] if oldest is not None else None,
            )
        elif isinstance(event, AssetRipperProcessorProgressEvent):
            self._emit(
                "processing",
                current=ProgressMeasure(event.current, event.total, "processors"),
                group=group,
                item=event.processor.removesuffix("Processor"),
            )
        elif isinstance(event, AssetRipperProgressEvent):
            self._emit(
                event.phase,
                current=ProgressMeasure(
                    event.current,
                    event.total,
                    "assets" if event.phase == "exporting" else "inputs",
                ),
                group=group,
            )
        elif isinstance(event, AssetRipperHeartbeatEvent):
            self._emit(
                "processing", current=self._current, group=group, item=self._item
            )
        elif isinstance(event, AssetRipperPhaseEvent):
            self._emit(event.phase, group=group)

    def finish_stage(
        self,
        stage: ProgressStage,
        *,
        failures: int | None = None,
    ) -> None:
        self._completed = self._total
        if failures is not None:
            self._failures = failures
        self._emit(stage, group=None, eta=False)

    def _emit(
        self,
        stage: ProgressStage,
        *,
        current: ProgressMeasure | None = None,
        group: AssetRipperGroupContext | None = None,
        item: str | None = None,
        eta: bool = True,
    ) -> None:
        self._stage = stage
        self._current = current
        self._group = group
        self._item = item
        eta_seconds = None
        if eta and self._durations and self._completed < self._total:
            eta_seconds = (sum(self._durations) / len(self._durations)) * (
                self._total - self._completed
            )
        progress_group = (
            ProgressGroup(group.group_id, group.index, group.total)
            if group is not None
            else None
        )
        self._progress.update(
            ProgressState(
                self._LABEL,
                stage,
                overall=ProgressMeasure(self._completed, self._total, "groups"),
                current=current,
                group=progress_group,
                item=item,
                failures=self._failures,
                eta_seconds=eta_seconds,
            )
        )


class AssetRipperBundleWorkflow:
    def __init__(
        self,
        exporter: _BundleExporter,
        dependency_scanner: _DependencyScanner,
        logger: LoggerPort,
        *,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._exporter = exporter
        self._dependency_scanner = dependency_scanner
        self._logger = logger
        self._progress_factory = progress_factory or NullProgressReporterFactory()
        self._cancellation = cancellation or NeverCancelled()
        self._clock = clock

    def run(
        self,
        context: ExecutionContext,
        inputs: Sequence[Path | BundleArchiveInput],
        *,
        concurrency: int,
        filtered: bool = False,
    ) -> BundleExtractionReport:
        if concurrency <= 0:
            raise ValueError("Bundle extraction concurrency must be positive.")
        try:
            with InterprocessFileLock(
                bundle_extraction_lock_path(context),
                operation="bundle extraction",
            ):
                return self._run_locked(
                    context,
                    inputs,
                    concurrency=concurrency,
                    filtered=filtered,
                )
        except OperationCancelledError:
            raise
        except InterprocessLockBusyError as exc:
            raise BundleExtractionError(str(exc)) from exc
        except BundleExtractionError:
            raise
        except (
            AssetRipperSourceError,
            AssetRipperToolError,
            BundleEntryStoreSpaceError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exc:
            raise BundleExtractionError(
                f"Bundle extraction could not continue: {exc}"
            ) from exc

    def _run_locked(
        self,
        context: ExecutionContext,
        inputs: Sequence[Path | BundleArchiveInput],
        *,
        concurrency: int,
        filtered: bool,
    ) -> BundleExtractionReport:
        self._cancellation.raise_if_cancelled()
        output_root = context.workspace.extracted_bundles
        output_root.parent.mkdir(parents=True, exist_ok=True)
        recover_replaced_directory(output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        self._cleanup_staging(output_root)
        archives = self._normalize_inputs(context, inputs)
        if not archives:
            return BundleExtractionReport()
        manifest = self._load_manifest(output_root / "manifest.json", context)
        run_fingerprint = self._run_fingerprint(context, archives, filtered=filtered)
        warm = self._load_warm_report(
            output_root,
            manifest,
            run_fingerprint,
        )
        if warm is not None:
            return warm

        warnings: list[str] = []
        with self._progress_factory.create(
            ProgressState(
                "Bundles",
                "scanning",
                current=ProgressMeasure(0, len(archives), "archives"),
                message="Scanning dependencies",
            )
        ) as progress:
            try:
                progress.update(
                    ProgressState(
                        "Bundles",
                        "scanning",
                        current=ProgressMeasure(0, len(archives), "archives"),
                        message="Scanning dependencies",
                    )
                )
                scans = self._dependency_scanner.scan(
                    context,
                    list(archives),
                    lambda event: self._handle_scan_event(progress, event),
                )
                plan = BundleDependencyPlanner(
                    self._cancellation.raise_if_cancelled
                ).build(archives, scans)
                prepared = self._prepare_plan(plan)
                warnings.extend(self._plan_warnings(prepared))
                if not prepared.executable.components:
                    raise BundleExtractionError(
                        "Bundle dependency scan found no complete exportable inputs."
                    )

                entries = self._unique_entries(prepared.executable.entries)
                progress.update(
                    ProgressState(
                        "Bundles",
                        "cache_fill",
                        current=ProgressMeasure(0, len(entries), "entries"),
                        message="Preparing entry cache",
                    )
                )
                store = BundleEntryStore(
                    bundle_entry_store_root(context),
                    materializer=self._exporter,
                    cancellation=self._cancellation,
                )
                resolved = store.resolve_many(
                    context,
                    entries,
                    concurrency=concurrency,
                    event_callback=lambda event: self._handle_cache_event(
                        progress, event
                    ),
                )
                resolved_by_node = {
                    entry.node_id: item
                    for entry, item in zip(entries, resolved, strict=True)
                }
                self._exporter.prepare(context)
                job_root = output_root.parent / f".bundles-staging-{uuid4().hex}"
                job_root.mkdir(parents=True)
                try:
                    result, batches, aggregate, tracker = self._export_streamed(
                        context,
                        prepared.executable,
                        resolved_by_node,
                        job_root,
                        progress,
                        concurrency=concurrency,
                    )
                    tracker.finish_stage("validating")
                    result = self._validate_result(aggregate, result, job_root)
                    merged_assets, collection_failures = self._merge_results(
                        [result], job_root
                    )
                    tracker.finish_stage(
                        "validating",
                        failures=len(collection_failures),
                    )
                    if collection_failures:
                        warnings.append(
                            "AssetRipper could not export "
                            f"{len(collection_failures)} collection(s); successful "
                            "outputs were published."
                        )
                    exported_target_ids = {
                        target_id for target_id in result.exported_target_ids
                    }
                    requested_target_ids = {
                        entry.node_id for entry in prepared.executable.entries
                    }
                    missing_coverage = requested_target_ids - exported_target_ids
                    failed_coverage = {
                        target_id
                        for failure in collection_failures
                        for target_id in failure.source_target_ids
                    }
                    if missing_coverage - failed_coverage:
                        raise AssetRipperToolError(
                            "AssetRipper result did not account for every target input."
                        )
                    new_manifest, publish_assets = self._build_manifest(
                        context,
                        manifest,
                        merged_assets,
                        collection_failures,
                        prepared.executable,
                        run_fingerprint,
                        filtered=filtered,
                        status=("partial" if collection_failures else "complete"),
                    )
                    publish_root = self._prepare_publish_tree(
                        output_root,
                        job_root,
                        manifest,
                        publish_assets,
                        filtered=filtered,
                    )
                    tracker.finish_stage("publishing")
                    self._publish_directory_transaction(
                        output_root,
                        publish_root,
                        new_manifest,
                    )
                    tracker.finish_stage("complete")
                finally:
                    shutil.rmtree(job_root, ignore_errors=True)
            except OperationCancelledError:
                progress.update(
                    ProgressState(
                        "Bundles",
                        "cancelled",
                        message="Bundle extraction cancelled",
                    )
                )
                raise
            except BaseException:
                progress.update(
                    ProgressState(
                        "Bundles",
                        "failed",
                        message="Bundle extraction failed",
                    )
                )
                raise

        return BundleExtractionReport(
            tuple(warnings),
            len(batches),
            len(batches),
            0,
            len(
                {
                    failure.archive_id
                    for failure in plan.scan_failures
                    if failure.entry_path is None
                }
            ),
            len(prepared.skipped),
        )

    def _export_streamed(
        self,
        context: ExecutionContext,
        plan: BundleDependencyPlan,
        resolved_by_node: dict[str, BundleEntryStoreResult],
        job_root: Path,
        progress: ProgressReporterPort,
        *,
        concurrency: int,
    ) -> tuple[
        AssetRipperExportResult,
        tuple[BundleExportBatch, ...],
        BundleExportBatch,
        _BundleProgressTracker,
    ]:
        batches = self._stream_batches(plan)
        groups: list[AssetRipperExportGroup] = []
        for batch in batches:
            target_ids = set(batch.target_node_ids)
            groups.append(
                AssetRipperExportGroup(
                    batch.batch_id,
                    tuple(
                        AssetRipperExportInput(
                            resolved_by_node[entry.node_id].path,
                            entry.node_id,
                            entry.node_id in target_ids,
                        )
                        for entry in self._unique_entries(batch.entries)
                    ),
                )
            )
        aggregate = self._batch_for_targets(plan, plan.components, batch_id="stream")
        log_aggregator = _AssetRipperLogAggregator(self._logger)
        tracker = _BundleProgressTracker(
            progress,
            log_aggregator,
            total_groups=len(groups),
            clock=self._clock,
        )
        try:
            self._cancellation.raise_if_cancelled()
            progress.update(
                ProgressState(
                    "Bundles",
                    "loading",
                    overall=ProgressMeasure(0, len(groups), "groups"),
                    message="Loading bundle groups",
                )
            )
            result = self._exporter.export_grouped(
                context,
                groups,
                job_root,
                concurrency=concurrency,
                event_callback=tracker.handle,
            )
        finally:
            log_aggregator.flush()
        return result, batches, aggregate, tracker

    def _validate_result(
        self,
        batch: BundleExportBatch,
        result: AssetRipperExportResult,
        staging_root: Path,
    ) -> AssetRipperExportResult:
        expected = set(batch.target_node_ids)
        if set(result.requested_target_ids) != expected:
            raise AssetRipperToolError(
                "AssetRipper result target set does not match the export request."
            )
        if not set(result.exported_target_ids) <= expected:
            raise AssetRipperToolError(
                "AssetRipper result contains unexpected target coverage."
            )
        normalized_assets: list[AssetRipperExportedAsset] = []
        for asset in result.assets:
            normalized_files: list[AssetRipperExportedFile] = []
            for item in asset.files:
                path = self._safe_child(staging_root, item.path)
                if not PurePosixPath(item.path).parts[0].casefold() == "assets":
                    raise AssetRipperToolError(
                        "AssetRipper output is outside the Assets layout."
                    )
                try:
                    stat = path.stat()
                except OSError as exc:
                    raise AssetRipperToolError(
                        "AssetRipper did not publish a declared output file."
                    ) from exc
                if stat.st_size != item.size:
                    raise AssetRipperToolError(
                        "AssetRipper output metadata changed before publication."
                    )
                normalized_files.append(replace(item, mtime_ns=stat.st_mtime_ns))
            normalized_assets.append(replace(asset, files=tuple(normalized_files)))
        return replace(result, assets=tuple(normalized_assets))

    def _merge_results(
        self,
        results: Sequence[AssetRipperExportResult],
        staging_root: Path,
    ) -> tuple[
        tuple[AssetRipperExportedAsset, ...], tuple[AssetRipperCollectionFailure, ...]
    ]:
        assets: dict[str, AssetRipperExportedAsset] = {}
        failures: dict[str, AssetRipperCollectionFailure] = {}
        for result in results:
            for failure in result.failures:
                existing_failure = failures.get(failure.stable_id)
                if existing_failure is None:
                    failures[failure.stable_id] = failure
                else:
                    failures[failure.stable_id] = replace(
                        existing_failure,
                        source_target_ids=tuple(
                            sorted(
                                set(existing_failure.source_target_ids)
                                | set(failure.source_target_ids),
                                key=str.casefold,
                            )
                        ),
                    )
            for asset in result.assets:
                failures.pop(asset.stable_id, None)
                existing = assets.get(asset.stable_id)
                if existing is None:
                    assets[asset.stable_id] = asset
                    continue
                if (
                    existing.normalized_collection != asset.normalized_collection
                    or existing.class_id != asset.class_id
                    or existing.path_id != asset.path_id
                ):
                    raise AssetRipperToolError("Stable asset identity collision.")
                for item in asset.files:
                    self._safe_child(staging_root, item.path).unlink(missing_ok=True)
                assets[asset.stable_id] = replace(
                    existing,
                    source_target_ids=tuple(
                        sorted(
                            set(existing.source_target_ids)
                            | set(asset.source_target_ids),
                            key=str.casefold,
                        )
                    ),
                )
        return (
            tuple(sorted(assets.values(), key=lambda item: item.stable_id)),
            tuple(sorted(failures.values(), key=lambda item: item.stable_id)),
        )

    def _build_manifest(
        self,
        context: ExecutionContext,
        old_manifest: dict[str, object],
        assets: Sequence[AssetRipperExportedAsset],
        failures: Sequence[AssetRipperCollectionFailure],
        plan: BundleDependencyPlan,
        run_fingerprint: str,
        *,
        filtered: bool,
        status: str,
    ) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
        entries = {entry.node_id: entry for entry in plan.entries}
        old_assets = self._manifest_assets(old_manifest)
        records = dict(old_assets) if filtered else {}
        successful_ids = {asset.stable_id for asset in assets}
        for stable_id in successful_ids:
            records.pop(stable_id, None)
        publish_assets: dict[str, dict[str, object]] = {}
        for asset in assets:
            canonical = sorted(set(asset.source_target_ids), key=str.casefold)
            aliases = sorted(
                {
                    f"{archive_id}::{entry_path}"
                    for source in canonical
                    if (entry := entries.get(source)) is not None
                    for archive_id, entry_path in entry.aliases
                },
                key=str.casefold,
            )
            record: dict[str, object] = {
                "asset_type": asset.asset_type,
                "readable_name": asset.readable_name,
                "collection": asset.collection,
                "normalized_collection": asset.normalized_collection,
                "class_id": asset.class_id,
                "path_id": asset.path_id,
                "canonical_sources": canonical,
                "alias_sources": aliases,
                "resource_version": context.resource_version,
                "files": [
                    {
                        "path": item.path,
                        "size": item.size,
                        "mtime_ns": item.mtime_ns,
                    }
                    for item in asset.files
                ],
            }
            records[asset.stable_id] = record
            publish_assets[asset.stable_id] = record
        manifest = {
            "schema_version": _BUNDLE_MANIFEST_SCHEMA_VERSION,
            "layout": _BUNDLE_LAYOUT,
            "region": context.region,
            "platform": context.platform,
            "resource_version": context.resource_version,
            "profile": _PROCESSING_PROFILE,
            "content_fingerprint": assetripper_exported_content_fingerprint(),
            "run_fingerprint": run_fingerprint,
            "status": status,
            "assets": records,
            "failures": [
                {
                    "stable_id": failure.stable_id,
                    "source_target_ids": list(failure.source_target_ids),
                    "error": failure.error,
                    "preserved_previous": (
                        filtered and failure.stable_id in old_assets
                    ),
                }
                for failure in failures
            ],
        }
        return manifest, publish_assets

    def _prepare_publish_tree(
        self,
        output_root: Path,
        job_root: Path,
        old_manifest: dict[str, object],
        publish_assets: dict[str, dict[str, object]],
        *,
        filtered: bool,
    ) -> Path:
        source_assets = self._find_assets_directory(job_root)
        if source_assets is None:
            source_assets = job_root / "Assets"
            source_assets.mkdir()
        if not filtered or old_manifest.get("_replace_incompatible_output") is True:
            return source_assets

        self._validate_complete_inventory(output_root, old_manifest)
        merged = job_root / "MergedAssets"
        merged.mkdir()
        updated_ids = set(publish_assets)
        old_assets = self._manifest_assets(old_manifest)
        claimed: set[str] = set()
        for stable_id, record in sorted(old_assets.items()):
            if stable_id in updated_ids:
                continue
            files = record.get("files")
            assert isinstance(files, list)
            for item in files:
                assert isinstance(item, dict)
                relative = str(item["path"])
                relative_inside = self._inside_assets(relative)
                source = self._safe_child(output_root, relative)
                destination = self._safe_child(merged, relative_inside)
                destination.parent.mkdir(parents=True, exist_ok=True)
                self._link_or_copy(source, destination)
                claimed.add(relative.casefold())

        for record in publish_assets.values():
            files = record.get("files")
            assert isinstance(files, list)
            rewritten: list[dict[str, object]] = []
            for item in files:
                assert isinstance(item, dict)
                desired = str(item["path"])
                allocated = self._allocate_path(desired, claimed)
                claimed.add(allocated.casefold())
                source = self._safe_child(job_root, desired)
                destination = self._safe_child(merged, self._inside_assets(allocated))
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.replace(destination)
                stat = destination.stat()
                rewritten.append(
                    {
                        **item,
                        "path": allocated,
                        "mtime_ns": stat.st_mtime_ns,
                    }
                )
            record["files"] = rewritten
        return merged

    def _publish_directory_transaction(
        self,
        output_root: Path,
        staged_assets: Path,
        manifest: dict[str, object],
    ) -> None:
        publish_root = staged_assets.parent / f".publish-bundles-{uuid4().hex}"
        publish_root.mkdir()
        staged_assets.replace(publish_root / "Assets")
        write_json_atomic(
            publish_root / "manifest.json",
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        publish_staged_directory(publish_root, output_root)

    def _load_manifest(
        self,
        path: Path,
        context: ExecutionContext,
    ) -> dict[str, object]:
        if not path.exists():
            return self._empty_manifest(context)
        try:
            payload = json.loads(path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise BundleExtractionError(
                "The bundle manifest is unreadable or corrupted; existing output was left unchanged."
            ) from exc
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("schema_version"), int)
            and payload.get("schema_version") != _BUNDLE_MANIFEST_SCHEMA_VERSION
        ):
            manifest = self._empty_manifest(context)
            manifest["_replace_incompatible_output"] = True
            return manifest
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _BUNDLE_MANIFEST_SCHEMA_VERSION
            or payload.get("layout") != _BUNDLE_LAYOUT
            or payload.get("region") != context.region
            or payload.get("platform") != context.platform
            or not isinstance(payload.get("assets"), dict)
            or not isinstance(payload.get("failures"), list)
        ):
            raise BundleExtractionError(
                "The bundle manifest has an incompatible or invalid structure; existing output was left unchanged."
            )
        declared_paths: set[str] = set()
        for stable_id, record in self._manifest_assets(payload).items():
            if not self._valid_asset_record(stable_id, record):
                raise BundleExtractionError(
                    "The bundle manifest contains an invalid asset record; existing output was left unchanged."
                )
            files = record["files"]
            assert isinstance(files, list)
            for item in files:
                assert isinstance(item, dict)
                path_key = str(item["path"]).casefold()
                if path_key in declared_paths:
                    raise BundleExtractionError(
                        "The bundle manifest assigns one output path to multiple assets."
                    )
                declared_paths.add(path_key)
        return payload

    def _load_warm_report(
        self,
        output_root: Path,
        manifest: dict[str, object],
        fingerprint: str,
    ) -> BundleExtractionReport | None:
        if (
            manifest.get("schema_version") != _BUNDLE_MANIFEST_SCHEMA_VERSION
            or manifest.get("run_fingerprint") != fingerprint
            or manifest.get("content_fingerprint")
            != assetripper_exported_content_fingerprint()
            or manifest.get("status") != "complete"
            or manifest.get("profile") != _PROCESSING_PROFILE
        ):
            return None
        try:
            self._validate_complete_inventory(output_root, manifest)
        except BundleExtractionError:
            return None
        return BundleExtractionReport(total_batches=1, succeeded_batches=1)

    def _validate_complete_inventory(
        self,
        output_root: Path,
        manifest: dict[str, object],
    ) -> None:
        declared: set[str] = set()
        for record in self._manifest_assets(manifest).values():
            files = record["files"]
            assert isinstance(files, list)
            for item in files:
                assert isinstance(item, dict)
                relative = str(item["path"])
                path = self._safe_child(output_root, relative)
                try:
                    stat = path.stat()
                except OSError as exc:
                    raise BundleExtractionError(
                        "A published bundle asset is missing; the extraction must be rebuilt."
                    ) from exc
                if stat.st_size != item["size"]:
                    raise BundleExtractionError(
                        "A published bundle asset was modified; the extraction must be rebuilt."
                    )
                if stat.st_mtime_ns != item["mtime_ns"]:
                    raise BundleExtractionError(
                        "A published bundle asset was modified; the extraction must be rebuilt."
                    )
                declared.add(relative.casefold())
        assets_root = self._find_assets_directory(output_root)
        actual = (
            {
                f"Assets/{path.relative_to(assets_root).as_posix()}".casefold()
                for path in assets_root.rglob("*")
                if path.is_file()
            }
            if assets_root is not None
            else set()
        )
        if actual != declared:
            raise BundleExtractionError(
                "The published Assets inventory differs from the bundle manifest; the extraction must be rebuilt."
            )

    @staticmethod
    def _valid_asset_record(stable_id: str, record: dict[str, object]) -> bool:
        files = record.get("files")
        canonical_sources = record.get("canonical_sources")
        alias_sources = record.get("alias_sources")
        return (
            bool(stable_id)
            and isinstance(record.get("asset_type"), str)
            and isinstance(record.get("readable_name"), str)
            and isinstance(record.get("collection"), str)
            and isinstance(record.get("normalized_collection"), str)
            and isinstance(record.get("class_id"), int)
            and isinstance(record.get("path_id"), int)
            and isinstance(canonical_sources, list)
            and isinstance(alias_sources, list)
            and isinstance(files, list)
            and bool(files)
            and all(
                isinstance(item, dict)
                and isinstance(item.get("path"), str)
                and str(item["path"]).startswith("Assets/")
                and isinstance(item.get("size"), int)
                and isinstance(item.get("mtime_ns"), int)
                for item in files
            )
        )

    def _run_fingerprint(
        self,
        context: ExecutionContext,
        archives: tuple[BundleArchiveInput, ...],
        *,
        filtered: bool,
    ) -> str:
        payload = {
            "schema": _BUNDLE_MANIFEST_SCHEMA_VERSION,
            "layout": _BUNDLE_LAYOUT,
            "profile": _PROCESSING_PROFILE,
            "grouping": {
                "profile": _STREAM_GROUPING_PROFILE,
                "target_entry_limit": _STREAM_GROUP_TARGET_ENTRY_LIMIT,
            },
            "mode": "filtered" if filtered else "full",
            "resource_version": context.resource_version,
            "dependency_scanner": assetripper_dependency_scan_cache_key(),
            "exported_content": assetripper_exported_content_fingerprint(),
            "inputs": [
                {
                    "archive_id": item.archive_id,
                    "size": item.size,
                    "mtime_ns": item.mtime_ns,
                    "checksum": (
                        {
                            "algorithm": item.checksum.algorithm,
                            "value": item.checksum.value,
                        }
                        if item.checksum is not None
                        else None
                    ),
                }
                for item in archives
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _empty_manifest(context: ExecutionContext) -> dict[str, object]:
        return {
            "schema_version": _BUNDLE_MANIFEST_SCHEMA_VERSION,
            "layout": _BUNDLE_LAYOUT,
            "region": context.region,
            "platform": context.platform,
            "resource_version": context.resource_version,
            "profile": _PROCESSING_PROFILE,
            "content_fingerprint": assetripper_exported_content_fingerprint(),
            "run_fingerprint": "",
            "status": "partial",
            "assets": {},
            "failures": [],
        }

    @staticmethod
    def _manifest_assets(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
        value = manifest.get("assets")
        if not isinstance(value, dict):
            return {}
        return {
            key: item
            for key, item in value.items()
            if isinstance(key, str) and isinstance(item, dict)
        }

    @staticmethod
    def _prepare_plan(plan: BundleDependencyPlan) -> _PreparedDependencyPlan:
        by_id = {component.component_id: component for component in plan.components}
        reasons: dict[str, str] = {}
        for component in plan.components:
            if component.scan_failed:
                reasons[component.component_id] = "dependency scan failed"
            elif component.unresolved_dependencies:
                names = sorted(
                    {item.logical_name for item in component.unresolved_dependencies},
                    key=str.casefold,
                )
                reasons[component.component_id] = (
                    "unresolved dependencies: " + ", ".join(names[:6])
                )
        changed = True
        while changed:
            changed = False
            for component in plan.components:
                if component.component_id in reasons:
                    continue
                missing = [
                    item
                    for item in component.dependency_component_ids
                    if item not in by_id or item in reasons
                ]
                if missing:
                    reasons[component.component_id] = (
                        "depends on unavailable component(s): " + ", ".join(missing)
                    )
                    changed = True
        executable = tuple(
            item for item in plan.components if item.component_id not in reasons
        )
        return _PreparedDependencyPlan(
            BundleDependencyPlan(executable, (), plan.ambiguous_dependencies, ()),
            tuple(
                (item, reasons[item.component_id])
                for item in plan.components
                if item.component_id in reasons
            ),
        )

    @staticmethod
    def _plan_warnings(prepared: _PreparedDependencyPlan) -> list[str]:
        warnings: list[str] = []
        if prepared.executable.ambiguous_dependencies:
            warnings.append(
                "AssetRipper dependency scan found "
                f"{len(prepared.executable.ambiguous_dependencies)} ambiguous "
                "reference(s); all matching owners will be loaded."
            )
        if prepared.skipped:
            warnings.append(
                f"AssetRipper skipped {len(prepared.skipped)} incomplete component(s)."
            )
        return warnings

    @staticmethod
    def _batch_for_targets(
        plan: BundleDependencyPlan,
        targets: Sequence[BundleComponent],
        *,
        batch_id: str,
    ) -> BundleExportBatch:
        by_id = {item.component_id: item for item in plan.components}
        loaded: set[str] = set()
        pending = [item.component_id for item in targets]
        while pending:
            current = pending.pop()
            if current in loaded:
                continue
            component = by_id[current]
            loaded.add(current)
            pending.extend(component.dependency_component_ids)
        loaded_components = tuple(
            component
            for component in plan.components
            if component.component_id in loaded
        )
        return BundleExportBatch(
            batch_id,
            tuple(targets),
            loaded_components,
        )

    def _stream_batches(
        self,
        plan: BundleDependencyPlan,
        *,
        target_entry_limit: int = _STREAM_GROUP_TARGET_ENTRY_LIMIT,
    ) -> tuple[BundleExportBatch, ...]:
        if target_entry_limit <= 0:
            raise ValueError("Bundle stream group target limit must be positive.")
        dependency_first = self._topological_components(plan)
        candidates = (
            self._group_components(
                plan,
                dependency_first,
                target_entry_limit=target_entry_limit,
            ),
            self._group_components(
                plan,
                tuple(reversed(dependency_first)),
                target_entry_limit=target_entry_limit,
            ),
        )
        return min(
            candidates,
            key=lambda batches: (
                sum(batch.total_bytes for batch in batches),
                sum(len(batch.entries) for batch in batches),
                tuple(batch.target_node_ids for batch in batches),
            ),
        )

    def _group_components(
        self,
        plan: BundleDependencyPlan,
        ordered: Sequence[BundleComponent],
        *,
        target_entry_limit: int,
    ) -> tuple[BundleExportBatch, ...]:
        target_groups: list[list[BundleComponent]] = []
        current: list[BundleComponent] = []
        current_entries = 0
        for component in ordered:
            self._cancellation.raise_if_cancelled()
            component_entries = len(component.entries)
            if current and current_entries + component_entries > target_entry_limit:
                target_groups.append(current)
                current = []
                current_entries = 0
            current.append(component)
            current_entries += component_entries
        if current:
            target_groups.append(current)
        width = max(1, len(str(len(target_groups))))
        return tuple(
            self._batch_for_targets(
                plan,
                targets,
                batch_id=f"group-{index:0{width}d}",
            )
            for index, targets in enumerate(target_groups, start=1)
        )

    def _topological_components(
        self,
        plan: BundleDependencyPlan,
    ) -> tuple[BundleComponent, ...]:
        by_id = {component.component_id: component for component in plan.components}
        if len(by_id) != len(plan.components):
            raise ValueError("Bundle dependency plan contains duplicate components.")
        component_keys = {
            component.component_id: min(
                entry.node_id.casefold() for entry in component.entries
            )
            for component in plan.components
        }
        dependent_ids: dict[str, list[str]] = {
            component_id: [] for component_id in by_id
        }
        pending_dependencies: dict[str, int] = {}
        for component in plan.components:
            self._cancellation.raise_if_cancelled()
            dependencies = component.dependency_component_ids
            if any(dependency not in by_id for dependency in dependencies):
                raise ValueError(
                    "Bundle dependency plan references an unknown component."
                )
            pending_dependencies[component.component_id] = len(dependencies)
            for dependency in dependencies:
                dependent_ids[dependency].append(component.component_id)

        ready: list[tuple[str, str]] = [
            (component_keys[component_id], component_id)
            for component_id, count in pending_dependencies.items()
            if count == 0
        ]
        heapq.heapify(ready)
        ordered: list[BundleComponent] = []
        while ready:
            self._cancellation.raise_if_cancelled()
            _, component_id = heapq.heappop(ready)
            ordered.append(by_id[component_id])
            for dependent_id in sorted(
                dependent_ids[component_id],
                key=lambda item: (component_keys[item], item),
            ):
                pending_dependencies[dependent_id] -= 1
                if pending_dependencies[dependent_id] == 0:
                    heapq.heappush(
                        ready,
                        (component_keys[dependent_id], dependent_id),
                    )
        if len(ordered) != len(plan.components):
            raise ValueError("Bundle dependency component graph is cyclic.")
        return tuple(ordered)

    @staticmethod
    def _unique_entries(
        entries: Sequence[BundleEntryInput],
    ) -> tuple[BundleEntryInput, ...]:
        by_node = {entry.node_id: entry for entry in entries}
        return tuple(by_node[key] for key in sorted(by_node, key=str.casefold))

    @staticmethod
    def _normalize_inputs(
        context: ExecutionContext,
        inputs: Sequence[Path | BundleArchiveInput],
    ) -> tuple[BundleArchiveInput, ...]:
        raw_root = context.workspace.raw_bundles.resolve(strict=False)
        archives: list[BundleArchiveInput] = []
        identifiers: set[str] = set()
        for item in inputs:
            if isinstance(item, BundleArchiveInput):
                resolved = item.path.resolve(strict=True)
                archive_id = item.archive_id
                checksum = item.checksum
            else:
                resolved = item.resolve(strict=True)
                checksum = None
                try:
                    archive_id = resolved.relative_to(raw_root).as_posix()
                except ValueError:
                    archive_id = resolved.name
            if archive_id.casefold() in identifiers:
                raise ValueError(f"Duplicate bundle archive identifier: {archive_id}")
            identifiers.add(archive_id.casefold())
            archives.append(
                BundleArchiveInput.from_path(
                    resolved,
                    archive_id=archive_id,
                    checksum=checksum,
                )
            )
        return tuple(sorted(archives, key=lambda item: item.archive_id.casefold()))

    @staticmethod
    def _handle_scan_event(
        progress: ProgressReporterPort,
        event: AssetRipperProcessEvent,
    ) -> None:
        if isinstance(event, AssetRipperScanProgressEvent):
            progress.update(
                ProgressState(
                    "Bundles",
                    "scanning",
                    current=ProgressMeasure(event.current, event.total, "archives"),
                    item=event.archive_id,
                )
            )

    @staticmethod
    def _handle_cache_event(
        progress: ProgressReporterPort,
        event: AssetRipperProcessEvent,
    ) -> None:
        if isinstance(event, AssetRipperEntryCacheProgressEvent):
            progress.update(
                ProgressState(
                    "Bundles",
                    "cache_fill",
                    current=ProgressMeasure(event.current, event.total, "entries"),
                    item=event.node_id,
                )
            )

    @staticmethod
    def _existing_assets_directories(output_root: Path) -> list[Path]:
        if not output_root.is_dir():
            return []
        return sorted(
            (
                path
                for path in output_root.iterdir()
                if path.is_dir() and path.name.casefold() == "assets"
            ),
            key=lambda item: item.name,
        )

    @classmethod
    def _find_assets_directory(cls, root: Path) -> Path | None:
        matches = cls._existing_assets_directories(root)
        return matches[0] if matches else None

    @staticmethod
    def _inside_assets(relative: str) -> str:
        parts = PurePosixPath(relative).parts
        if len(parts) < 2 or parts[0].casefold() != "assets":
            raise AssetRipperToolError(
                "AssetRipper output is outside the Assets layout."
            )
        return PurePosixPath(*parts[1:]).as_posix()

    @staticmethod
    def _allocate_path(desired: str, claimed: set[str]) -> str:
        if desired.casefold() not in claimed:
            return desired
        path = PurePosixPath(desired)
        stem = path.stem
        suffix = path.suffix
        counter = 0
        while True:
            candidate = str(path.with_name(f"{stem}_{counter}{suffix}"))
            if candidate.casefold() not in claimed:
                return candidate
            counter += 1

    @staticmethod
    def _link_or_copy(source: Path, destination: Path) -> None:
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)

    @staticmethod
    def _safe_child(root: Path, relative: str) -> Path:
        pure = PurePosixPath(relative)
        if (
            not relative
            or pure.is_absolute()
            or any(part in ("", ".", "..") for part in pure.parts)
            or any("\\" in part or ":" in part or "\0" in part for part in pure.parts)
        ):
            raise AssetRipperToolError("AssetRipper output path is unsafe.")
        root_resolved = root.resolve(strict=False)
        candidate = root_resolved.joinpath(*pure.parts).resolve(strict=False)
        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise AssetRipperToolError("AssetRipper output escaped its root.") from exc
        return candidate

    @staticmethod
    def _cleanup_staging(output_root: Path) -> None:
        for path in output_root.parent.glob(".bundles-staging-*"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
