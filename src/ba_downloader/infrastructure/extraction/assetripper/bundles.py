from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path, PurePosixPath
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
    ProgressReporterFactoryPort,
    ProgressReporterPort,
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
    AssetRipperEntryCacheProgressEvent,
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
    AssetRipperExportGroup,
    AssetRipperExportInput,
    AssetRipperExportResult,
    AssetRipperToolError,
    assetripper_dependency_scan_cache_key,
    assetripper_exporter_cache_key,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    AssetRipperSourceError,
)
from ba_downloader.infrastructure.extraction.errors import BundleExtractionError
from ba_downloader.infrastructure.files.atomic import write_json_atomic
from ba_downloader.infrastructure.files.checksum import calculate_sha256
from ba_downloader.infrastructure.files.lock import (
    InterprocessFileLock,
    InterprocessLockBusyError,
)
from ba_downloader.infrastructure.progress import NullProgressReporterFactory

_BUNDLE_MANIFEST_SCHEMA_VERSION = 10
_BUNDLE_LAYOUT = "assetripper-readable-v1"
_PROCESSING_PROFILE = "readable-fast-v1"
_TRANSACTION_SCHEMA_VERSION = 1
_STREAM_GROUP_TARGET_ENTRY_LIMIT = 512


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


class AssetRipperBundleWorkflow:
    def __init__(
        self,
        exporter: _BundleExporter,
        dependency_scanner: _DependencyScanner,
        logger: LoggerPort,
        *,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self._exporter = exporter
        self._dependency_scanner = dependency_scanner
        self._logger = logger
        self._progress_factory = progress_factory or NullProgressReporterFactory()
        self._cancellation = cancellation or NeverCancelled()

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
        output_root.mkdir(parents=True, exist_ok=True)
        self._recover_publish_transaction(output_root)
        self._cleanup_staging(output_root)
        archives = self._normalize_inputs(context, inputs)
        if not archives:
            return BundleExtractionReport()
        manifest = self._load_manifest(output_root / "manifest.json", context)
        run_fingerprint = self._run_fingerprint(context, archives, filtered=filtered)
        warm = self._load_warm_report(output_root, manifest, run_fingerprint)
        if warm is not None:
            return warm

        warnings: list[str] = []
        with self._progress_factory.create(
            len(archives),
            "Extracting bundles...",
            extract_mode=True,
        ) as progress:
            try:
                progress.set_progress(
                    0,
                    len(archives),
                    stage="scanning",
                    unit="archives",
                    secondary_status="Scanning dependencies",
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
                progress.set_progress(
                    0,
                    len(entries),
                    stage="cache_fill",
                    unit="entries",
                    secondary_status="Preparing entry cache",
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
                    result, batches = self._export_streamed(
                        context,
                        prepared.executable,
                        resolved_by_node,
                        job_root,
                        progress,
                        concurrency=concurrency,
                    )
                    merged_assets, collection_failures = self._merge_results(
                        [result], job_root
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
                    self._publish_directory_transaction(
                        output_root,
                        publish_root,
                        new_manifest,
                    )
                finally:
                    shutil.rmtree(job_root, ignore_errors=True)
                progress.set_progress(
                    len(batches),
                    len(batches),
                    stage="exporting",
                    unit="batches",
                    status=f"{len(batches)}/{len(batches)} groups",
                    secondary_status="Bundle extraction complete",
                )
            except OperationCancelledError:
                progress.set_failed_status("Bundle extraction cancelled")
                raise
            except BaseException:
                progress.set_failed_status("Bundle extraction failed")
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
    ) -> tuple[AssetRipperExportResult, tuple[BundleExportBatch, ...]]:
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
        try:
            self._cancellation.raise_if_cancelled()
            progress.set_progress(
                0,
                len(groups),
                stage="loading",
                unit="groups",
                status=f"0/{len(groups)} groups",
                secondary_status="Loading bundle groups",
            )
            result = self._exporter.export_grouped(
                context,
                groups,
                job_root,
                concurrency=concurrency,
                event_callback=partial(
                    self._handle_export_event,
                    progress,
                    batch=aggregate,
                    completed_batches=0,
                    total_batches=len(groups),
                    logs=log_aggregator,
                ),
            )
            self._validate_result(aggregate, result, job_root)
        finally:
            log_aggregator.flush()
        return result, batches

    def _validate_result(
        self,
        batch: BundleExportBatch,
        result: AssetRipperExportResult,
        staging_root: Path,
    ) -> None:
        expected = set(batch.target_node_ids)
        if set(result.requested_target_ids) != expected:
            raise AssetRipperToolError(
                "AssetRipper result target set does not match the export request."
            )
        if not set(result.exported_target_ids) <= expected:
            raise AssetRipperToolError(
                "AssetRipper result contains unexpected target coverage."
            )
        stable_ids: set[str] = set()
        paths: set[str] = set()
        for asset in result.assets:
            if asset.stable_id in stable_ids:
                raise AssetRipperToolError(
                    "AssetRipper returned a duplicate stable ID."
                )
            stable_ids.add(asset.stable_id)
            identity = (
                f"{asset.normalized_collection}\n{asset.class_id}\n{asset.path_id}"
            )
            if hashlib.sha256(identity.encode()).hexdigest()[:20] != asset.stable_id:
                raise AssetRipperToolError("AssetRipper stable identity is invalid.")
            for item in asset.files:
                path = self._safe_child(staging_root, item.path)
                if not PurePosixPath(item.path).parts[0].casefold() == "assets":
                    raise AssetRipperToolError(
                        "AssetRipper output is outside the Assets layout."
                    )
                key = item.path.casefold()
                if key in paths:
                    raise AssetRipperToolError(
                        "AssetRipper returned duplicate output paths."
                    )
                paths.add(key)
                try:
                    stat = path.stat()
                except OSError as exc:
                    raise AssetRipperToolError(
                        "AssetRipper did not publish a declared output file."
                    ) from exc
                if stat.st_size != item.size or stat.st_mtime_ns != item.mtime_ns:
                    raise AssetRipperToolError(
                        "AssetRipper output metadata changed before publication."
                    )

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
                        "sha256": item.sha256,
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
            "tool_fingerprint": assetripper_exporter_cache_key(),
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
        if not filtered or old_manifest.get("schema_version") != 10:
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
        journal_path = output_root / ".bundle-publish.json"
        transaction_root = output_root / f".publish-{uuid4().hex}"
        transaction_root.mkdir()
        manifest_path = output_root / "manifest.json"
        manifest_backup = transaction_root / "manifest.backup"
        had_manifest = manifest_path.is_file()
        if had_manifest:
            shutil.copy2(manifest_path, manifest_backup)
        existing = self._existing_assets_directories(output_root)
        backups = [
            {
                "name": path.name,
                "backup": str(transaction_root / f"assets-{index}"),
            }
            for index, path in enumerate(existing)
        ]
        journal: dict[str, object] = {
            "schema_version": _TRANSACTION_SCHEMA_VERSION,
            "phase": "prepared",
            "transaction_root": str(transaction_root),
            "staged_assets": str(staged_assets),
            "had_manifest": had_manifest,
            "backups": backups,
        }
        write_json_atomic(journal_path, journal, separators=(",", ":"))
        try:
            for path, item in zip(existing, backups, strict=True):
                path.replace(Path(str(item["backup"])))
            public_assets = output_root / "Assets"
            staged_assets.replace(public_assets)
            journal["phase"] = "files_applied"
            write_json_atomic(journal_path, journal, separators=(",", ":"))
            write_json_atomic(
                manifest_path,
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            journal["phase"] = "manifest_committed"
            write_json_atomic(journal_path, journal, separators=(",", ":"))
        except BaseException:
            self._recover_publish_transaction(output_root)
            raise
        shutil.rmtree(transaction_root, ignore_errors=True)
        journal_path.unlink(missing_ok=True)

    def _recover_publish_transaction(self, output_root: Path) -> None:
        journal_path = output_root / ".bundle-publish.json"
        if not journal_path.is_file():
            return
        try:
            payload = json.loads(journal_path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise BundleExtractionError(
                "The bundle publish journal is corrupted; existing output was left unchanged."
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _TRANSACTION_SCHEMA_VERSION
            or payload.get("phase")
            not in {"prepared", "files_applied", "manifest_committed"}
            or not isinstance(payload.get("transaction_root"), str)
            or not isinstance(payload.get("staged_assets"), str)
            or not isinstance(payload.get("backups"), list)
        ):
            raise BundleExtractionError("The bundle publish journal is invalid.")
        transaction_root = Path(payload["transaction_root"]).resolve(strict=False)
        output_resolved = output_root.resolve(strict=False)
        if (
            transaction_root.parent != output_resolved
            or not transaction_root.name.startswith(".publish-")
        ):
            raise BundleExtractionError("The bundle publish journal is unsafe.")
        if payload["phase"] == "manifest_committed":
            shutil.rmtree(transaction_root, ignore_errors=True)
            journal_path.unlink(missing_ok=True)
            return
        staged_assets = Path(payload["staged_assets"])
        files_were_applied = (
            payload["phase"] == "files_applied" or not staged_assets.exists()
        )
        if files_were_applied:
            public_assets = output_root / "Assets"
            if public_assets.is_dir():
                shutil.rmtree(public_assets, ignore_errors=True)
        for item in payload["backups"]:
            if not isinstance(item, dict):
                raise BundleExtractionError("The bundle publish journal is invalid.")
            name = item.get("name")
            backup = item.get("backup")
            if (
                not isinstance(name, str)
                or name.casefold() != "assets"
                or not isinstance(backup, str)
            ):
                raise BundleExtractionError("The bundle publish journal is invalid.")
            source = Path(backup).resolve(strict=False)
            if source.parent != transaction_root:
                raise BundleExtractionError("The bundle publish journal is unsafe.")
            if source.exists():
                source.replace(output_root / name)
        manifest_path = output_root / "manifest.json"
        manifest_backup = transaction_root / "manifest.backup"
        if payload.get("had_manifest") is True and manifest_backup.is_file():
            os.replace(manifest_backup, manifest_path)
        elif payload.get("had_manifest") is False:
            manifest_path.unlink(missing_ok=True)
        shutil.rmtree(transaction_root, ignore_errors=True)
        journal_path.unlink(missing_ok=True)

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
        if isinstance(payload, dict) and payload.get("schema_version") == 9:
            return self._empty_manifest(context)
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
            or manifest.get("status") != "complete"
            or manifest.get("tool_fingerprint") != assetripper_exporter_cache_key()
            or manifest.get("profile") != _PROCESSING_PROFILE
        ):
            return None
        try:
            changed = self._validate_complete_inventory(output_root, manifest)
        except BundleExtractionError:
            return None
        if changed:
            write_json_atomic(
                output_root / "manifest.json",
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        return BundleExtractionReport(total_batches=1, succeeded_batches=1)

    def _validate_complete_inventory(
        self,
        output_root: Path,
        manifest: dict[str, object],
    ) -> bool:
        declared: set[str] = set()
        changed = False
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
                    if calculate_sha256(path) != item["sha256"]:
                        raise BundleExtractionError(
                            "A published bundle asset was modified; the extraction must be rebuilt."
                        )
                    item["mtime_ns"] = stat.st_mtime_ns
                    changed = True
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
        return changed

    @staticmethod
    def _valid_asset_record(stable_id: str, record: dict[str, object]) -> bool:
        files = record.get("files")
        collection = record.get("collection")
        normalized = record.get("normalized_collection")
        class_id = record.get("class_id")
        path_id = record.get("path_id")
        canonical_sources = record.get("canonical_sources")
        alias_sources = record.get("alias_sources")
        identity = f"{normalized}\n{class_id}\n{path_id}"
        return (
            len(stable_id) == 20
            and all(character in "0123456789abcdef" for character in stable_id)
            and hashlib.sha256(identity.encode()).hexdigest()[:20] == stable_id
            and isinstance(record.get("asset_type"), str)
            and isinstance(record.get("readable_name"), str)
            and isinstance(collection, str)
            and isinstance(normalized, str)
            and normalized == collection.replace("\\", "/").strip().lower()
            and isinstance(class_id, int)
            and not isinstance(class_id, bool)
            and isinstance(path_id, int)
            and not isinstance(path_id, bool)
            and isinstance(canonical_sources, list)
            and all(isinstance(item, str) and bool(item) for item in canonical_sources)
            and isinstance(alias_sources, list)
            and all(isinstance(item, str) and bool(item) for item in alias_sources)
            and isinstance(files, list)
            and bool(files)
            and all(
                isinstance(item, dict)
                and isinstance(item.get("path"), str)
                and str(item["path"]).startswith("Assets/")
                and isinstance(item.get("size"), int)
                and isinstance(item.get("mtime_ns"), int)
                and isinstance(item.get("sha256"), str)
                and len(str(item["sha256"])) == 64
                and all(
                    character in "0123456789abcdef" for character in str(item["sha256"])
                )
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
            "mode": "filtered" if filtered else "full",
            "resource_version": context.resource_version,
            "dependency_scanner": assetripper_dependency_scan_cache_key(),
            "exporter": assetripper_exporter_cache_key(),
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
            "tool_fingerprint": assetripper_exporter_cache_key(),
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
        ordered = sorted(
            plan.components,
            key=lambda item: min(entry.node_id.casefold() for entry in item.entries),
        )
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
            progress.set_progress(
                event.current,
                event.total,
                stage="scanning",
                unit="archives",
                secondary_status=event.archive_id,
            )

    @staticmethod
    def _handle_cache_event(
        progress: ProgressReporterPort,
        event: AssetRipperProcessEvent,
    ) -> None:
        if isinstance(event, AssetRipperEntryCacheProgressEvent):
            progress.set_progress(
                event.current,
                event.total,
                stage="cache_fill",
                unit="entries",
                secondary_status=event.node_id,
            )

    @staticmethod
    def _handle_export_event(
        progress: ProgressReporterPort,
        event: AssetRipperProcessEvent,
        batch: BundleExportBatch,
        completed_batches: int,
        total_batches: int,
        logs: _AssetRipperLogAggregator,
    ) -> None:
        status = f"{completed_batches}/{total_batches} batches"
        prefix = f"{batch.batch_id}: "
        if isinstance(event, AssetRipperLogEvent):
            logs.handle(event)
        elif isinstance(event, AssetRipperProcessorProgressEvent):
            progress.set_progress(
                event.current,
                event.total,
                stage="processing",
                unit="processors",
                status=status,
                secondary_status=(
                    f"{prefix}{event.processor.removesuffix('Processor')}"
                ),
            )
        elif isinstance(event, AssetRipperProgressEvent):
            progress.set_progress(
                event.current,
                event.total,
                stage=event.phase,
                unit="assets" if event.phase == "exporting" else "inputs",
                status=status,
                secondary_status=f"{prefix}{event.stage}",
            )
        elif isinstance(event, AssetRipperHeartbeatEvent):
            progress.set_progress(
                0,
                1,
                stage="processing",
                unit="processors",
                status=status,
                secondary_status=f"{prefix}Processing",
            )
        elif isinstance(event, AssetRipperPhaseEvent):
            progress.set_progress(
                0,
                1,
                stage=event.phase,
                unit="assets" if event.phase == "exporting" else "inputs",
                status=status,
                secondary_status=f"{prefix}{event.phase.title()}",
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
