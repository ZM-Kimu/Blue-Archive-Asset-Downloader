from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import (
    ProgressReporterFactoryPort,
    ProgressReporterPort,
)
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleComponent,
    BundleDependencyBatchPlanner,
    BundleDependencyPlan,
    BundleDependencyPlanner,
    BundleEntryInput,
    BundleExportBatch,
)
from ba_downloader.infrastructure.extraction.assetripper.entry_store import (
    BundleEntryStore,
    BundleEntryStoreResult,
    bundle_entry_store_root,
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
    ASSETRIPPER_EXPORTER_WRAPPER_VERSION,
    AssetRipperExportError,
    AssetRipperExportInput,
    AssetRipperExportResult,
    AssetRipperToolError,
    assetripper_dependency_scan_cache_key,
    assetripper_exporter_cache_key,
)
from ba_downloader.infrastructure.extraction.assetripper.scanner import (
    BundleDependencyScanBackend,
)
from ba_downloader.infrastructure.extraction.assetripper.scheduler import (
    BundleBatchScheduleDecision,
    BundleBatchScheduler,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    ASSETRIPPER_COMMIT,
    ASSETRIPPER_OVERLAY_VERSION,
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.extraction.threaded_runner import (
    ExtractionFailure,
    ExtractionFailureError,
)
from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    write_json_atomic,
)
from ba_downloader.infrastructure.files.checksum import calculate_sha256
from ba_downloader.infrastructure.progress import NullProgressReporterFactory

DEFAULT_MAX_BATCH_BYTES = 500 * 1024 * 1024
_BUNDLE_MANIFEST_SCHEMA_VERSION = 7
_BUNDLE_PLANNER_VERSION = 2
_CONFLICT_NAMESPACE = "_baad_conflicts"


@dataclass(frozen=True, slots=True)
class BundleExtractionReport:
    warnings: tuple[str, ...] = ()
    complete: bool = True
    total_batches: int = 0
    succeeded_batches: int = 0
    failed_batches: int = 0
    skipped_archives: int = 0
    skipped_components: int = 0
    conflict_paths: int = 0
    conflict_variants: int = 0


@dataclass(frozen=True, slots=True)
class _SkippedComponent:
    component: BundleComponent
    reason: str


@dataclass(frozen=True, slots=True)
class _PreparedDependencyPlan:
    executable: BundleDependencyPlan
    skipped_components: tuple[_SkippedComponent, ...]


@dataclass(frozen=True, slots=True)
class _PartialResumeState:
    successful_batches: dict[str, dict[str, object]]
    merge_index: _OutputMergeIndex


@dataclass(slots=True)
class _OutputVariant:
    stored_path: str
    sha256: str | None
    size: int
    source_batches: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _OutputPathRecord:
    original_path: str
    canonical: _OutputVariant
    variants: dict[str, _OutputVariant] = field(default_factory=dict)


@dataclass(slots=True)
class _OutputMergeIndex:
    records: dict[str, _OutputPathRecord] = field(default_factory=dict)

    @property
    def conflict_paths(self) -> int:
        return sum(bool(record.variants) for record in self.records.values())

    @property
    def conflict_variants(self) -> int:
        return sum(len(record.variants) for record in self.records.values())


@dataclass(frozen=True, slots=True)
class _ValidatedOutput:
    relative_path: str
    source: Path
    size: int


class _BundleBatchError(AssetRipperExportError):
    """A recoverable failure caused by one dependency batch."""


class _UnsafeBundleOutputError(AssetRipperToolError):
    """An exporter output path violated the extraction boundary."""


class _BundleExporter(Protocol):
    def prepare(self, context: ExecutionContext) -> None: ...

    def export(
        self,
        context: ExecutionContext,
        inputs: list[AssetRipperExportInput],
        output_directory: Path,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> AssetRipperExportResult: ...


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
        if self._serialize_reference_count == 0:
            return
        self._logger.warn(
            "AssetRipper Import: SerializeReference is not supported for "
            f"{self._serialize_reference_count} MonoBehaviour assets; "
            "structured fields were not parsed."
        )


class AssetRipperBundleWorkflow:
    def __init__(
        self,
        exporter: _BundleExporter,
        dependency_scanner: BundleDependencyScanBackend,
        logger: LoggerPort,
        *,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
        max_batch_bytes: int = DEFAULT_MAX_BATCH_BYTES,
        batch_scheduler: BundleBatchScheduler | None = None,
    ) -> None:
        self._exporter = exporter
        self._dependency_scanner = dependency_scanner
        self._logger = logger
        self._progress_factory = progress_factory or NullProgressReporterFactory()
        self._cancellation = cancellation or NeverCancelled()
        self._max_batch_bytes = max_batch_bytes
        self._batch_scheduler = batch_scheduler
        self._batch_planner = BundleDependencyBatchPlanner(
            max_batch_bytes=max_batch_bytes
        )

    def run(
        self,
        context: ExecutionContext,
        inputs: list[Path],
    ) -> BundleExtractionReport:
        run_started = time.perf_counter()
        archives = self._normalize_inputs(context, inputs)
        if not archives:
            raise ValueError("AssetRipper requires at least one input archive.")
        fingerprint = self._extraction_fingerprint(archives)
        cached = self._load_complete_report(
            context.workspace.extracted_bundles,
            fingerprint,
        )
        if cached is not None:
            self._logger.info("Bundle extraction is already up to date.")
            return cached

        completed = False
        with self._progress_factory.create(
            len(archives),
            "Extracting bundles...",
            extract_mode=True,
        ) as progress:
            progress.set_status(f"Scanning 0/{len(archives)} archives")
            progress.set_loading_progress(0, len(archives), "Scanning dependencies")
            try:
                self._cancellation.raise_if_cancelled()
                scan_started = time.perf_counter()
                scans = self._dependency_scanner.scan(
                    context,
                    list(archives),
                    lambda event: self._handle_event(progress, event, None),
                )
                scan_seconds = time.perf_counter() - scan_started
                progress.set_secondary_status("Planning dependency batches")
                planner_started = time.perf_counter()
                plan = BundleDependencyPlanner().build(archives, scans)
                warnings: list[str] = []
                prepared = self._prepare_plan(plan, warnings)
                batches = self._batch_planner.build(prepared.executable)
                planner_seconds = time.perf_counter() - planner_started
                if not batches:
                    detail = (
                        prepared.skipped_components[0].reason
                        if prepared.skipped_components
                        else "the dependency scan produced no bundle entries"
                    )
                    raise AssetRipperExportError(
                        "AssetRipper dependency scan produced no executable "
                        f"components: {detail}."
                    )
                progress.set_total(len(plan.entries))
                skipped_node_ids = {
                    node_id
                    for skipped in prepared.skipped_components
                    for node_id in skipped.component.node_ids
                }
                progress.set_completed(len(skipped_node_ids))
                progress.set_status(
                    f"{len(skipped_node_ids)}/{len(plan.entries)} entries"
                )
                report = self._export_all(
                    context,
                    archives,
                    plan,
                    prepared,
                    batches,
                    progress,
                    warnings,
                    fingerprint,
                    {
                        "scan_seconds": scan_seconds,
                        "planner_seconds": planner_seconds,
                    },
                    run_started,
                )
                self._cancellation.raise_if_cancelled()
                completed = True
            except OperationCancelledError:
                progress.set_failed_status("Bundle extraction cancelled")
                raise
            except AssetRipperExportError as exc:
                progress.set_failed_status(
                    f"Bundle extraction failed: {exc.__class__.__name__}: {exc}"
                )
                failure = ExtractionFailure("<all bundle inputs>", exc)
                raise ExtractionFailureError("bundle extraction", [failure]) from exc
            finally:
                if not completed:
                    progress.set_secondary_status("Bundle extraction failed")

        self._logger.info(
            "Bundle extraction completed: "
            f"{report.succeeded_batches}/{report.total_batches} batches succeeded, "
            f"{report.failed_batches} failed, "
            f"{report.skipped_archives} scan sources skipped, "
            f"{report.skipped_components} components skipped, "
            f"{report.conflict_paths} conflicting paths preserved."
        )
        return report

    def _export_all(
        self,
        context: ExecutionContext,
        archives: tuple[BundleArchiveInput, ...],
        plan: BundleDependencyPlan,
        prepared: _PreparedDependencyPlan,
        batches: tuple[BundleExportBatch, ...],
        progress: ProgressReporterPort,
        warnings: list[str],
        fingerprint: str,
        phase_timings: dict[str, float],
        run_started: float,
    ) -> BundleExtractionReport:
        output_root = context.workspace.extracted_bundles
        staging_root = output_root.parent / f".{output_root.name}.staging-{uuid4().hex}"
        content_root = staging_root / "content"
        resume = self._load_partial_resume(output_root, fingerprint, batches)
        log_aggregator = _AssetRipperLogAggregator(self._logger)
        staging_root.mkdir(parents=True)
        try:
            if resume is not None:
                self._seed_partial_output(
                    output_root / "content",
                    content_root,
                    resume.merge_index,
                )
            completed_node_ids = {
                node_id
                for skipped in prepared.skipped_components
                for node_id in skipped.component.node_ids
            }
            batch_records: list[dict[str, object]] = []
            merge_index = (
                resume.merge_index if resume is not None else _OutputMergeIndex()
            )
            succeeded_batches = 0
            failed_batches = 0
            first_batch_error: AssetRipperExportError | None = None
            entry_store = BundleEntryStore(
                bundle_entry_store_root(context),
                cancellation=self._cancellation,
            )
            cache_started = time.perf_counter()
            try:
                resolved_entries = entry_store.resolve_many(prepared.executable.entries)
            except (KeyError, RuntimeError, ValueError) as exc:
                raise AssetRipperToolError(
                    "Could not populate the AssetRipper entry cache: "
                    f"{exc.__class__.__name__}: {exc}"
                ) from exc
            resolved_by_node = {
                entry.node_id: resolved
                for entry, resolved in zip(
                    prepared.executable.entries,
                    resolved_entries,
                    strict=True,
                )
            }
            logical_entry_count = sum(len(batch.entries) for batch in batches)
            duplicate_entry_reuses = logical_entry_count - len(resolved_entries)
            entry_cache_hits = (
                sum(result.hit for result in resolved_entries) + duplicate_entry_reuses
            )
            entry_cache_misses = sum(not result.hit for result in resolved_entries)
            entry_cache_bytes_written = sum(
                result.bytes_written for result in resolved_entries
            )
            phase_timings["entry_cache_seconds"] = time.perf_counter() - cache_started
            successful_batch_ids = (
                set(resume.successful_batches) if resume is not None else set()
            )
            pending_batches = tuple(
                batch for batch in batches if batch.batch_id not in successful_batch_ids
            )
            schedule = self._schedule_batches(pending_batches or batches)
            self._logger.info(
                "AssetRipper batch scheduler selected "
                f"{schedule.worker_count} worker(s); estimated peak per worker is "
                f"{schedule.estimated_worker_bytes} bytes."
            )
            if (
                schedule.worker_count == 1
                and len(pending_batches) > 1
                and schedule.available_memory_bytes
                < schedule.memory_reserve_bytes + schedule.estimated_worker_bytes
            ):
                self._logger.warn(
                    "Available memory does not satisfy the preferred parallel "
                    "AssetRipper reserve; continuing with one worker and the "
                    "persistent disk entry cache."
                )
            prepare = getattr(self._exporter, "prepare", None)
            prepare_started = time.perf_counter()
            if callable(prepare):
                prepare(context)
            phase_timings["tool_prepare_seconds"] = (
                time.perf_counter() - prepare_started
            )
            event_lock = threading.Lock()
            export_outcomes: dict[
                str,
                tuple[
                    Path,
                    tuple[AssetRipperExportResult, float] | AssetRipperExportError,
                ],
            ] = {}
            export_merge_started = time.perf_counter()
            merge_seconds = 0.0
            with ThreadPoolExecutor(
                max_workers=schedule.worker_count,
                thread_name_prefix="assetripper-batch",
            ) as executor:
                pending = iter(
                    (batch_index, batch)
                    for batch_index, batch in enumerate(batches, start=1)
                    if batch.batch_id not in successful_batch_ids
                )
                active: dict[
                    Future[tuple[AssetRipperExportResult, float]],
                    tuple[Path, BundleExportBatch],
                ] = {}

                def submit_next() -> bool:
                    try:
                        batch_index, batch = next(pending)
                    except StopIteration:
                        return False
                    self._cancellation.raise_if_cancelled()
                    if batch.oversized:
                        self._logger.warn(
                            f"AssetRipper dependency batch {batch.batch_id} is "
                            f"{batch.total_bytes} bytes and exceeds the "
                            f"{batch.max_batch_bytes}-byte batch target; dependent "
                            "entries will remain together."
                        )
                    batch_label = f"Batch {batch_index}/{len(batches)}"
                    progress.set_secondary_status(batch_label)
                    batch_work_root = staging_root / ".work" / batch.batch_id
                    batch_output_root = batch_work_root / "output"
                    batch_inputs = self._batch_inputs(batch, resolved_by_node)

                    def handle_batch_event(
                        event: AssetRipperProcessEvent,
                        label: str = batch_label,
                    ) -> None:
                        with event_lock:
                            self._handle_event(
                                progress,
                                event,
                                log_aggregator,
                                label,
                            )

                    future = executor.submit(
                        self._export_timed,
                        self._exporter,
                        context,
                        batch_inputs,
                        batch_output_root,
                        handle_batch_event,
                    )
                    active[future] = (batch_work_root, batch)
                    return True

                for _ in range(schedule.worker_count):
                    if not submit_next():
                        break

                fatal_error: BaseException | None = None
                while active:
                    done, _ = wait(tuple(active), return_when=FIRST_COMPLETED)
                    for future in done:
                        batch_work_root, batch = active.pop(future)
                        if future.cancelled():
                            continue
                        try:
                            outcome = future.result()
                        except AssetRipperExportError as exc:
                            if isinstance(exc, AssetRipperToolError):
                                fatal_error = fatal_error or exc
                            else:
                                export_outcomes[batch.batch_id] = (
                                    batch_work_root,
                                    exc,
                                )
                        except BaseException as exc:
                            fatal_error = fatal_error or exc
                        else:
                            export_outcomes[batch.batch_id] = (
                                batch_work_root,
                                outcome,
                            )

                    if fatal_error is not None:
                        for future in active:
                            future.cancel()
                        continue
                    while len(active) < schedule.worker_count and submit_next():
                        pass

                if fatal_error is not None:
                    raise fatal_error

                for batch_index, batch in enumerate(batches, start=1):
                    if batch.batch_id in successful_batch_ids:
                        succeeded_batches += 1
                        batch_records.append(
                            dict(resume.successful_batches[batch.batch_id])  # type: ignore[union-attr]
                        )
                        completed_node_ids.update(batch.node_ids)
                        progress.set_completed(len(completed_node_ids))
                        progress.set_status(
                            f"{len(completed_node_ids)}/{len(plan.entries)} entries"
                        )
                        continue
                    batch_work_root, export_outcome = export_outcomes[batch.batch_id]
                    if schedule.worker_count > 1:
                        progress.set_secondary_status(
                            f"Merging batch {batch_index}/{len(batches)}"
                        )
                    batch_output_root = batch_work_root / "output"
                    batch_record = self._batch_manifest(batch)
                    try:
                        if isinstance(export_outcome, AssetRipperExportError):
                            raise export_outcome
                        result, export_seconds = export_outcome
                        self._validate_target_coverage(batch, result)
                        merge_started = time.perf_counter()
                        conflict_paths = self._merge_batch_output(
                            batch_output_root,
                            content_root,
                            result.files,
                            batch.batch_id,
                            merge_index,
                        )
                        merge_seconds += time.perf_counter() - merge_started
                    except OperationCancelledError:
                        raise
                    except AssetRipperToolError:
                        raise
                    except AssetRipperExportError as exc:
                        failed_batches += 1
                        if first_batch_error is None:
                            first_batch_error = exc
                        warning = (
                            f"[BUNDLE_BATCH_FAILED] {batch.batch_id} failed; "
                            "continuing with later batches: "
                            f"{exc.__class__.__name__}: {exc}"
                        )
                        self._record_warning(warnings, warning)
                        batch_record.update(
                            {
                                "status": "failed",
                                "error": {
                                    "type": exc.__class__.__name__,
                                    "message": str(exc),
                                },
                                "conflict_count": 0,
                            }
                        )
                    else:
                        succeeded_batches += 1
                        batch_record.update(
                            {
                                "status": "succeeded",
                                "error": None,
                                "conflict_count": len(conflict_paths),
                                "export_seconds": export_seconds,
                                "coverage": {
                                    "requested": list(result.requested_target_ids),
                                    "resolved": list(result.resolved_target_ids),
                                    "exported": list(result.exported_target_ids),
                                },
                            }
                        )
                        if conflict_paths:
                            examples = ", ".join(conflict_paths[:3])
                            warning = (
                                f"[BUNDLE_OUTPUT_CONFLICT] {batch.batch_id} produced "
                                f"{len(conflict_paths)} conflicting path(s); all unique "
                                f"variants were preserved. Examples: {examples}"
                            )
                            self._record_warning(warnings, warning)
                    finally:
                        if batch_work_root.exists():
                            shutil.rmtree(batch_work_root)
                    completed_node_ids.update(batch.node_ids)
                    progress.set_completed(len(completed_node_ids))
                    progress.set_status(
                        f"{len(completed_node_ids)}/{len(plan.entries)} entries"
                    )
                    batch_records.append(batch_record)
            phase_timings["export_merge_seconds"] = (
                time.perf_counter() - export_merge_started
            )
            phase_timings["merge_seconds"] = merge_seconds
            work_root = staging_root / ".work"
            if work_root.exists():
                work_root.rmdir()
            if succeeded_batches == 0:
                detail = (
                    f" First error: {first_batch_error.__class__.__name__}: "
                    f"{first_batch_error}"
                    if first_batch_error is not None
                    else ""
                )
                raise AssetRipperExportError(
                    "AssetRipper bundle extraction produced no publishable output; "
                    f"no batch succeeded.{detail}"
                )
            self._cancellation.raise_if_cancelled()
            exported_files = self._files_manifest(merge_index)
            complete = not (
                failed_batches
                or prepared.skipped_components
                or plan.scan_failures
                or merge_index.conflict_paths
            )
            if not complete:
                self._record_warning(
                    warnings,
                    "[BUNDLE_EXTRACTION_PARTIAL] Bundle extraction published "
                    f"partial output: {succeeded_batches}/{len(batches)} batches "
                    f"succeeded, {failed_batches} failed, "
                    f"{len(plan.scan_failures)} scan source(s) skipped, "
                    f"{len(prepared.skipped_components)} components skipped, and "
                    f"{merge_index.conflict_paths} conflicting paths preserved.",
                )
            manifest = {
                "schema_version": _BUNDLE_MANIFEST_SCHEMA_VERSION,
                "layout": "content",
                "complete": complete,
                "fingerprint": fingerprint,
                "warnings": list(warnings),
                "entry_cache": {
                    "hits": entry_cache_hits,
                    "misses": entry_cache_misses,
                    "bytes_written": entry_cache_bytes_written,
                },
                "scheduler": {
                    "worker_count": schedule.worker_count,
                    "available_memory_bytes": schedule.available_memory_bytes,
                    "memory_reserve_bytes": schedule.memory_reserve_bytes,
                    "estimated_worker_bytes": schedule.estimated_worker_bytes,
                },
                "timings": {
                    **phase_timings,
                    "total_seconds": time.perf_counter() - run_started,
                },
                "assetripper": {
                    "commit": ASSETRIPPER_COMMIT,
                    "overlay_version": ASSETRIPPER_OVERLAY_VERSION,
                    "overlay_hash": AssetRipperSourceResolver.overlay_hash(),
                    "wrapper_version": ASSETRIPPER_EXPORTER_WRAPPER_VERSION,
                },
                "inputs": [
                    {"name": archive.archive_id, "size": archive.size}
                    for archive in archives
                ],
                "entries": [self._entry_manifest(entry) for entry in plan.entries],
                "components": [
                    self._component_manifest(component) for component in plan.components
                ],
                "batches": batch_records,
                "skipped_archives": [
                    {
                        "archive": failure.archive_id,
                        "entry": failure.entry_path,
                        "reason": failure.error,
                    }
                    for failure in plan.scan_failures
                ],
                "skipped_components": [
                    {
                        "id": skipped.component.component_id,
                        "entries": list(skipped.component.node_ids),
                        "reason": skipped.reason,
                    }
                    for skipped in prepared.skipped_components
                ],
                "conflicts": self._conflict_manifest(merge_index),
                "outputs": self._output_manifest(merge_index),
                "summary": {
                    "total_batches": len(batches),
                    "succeeded_batches": succeeded_batches,
                    "failed_batches": failed_batches,
                    "total_components": len(plan.components),
                    "executable_components": len(prepared.executable.components),
                    "skipped_components": len(prepared.skipped_components),
                    "skipped_archives": len(plan.scan_failures),
                    "conflict_paths": merge_index.conflict_paths,
                    "conflict_variants": merge_index.conflict_variants,
                },
                "files": exported_files,
            }
            write_json_atomic(
                content_root / "manifest.json",
                manifest,
                indent=2,
                sort_keys=True,
            )
            publish_staged_directory(staging_root, output_root)
            return BundleExtractionReport(
                warnings=tuple(warnings),
                complete=complete,
                total_batches=len(batches),
                succeeded_batches=succeeded_batches,
                failed_batches=failed_batches,
                skipped_archives=len(plan.scan_failures),
                skipped_components=len(prepared.skipped_components),
                conflict_paths=merge_index.conflict_paths,
                conflict_variants=merge_index.conflict_variants,
            )
        finally:
            log_aggregator.flush()
            shutil.rmtree(staging_root, ignore_errors=True)

    @staticmethod
    def _export_timed(
        exporter: _BundleExporter,
        context: ExecutionContext,
        inputs: list[AssetRipperExportInput],
        output_directory: Path,
        event_callback: Callable[[AssetRipperProcessEvent], None],
    ) -> tuple[AssetRipperExportResult, float]:
        started = time.perf_counter()
        result = exporter.export(
            context,
            inputs,
            output_directory,
            event_callback,
        )
        return result, time.perf_counter() - started

    @staticmethod
    def _batch_inputs(
        batch: BundleExportBatch,
        resolved_by_node: dict[str, BundleEntryStoreResult],
    ) -> list[AssetRipperExportInput]:
        inputs: list[AssetRipperExportInput] = []
        target_node_ids = set(batch.target_node_ids)
        for entry in batch.entries:
            resolved = resolved_by_node[entry.node_id]
            inputs.append(
                AssetRipperExportInput(
                    resolved.path,
                    entry.node_id,
                    entry.node_id in target_node_ids,
                )
            )
        return inputs

    def _schedule_batches(
        self,
        batches: tuple[BundleExportBatch, ...],
    ) -> BundleBatchScheduleDecision:
        estimates = [
            BundleBatchScheduler.estimate_batch_memory(
                batch.total_bytes,
                len(batch.entries),
            )
            for batch in batches
        ]
        if self._batch_scheduler is None:
            return BundleBatchScheduleDecision(
                worker_count=1,
                available_memory_bytes=0,
                memory_reserve_bytes=0,
                estimated_worker_bytes=max(estimates),
            )
        return self._batch_scheduler.decide(estimates)

    @staticmethod
    def _validate_target_coverage(
        batch: BundleExportBatch,
        result: AssetRipperExportResult,
    ) -> None:
        expected = set(batch.target_node_ids)
        coverage = {
            "requested": result.requested_target_ids,
            "resolved": result.resolved_target_ids,
            "exported": result.exported_target_ids,
        }
        mismatches = [
            name
            for name, node_ids in coverage.items()
            if len(node_ids) != len(expected) or set(node_ids) != expected
        ]
        if mismatches:
            raise _BundleBatchError(
                "AssetRipper selective export target coverage is incomplete for "
                f"{batch.batch_id}: {', '.join(mismatches)} coverage did not match "
                f"the {len(expected)} requested target(s)."
            )

    @staticmethod
    def _entry_manifest(entry: BundleEntryInput) -> dict[str, object]:
        return {
            "node_id": entry.node_id,
            "source_archive": entry.archive.archive_id,
            "entry_path": entry.entry_path,
            "sha256": entry.sha256,
            "size": entry.size,
            "aliases": [
                {"source_archive": archive_id, "entry_path": entry_path}
                for archive_id, entry_path in entry.aliases
            ],
        }

    def _handle_event(
        self,
        progress: ProgressReporterPort,
        event: AssetRipperProcessEvent,
        log_aggregator: _AssetRipperLogAggregator | None,
        batch_label: str | None = None,
    ) -> None:
        if isinstance(event, AssetRipperPhaseEvent):
            if event.phase == "processing":
                progress.set_secondary_status("Processing")
                progress.set_processing_status("Processing")
            elif event.phase == "exporting":
                progress.set_secondary_status(
                    f"{batch_label}: Exporting" if batch_label else "Exporting"
                )
                progress.set_processing_status("Processing complete")
        elif isinstance(event, AssetRipperProgressEvent):
            if event.phase == "loading":
                progress.set_loading_progress(
                    event.current,
                    event.total,
                    self._format_stage(event.stage),
                )
            else:
                progress.set_secondary_status(
                    f"{batch_label + ': ' if batch_label else ''}"
                    f"Exporting assets {event.current}/{event.total}"
                )
        elif isinstance(event, AssetRipperHeartbeatEvent):
            progress.set_processing_status(
                f"Processing {self._format_elapsed(event.elapsed_seconds)}"
            )
        elif isinstance(event, AssetRipperLogEvent):
            if log_aggregator is not None:
                log_aggregator.handle(event)
        elif isinstance(event, AssetRipperScanProgressEvent):
            progress.set_loading_progress(
                event.current,
                event.total,
                "Scanning dependencies",
            )
            progress.set_status(f"Scanned {event.current}/{event.total} bundles")

    def _normalize_inputs(
        self,
        context: ExecutionContext,
        inputs: list[Path],
    ) -> tuple[BundleArchiveInput, ...]:
        raw_root = context.workspace.raw_bundles.resolve(strict=False)
        archives: list[BundleArchiveInput] = []
        identifiers: set[str] = set()
        for path in inputs:
            resolved = path.resolve(strict=True)
            try:
                archive_id = resolved.relative_to(raw_root).as_posix()
            except ValueError:
                archive_id = resolved.name
            normalized_id = archive_id.casefold()
            if normalized_id in identifiers:
                raise ValueError(f"Duplicate bundle archive identifier: {archive_id}")
            identifiers.add(normalized_id)
            archives.append(
                BundleArchiveInput.from_path(resolved, archive_id=archive_id)
            )
        return tuple(sorted(archives, key=lambda item: item.archive_id.casefold()))

    def _extraction_fingerprint(
        self,
        archives: tuple[BundleArchiveInput, ...],
    ) -> str:
        inputs: list[dict[str, object]] = []
        for archive in archives:
            identity: dict[str, object] = {
                "archive_id": archive.archive_id,
                "size": archive.size,
            }
            if archive.checksum is not None:
                identity.update(
                    {
                        "identity": "catalog",
                        "checksum_algorithm": archive.checksum.algorithm,
                        "checksum_value": archive.checksum.value,
                    }
                )
            else:
                identity.update(
                    {
                        "identity": "local",
                        "path": str(archive.path),
                        "mtime_ns": archive.mtime_ns,
                    }
                )
            inputs.append(identity)
        payload = {
            "manifest_schema": _BUNDLE_MANIFEST_SCHEMA_VERSION,
            "planner_version": _BUNDLE_PLANNER_VERSION,
            "max_batch_bytes": self._max_batch_bytes,
            "dependency_scanner": assetripper_dependency_scan_cache_key(),
            "exporter": assetripper_exporter_cache_key(),
            "inputs": inputs,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf8")).hexdigest()

    @staticmethod
    def _load_complete_report(
        output_root: Path,
        fingerprint: str,
    ) -> BundleExtractionReport | None:
        content_root = output_root / "content"
        manifest_path = content_root / "manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf8"))
        except (OSError, ValueError):
            return None
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _BUNDLE_MANIFEST_SCHEMA_VERSION
            or payload.get("fingerprint") != fingerprint
            or payload.get("complete") is not True
        ):
            return None
        summary = payload.get("summary")
        warnings = payload.get("warnings", [])
        files = payload.get("files")
        if (
            not isinstance(summary, dict)
            or not isinstance(warnings, list)
            or not AssetRipperBundleWorkflow._validate_complete_inventory(
                content_root,
                files,
            )
        ):
            return None

        def count(name: str) -> int | None:
            value = summary.get(name)
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool)
                else None
            )

        values = {
            name: count(name)
            for name in (
                "total_batches",
                "succeeded_batches",
                "failed_batches",
                "skipped_archives",
                "skipped_components",
                "conflict_paths",
                "conflict_variants",
            )
        }
        if any(value is None for value in values.values()) or not all(
            isinstance(item, str) for item in warnings
        ):
            return None
        return BundleExtractionReport(
            warnings=tuple(warnings),
            complete=True,
            total_batches=values["total_batches"] or 0,
            succeeded_batches=values["succeeded_batches"] or 0,
            failed_batches=values["failed_batches"] or 0,
            skipped_archives=values["skipped_archives"] or 0,
            skipped_components=values["skipped_components"] or 0,
            conflict_paths=values["conflict_paths"] or 0,
            conflict_variants=values["conflict_variants"] or 0,
        )

    @staticmethod
    def _validate_complete_inventory(content_root: Path, payload: object) -> bool:
        if not isinstance(payload, list):
            return False
        try:
            resolved_root = content_root.resolve(strict=True)
        except OSError:
            return False
        if content_root.is_symlink() or not resolved_root.is_dir():
            return False

        paths: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                return False
            try:
                relative_path = AssetRipperBundleWorkflow._validate_manifest_path(
                    item.get("path")
                )
            except ValueError:
                return False
            size = item.get("size")
            normalized_path = relative_path.casefold()
            if (
                not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
                or normalized_path in paths
            ):
                return False
            paths.add(normalized_path)
            candidate = content_root.joinpath(*PurePosixPath(relative_path).parts)
            try:
                resolved_candidate = candidate.resolve(strict=True)
                resolved_candidate.relative_to(resolved_root)
                actual_size = resolved_candidate.stat().st_size
            except (OSError, ValueError):
                return False
            if candidate.is_symlink() or not resolved_candidate.is_file():
                return False
            if actual_size != size:
                return False
        return True

    @classmethod
    def _load_partial_resume(
        cls,
        output_root: Path,
        fingerprint: str,
        batches: tuple[BundleExportBatch, ...],
    ) -> _PartialResumeState | None:
        manifest_path = output_root / "content" / "manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf8"))
        except (OSError, ValueError):
            return None
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _BUNDLE_MANIFEST_SCHEMA_VERSION
            or payload.get("fingerprint") != fingerprint
            or payload.get("complete") is not False
        ):
            return None
        batch_payloads = payload.get("batches")
        output_payloads = payload.get("outputs")
        if not isinstance(batch_payloads, list) or not isinstance(
            output_payloads, list
        ):
            return None
        current_batches = {batch.batch_id: batch for batch in batches}
        successful: dict[str, dict[str, object]] = {}
        for item in batch_payloads:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                return None
            batch_id = item["id"]
            batch = current_batches.get(batch_id)
            if (
                batch is None
                or item.get("targets") != list(batch.target_node_ids)
                or item.get("entries") != list(batch.node_ids)
            ):
                return None
            if item.get("status") == "succeeded":
                successful[batch_id] = dict(item)
        if not successful:
            return None

        merge_index = _OutputMergeIndex()
        try:
            for item in output_payloads:
                if not isinstance(item, dict):
                    return None
                original_path = cls._validate_manifest_path(item.get("original_path"))
                canonical = cls._parse_manifest_variant(item.get("canonical"))
                variants_payload = item.get("variants")
                if not isinstance(variants_payload, list):
                    return None
                variants: dict[str, _OutputVariant] = {}
                for variant_payload in variants_payload:
                    variant = cls._parse_manifest_variant(variant_payload)
                    if variant.sha256 is None or variant.sha256 in variants:
                        return None
                    variants[variant.sha256] = variant
                key = original_path.casefold()
                if key in merge_index.records:
                    return None
                merge_index.records[key] = _OutputPathRecord(
                    original_path,
                    canonical,
                    variants,
                )
        except (TypeError, ValueError):
            return None
        if not cls._validate_resume_inventory(output_root / "content", merge_index):
            return None
        return _PartialResumeState(successful, merge_index)

    @classmethod
    def _validate_resume_inventory(
        cls,
        content_root: Path,
        merge_index: _OutputMergeIndex,
    ) -> bool:
        try:
            resolved_root = content_root.resolve(strict=True)
        except OSError:
            return False
        if content_root.is_symlink() or not resolved_root.is_dir():
            return False

        stored_paths: set[str] = set()
        for record in merge_index.records.values():
            for variant in (record.canonical, *record.variants.values()):
                normalized_path = variant.stored_path.casefold()
                if normalized_path in stored_paths:
                    return False
                stored_paths.add(normalized_path)
                relative = PurePosixPath(variant.stored_path)
                candidate = content_root.joinpath(*relative.parts)
                try:
                    resolved_candidate = candidate.resolve(strict=True)
                    resolved_candidate.relative_to(resolved_root)
                    stat = resolved_candidate.stat()
                except (OSError, ValueError):
                    return False
                if (
                    candidate.is_symlink()
                    or not resolved_candidate.is_file()
                    or stat.st_size != variant.size
                ):
                    return False
                if variant.sha256 is not None:
                    try:
                        with resolved_candidate.open("rb") as source:
                            actual_hash = hashlib.file_digest(
                                source, "sha256"
                            ).hexdigest()
                    except OSError:
                        return False
                    if actual_hash != variant.sha256:
                        return False
        return True

    @classmethod
    def _parse_manifest_variant(cls, payload: object) -> _OutputVariant:
        if not isinstance(payload, dict):
            raise TypeError("Bundle output variant must be an object.")
        stored_path = cls._validate_manifest_path(payload.get("stored_path"))
        sha256 = payload.get("sha256")
        size = payload.get("size")
        source_batches = payload.get("source_batches")
        if (
            (sha256 is not None and not cls._is_sha256(sha256))
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(source_batches, list)
            or not all(isinstance(item, str) for item in source_batches)
        ):
            raise ValueError("Bundle output variant is invalid.")
        return _OutputVariant(stored_path, sha256, size, list(source_batches))

    @staticmethod
    def _validate_manifest_path(value: object) -> str:
        if not isinstance(value, str) or not value or "\\" in value:
            raise ValueError("Bundle manifest path is invalid.")
        relative = PurePosixPath(value)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
        ):
            raise ValueError("Bundle manifest path is unsafe.")
        return relative.as_posix()

    @staticmethod
    def _is_sha256(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    def _seed_partial_output(
        self,
        source_root: Path,
        destination_root: Path,
        merge_index: _OutputMergeIndex,
    ) -> None:
        resolved_source_root = source_root.resolve(strict=True)
        for file_record in self._files_manifest(merge_index):
            self._cancellation.raise_if_cancelled()
            relative = PurePosixPath(str(file_record["path"]))
            source = source_root.joinpath(*relative.parts)
            resolved_source = source.resolve(strict=True)
            try:
                resolved_source.relative_to(resolved_source_root)
            except ValueError as exc:
                raise AssetRipperToolError(
                    f"Bundle resume output escaped its root: {relative.as_posix()}"
                ) from exc
            if (
                source.is_symlink()
                or not resolved_source.is_file()
                or resolved_source.stat().st_size != file_record["size"]
            ):
                raise AssetRipperToolError(
                    f"Bundle resume output is missing or invalid: {relative.as_posix()}"
                )
            destination = destination_root.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(resolved_source, destination)
            except OSError:
                shutil.copy2(resolved_source, destination)

    def _prepare_plan(
        self,
        plan: BundleDependencyPlan,
        warnings: list[str],
    ) -> _PreparedDependencyPlan:
        if plan.ambiguous_dependencies:
            self._record_warning(
                warnings,
                "AssetRipper dependency scan found "
                f"{len(plan.ambiguous_dependencies)} ambiguous reference(s); "
                "all matching owner entries will be loaded together.",
            )

        components_by_id = {
            component.component_id: component for component in plan.components
        }
        skipped_reasons: dict[str, str] = {}
        for component in plan.components:
            if component.scan_failed:
                failures = [
                    failure
                    for failure in plan.scan_failures
                    if failure.entry_path is not None
                    and f"{failure.archive_id}::{failure.entry_path}"
                    in component.node_ids
                ]
                detail = failures[0].error if failures else "dependency scan failed"
                skipped_reasons[component.component_id] = (
                    f"component scan failed: {detail}"
                )
            elif component.unresolved_dependencies:
                names = sorted(
                    {issue.logical_name for issue in component.unresolved_dependencies},
                    key=str.casefold,
                )
                skipped_reasons[component.component_id] = (
                    "unresolved dependencies: " + ", ".join(names[:6])
                )

        changed = True
        while changed:
            changed = False
            for component in plan.components:
                if component.component_id in skipped_reasons:
                    continue
                missing = [
                    dependency_id
                    for dependency_id in component.dependency_component_ids
                    if dependency_id not in components_by_id
                ]
                if missing:
                    skipped_reasons[component.component_id] = (
                        "dependency closure references unavailable component(s): "
                        + ", ".join(missing)
                    )
                    changed = True
                    continue
                skipped_dependencies = [
                    dependency_id
                    for dependency_id in component.dependency_component_ids
                    if dependency_id in skipped_reasons
                ]
                if skipped_dependencies:
                    skipped_reasons[component.component_id] = (
                        "depends on skipped component(s): "
                        + ", ".join(skipped_dependencies)
                    )
                    changed = True

        skipped = tuple(
            _SkippedComponent(component, skipped_reasons[component.component_id])
            for component in plan.components
            if component.component_id in skipped_reasons
        )
        executable_components = tuple(
            component
            for component in plan.components
            if component.component_id not in skipped_reasons
        )
        executable_ids = {component.component_id for component in executable_components}
        executable = BundleDependencyPlan(
            components=executable_components,
            unresolved_dependencies=(),
            ambiguous_dependencies=tuple(
                issue
                for issue in plan.ambiguous_dependencies
                if any(
                    issue.source_archive_id == entry.archive.archive_id
                    and issue.source_entry_path == entry.entry_path
                    for component in executable_components
                    for entry in component.entries
                )
            ),
            scan_failures=(),
        )
        for component in executable.components:
            if any(
                dependency_id not in executable_ids
                for dependency_id in component.dependency_component_ids
            ):
                raise RuntimeError(
                    "AssetRipper executable plan retained a skipped dependency."
                )

        if plan.scan_failures:
            first = plan.scan_failures[0]
            self._record_warning(
                warnings,
                "[BUNDLE_SCAN_SKIPPED] Dependency scanning skipped "
                f"{len(plan.scan_failures)} archive or entry source(s); "
                f"first: {first.archive_id}: {first.error}",
            )
        if skipped:
            examples = "; ".join(
                f"{item.component.component_id}: {item.reason}" for item in skipped[:3]
            )
            self._record_warning(
                warnings,
                "[BUNDLE_COMPONENT_SKIPPED] Skipped "
                f"{len(skipped)} incomplete dependency component(s). "
                f"Examples: {examples}",
            )
        return _PreparedDependencyPlan(executable, skipped)

    def _merge_batch_output(
        self,
        batch_root: Path,
        content_root: Path,
        files: tuple[object, ...],
        batch_id: str,
        merge_index: _OutputMergeIndex,
    ) -> tuple[str, ...]:
        validated = self._validate_batch_output(batch_root, files)
        content_root.mkdir(parents=True, exist_ok=True)
        conflicts: set[str] = set()
        for item in validated:
            key = item.relative_path.casefold()
            record = merge_index.records.get(key)
            if record is None:
                destination = content_root.joinpath(
                    *PurePosixPath(item.relative_path).parts
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                item.source.replace(destination)
                merge_index.records[key] = _OutputPathRecord(
                    item.relative_path,
                    _OutputVariant(
                        item.relative_path,
                        None,
                        item.size,
                        [batch_id],
                    ),
                )
                continue

            canonical_path = content_root.joinpath(
                *PurePosixPath(record.canonical.stored_path).parts
            )
            canonical_hash = record.canonical.sha256
            if canonical_hash is None:
                canonical_hash = calculate_sha256(
                    canonical_path,
                    on_chunk=self._cancellation.raise_if_cancelled,
                )
                record.canonical.sha256 = canonical_hash
            item_hash = calculate_sha256(
                item.source,
                on_chunk=self._cancellation.raise_if_cancelled,
            )
            if item_hash == canonical_hash:
                self._append_source_batch(record.canonical, batch_id)
                item.source.unlink()
                continue

            conflicts.add(record.original_path)
            variant = record.variants.get(item_hash)
            if variant is None:
                stored_path = (
                    f"{_CONFLICT_NAMESPACE}/{item_hash}/{record.original_path}"
                )
                destination = content_root.joinpath(*PurePosixPath(stored_path).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() or destination.is_symlink():
                    raise RuntimeError(
                        "AssetRipper conflict index selected an occupied variant path."
                    )
                item.source.replace(destination)
                record.variants[item_hash] = _OutputVariant(
                    stored_path,
                    item_hash,
                    item.size,
                    [batch_id],
                )
                continue

            if item.size != variant.size:
                raise RuntimeError(
                    "AssetRipper conflict index contains an inconsistent SHA-256 variant."
                )
            self._append_source_batch(variant, batch_id)
            item.source.unlink()
        return tuple(sorted(conflicts, key=str.casefold))

    def _validate_batch_output(
        self,
        batch_root: Path,
        files: tuple[object, ...],
    ) -> tuple[_ValidatedOutput, ...]:
        validated: list[_ValidatedOutput] = []
        seen: set[str] = set()
        try:
            resolved_root = batch_root.resolve(strict=True)
        except FileNotFoundError as exc:
            raise _BundleBatchError(
                "AssetRipper output directory was not created."
            ) from exc
        for item in files:
            raw_relative = getattr(item, "path", None)
            expected_size = getattr(item, "size", None)
            if (
                not isinstance(raw_relative, str)
                or not isinstance(expected_size, int)
                or isinstance(expected_size, bool)
                or expected_size < 0
            ):
                raise AssetRipperToolError(
                    "AssetRipper returned an invalid exported file record."
                )
            relative = self._validate_output_path(raw_relative)
            normalized = relative.as_posix()
            key = normalized.casefold()
            if key in seen:
                raise AssetRipperToolError(
                    f"AssetRipper returned a duplicate output path: {raw_relative}"
                )
            seen.add(key)
            source = batch_root.joinpath(*relative.parts)
            try:
                resolved_source = source.resolve(strict=True)
            except FileNotFoundError as exc:
                raise _BundleBatchError(
                    f"AssetRipper output validation failed: {raw_relative}"
                ) from exc
            try:
                resolved_source.relative_to(resolved_root)
            except ValueError as exc:
                raise _UnsafeBundleOutputError(
                    f"AssetRipper output escaped its batch directory: {raw_relative}"
                ) from exc
            if (
                not resolved_source.is_file()
                or resolved_source.stat().st_size != expected_size
            ):
                raise _BundleBatchError(
                    f"AssetRipper output validation failed: {raw_relative}"
                )
            validated.append(
                _ValidatedOutput(
                    normalized,
                    resolved_source,
                    expected_size,
                )
            )
        return tuple(validated)

    @staticmethod
    def _validate_output_path(raw_relative: str) -> PurePosixPath:
        relative = PurePosixPath(raw_relative)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or "\\" in raw_relative
            or any(ord(character) < 32 for character in raw_relative)
            or any(
                any(character in '<>:"|?*' for character in part)
                or part[-1] in {" ", "."}
                for part in relative.parts
            )
        ):
            raise _UnsafeBundleOutputError(
                f"AssetRipper returned an unsafe output path: {raw_relative}"
            )
        if relative.parts[0].casefold() == _CONFLICT_NAMESPACE.casefold():
            raise _UnsafeBundleOutputError(
                f"AssetRipper returned a reserved output path: {raw_relative}"
            )
        return relative

    @staticmethod
    def _append_source_batch(variant: _OutputVariant, batch_id: str) -> None:
        if batch_id not in variant.source_batches:
            variant.source_batches.append(batch_id)

    @staticmethod
    def _batch_manifest(batch: BundleExportBatch) -> dict[str, object]:
        return {
            "id": batch.batch_id,
            "targets": list(batch.target_node_ids),
            "entries": list(batch.node_ids),
            "size": batch.total_bytes,
            "oversized": batch.oversized,
            "target_components": [
                component.component_id for component in batch.target_components
            ],
            "loaded_components": [
                component.component_id for component in batch.loaded_components
            ],
        }

    @staticmethod
    def _component_manifest(component: BundleComponent) -> dict[str, object]:
        return {
            "id": component.component_id,
            "entries": list(component.node_ids),
            "dependencies": list(component.dependency_component_ids),
            "ambiguous_dependencies": len(component.ambiguous_dependencies),
        }

    @staticmethod
    def _conflict_manifest(index: _OutputMergeIndex) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for record in sorted(
            index.records.values(),
            key=lambda item: item.original_path.casefold(),
        ):
            if not record.variants:
                continue
            records.append(
                {
                    "original_path": record.original_path,
                    "canonical": AssetRipperBundleWorkflow._variant_manifest(
                        record.canonical
                    ),
                    "variants": [
                        AssetRipperBundleWorkflow._variant_manifest(variant)
                        for variant in sorted(
                            record.variants.values(),
                            key=lambda item: item.sha256 or "",
                        )
                    ],
                }
            )
        return records

    @staticmethod
    def _output_manifest(index: _OutputMergeIndex) -> list[dict[str, object]]:
        return [
            {
                "original_path": record.original_path,
                "canonical": AssetRipperBundleWorkflow._resume_variant_manifest(
                    record.canonical
                ),
                "variants": [
                    AssetRipperBundleWorkflow._resume_variant_manifest(variant)
                    for variant in sorted(
                        record.variants.values(),
                        key=lambda item: item.stored_path.casefold(),
                    )
                ],
            }
            for record in sorted(
                index.records.values(),
                key=lambda item: item.original_path.casefold(),
            )
        ]

    @staticmethod
    def _files_manifest(index: _OutputMergeIndex) -> list[dict[str, object]]:
        files = [
            {"path": variant.stored_path, "size": variant.size}
            for record in index.records.values()
            for variant in (record.canonical, *record.variants.values())
        ]
        return sorted(files, key=lambda item: str(item["path"]).casefold())

    @staticmethod
    def _resume_variant_manifest(variant: _OutputVariant) -> dict[str, object]:
        return {
            "stored_path": variant.stored_path,
            "sha256": variant.sha256,
            "size": variant.size,
            "source_batches": list(variant.source_batches),
        }

    @staticmethod
    def _variant_manifest(variant: _OutputVariant) -> dict[str, object]:
        if variant.sha256 is None:
            raise RuntimeError("AssetRipper conflict variant has no SHA-256.")
        return {
            "stored_path": variant.stored_path,
            "sha256": variant.sha256,
            "size": variant.size,
            "source_batches": list(variant.source_batches),
        }

    def _record_warning(self, warnings: list[str], message: str) -> None:
        warnings.append(message)
        self._logger.warn(message)

    @staticmethod
    def _format_stage(stage: str) -> str:
        return stage.replace("_", " ").capitalize()

    @staticmethod
    def _format_elapsed(elapsed_seconds: float) -> str:
        total_seconds = max(0, int(elapsed_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
