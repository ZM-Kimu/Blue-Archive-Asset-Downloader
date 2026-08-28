from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection, AssetType, ChecksumSpec
from ba_downloader.domain.models.bundle import BundleHandler
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.extraction import ExtractionReport
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.extract import AssetExtractionPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import ProgressReporterFactoryPort
from ba_downloader.infrastructure.download.bundle_members import (
    extract_local_bundle_member,
    find_exact_entry,
    member_cache_path,
    read_local_zip_entries,
)
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
)
from ba_downloader.infrastructure.extraction.bundles import (
    BundleExtractionReport,
)
from ba_downloader.infrastructure.extraction.errors import BundleExtractionError
from ba_downloader.infrastructure.extraction.media.exporter import (
    MediaArchiveExtractor,
)
from ba_downloader.infrastructure.extraction.process_table_runner import (
    ProcessTableExtractionRunner,
    TableProfileFactory,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    build_default_table_profile_for_context,
)
from ba_downloader.infrastructure.files.checksum import calculate_crc
from ba_downloader.infrastructure.progress import NullProgressReporterFactory


class _BundleWorkflow(Protocol):
    def run(
        self,
        context: ExecutionContext,
        inputs: Sequence[Path | BundleArchiveInput],
        *,
        concurrency: int,
        filtered: bool = False,
    ) -> BundleExtractionReport: ...


class AssetExtractionWorkflow(AssetExtractionPort):
    POLL_INTERVAL_SECONDS = 0.2
    INTERRUPT_GRACE_SECONDS = 2.0

    def __init__(
        self,
        logger: LoggerPort,
        *,
        table_profile_factory: TableProfileFactory = build_default_table_profile_for_context,
        force_exit: Callable[[int], None] | None = None,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
        bundle_workflow: _BundleWorkflow | None = None,
        unitypy_bundle_workflow: _BundleWorkflow | None = None,
        media_extractor: MediaArchiveExtractor | None = None,
    ) -> None:
        self.logger = logger
        self._force_exit = force_exit or os._exit
        self._table_profile_factory = table_profile_factory
        self._progress_factory = progress_factory or NullProgressReporterFactory()
        self._cancellation = cancellation or NeverCancelled()
        self._bundle_workflow = bundle_workflow
        self._unitypy_bundle_workflow = unitypy_bundle_workflow
        self._media_extractor = media_extractor
        self._process_table_runner = ProcessTableExtractionRunner(
            logger,
            poll_interval_seconds=self.POLL_INTERVAL_SECONDS,
            interrupt_grace_seconds=self.INTERRUPT_GRACE_SECONDS,
            table_profile_factory=self._table_profile_factory,
            force_exit=self._force_exit,
            progress_factory=self._progress_factory,
            cancellation=self._cancellation,
        )

    def extract_bundles(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
        filtered: bool = False,
        handler: BundleHandler = BundleHandler.assetripper,
    ) -> ExtractionReport:
        self._cancellation.raise_if_cancelled()
        bundles = self._resolve_bundle_inputs(context, resources)
        if not bundles:
            return ExtractionReport()

        workflow: _BundleWorkflow | None
        if handler is BundleHandler.assetripper:
            workflow = self._bundle_workflow
        elif handler is BundleHandler.unitypy:
            workflow = self._unitypy_bundle_workflow
        else:
            raise ValueError(f"Unsupported bundle handler '{handler}'.")
        if workflow is None:
            raise RuntimeError(f"{handler.value} bundle workflow is not configured.")
        report = workflow.run(
            context,
            bundles,
            concurrency=concurrency,
            filtered=filtered,
        )
        return ExtractionReport(report.warnings)

    def extract_media(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
    ) -> ExtractionReport:
        self._cancellation.raise_if_cancelled()
        files = self._resolve_media_files(context, resources)
        if not files:
            return ExtractionReport()

        if self._media_extractor is None:
            raise RuntimeError("Media archive extractor is not configured.")
        self._media_extractor.extract(
            context,
            files,
            concurrency=concurrency,
        )
        return ExtractionReport()

    def extract_tables(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
    ) -> ExtractionReport:
        self._cancellation.raise_if_cancelled()
        table_files = [
            table_path.name
            for table_path in self._resolve_table_files(context, resources)
        ]
        if not table_files:
            return ExtractionReport()

        table_file_metadata = self._resolve_table_file_metadata(context, resources)
        context.workspace.extracted_table_semantic.mkdir(
            parents=True,
            exist_ok=True,
        )
        if table_file_metadata:
            self._process_table_runner.run(
                table_files,
                context,
                concurrency=concurrency,
                metadata_by_file=table_file_metadata,
            )
            return ExtractionReport()

        self._process_table_runner.run(table_files, context, concurrency=concurrency)
        return ExtractionReport()

    def _resolve_bundle_files(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None,
    ) -> list[Path]:
        if resources is not None:
            return self._resolve_existing_resource_files(
                context,
                resources,
                AssetType.bundle,
            )

        bundle_folder = context.workspace.raw_bundles
        if not bundle_folder.exists():
            return []
        return [
            bundle_folder / bundle.name
            for bundle in bundle_folder.iterdir()
            if bundle.is_file()
        ]

    def _resolve_bundle_inputs(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None,
    ) -> list[BundleArchiveInput]:
        if resources is None:
            return [
                BundleArchiveInput.from_path(path)
                for path in self._resolve_bundle_files(context, None)
            ]
        result: list[BundleArchiveInput] = []
        seen_paths: set[Path] = set()
        missing_members: list[str] = []
        for resource in resources:
            if resource.asset_type is not AssetType.bundle:
                continue
            if resource.selected_member_paths:
                archive_path = context.workspace.raw_resource_path(
                    resource.asset_type.value,
                    resource.path,
                )
                local_entries = None
                for member in resource.selected_member_paths:
                    path = member_cache_path(context, resource, member)
                    entry = None
                    if not path.is_file() and archive_path.is_file():
                        if local_entries is None:
                            local_entries = read_local_zip_entries(archive_path)
                        entry = find_exact_entry(local_entries, member)
                        extract_local_bundle_member(archive_path, entry, path)
                    if not path.is_file():
                        missing_members.append(f"{resource.path}::{member}")
                        continue
                    if path in seen_paths:
                        continue
                    normalized_archive = resource.path.replace("\\", "/")
                    normalized_member = member.replace("\\", "/")
                    result.append(
                        BundleArchiveInput.from_path(
                            path,
                            archive_id=f"{normalized_archive}#{normalized_member}",
                            checksum=ChecksumSpec("crc", str(calculate_crc(path))),
                        )
                    )
                    seen_paths.add(path)
                continue
            path = context.workspace.raw_resource_path(
                resource.asset_type.value,
                resource.path,
            )
            if path in seen_paths or not path.is_file():
                continue
            result.append(
                BundleArchiveInput.from_path(
                    path,
                    archive_id=resource.path.replace("\\", "/"),
                    checksum=resource.checksum,
                )
            )
            seen_paths.add(path)
        if missing_members:
            examples = ", ".join(missing_members[:3])
            suffix = "" if len(missing_members) <= 3 else ", ..."
            raise BundleExtractionError(
                "Direct bundle member cache is incomplete: "
                f"{len(missing_members)} member(s) are missing "
                f"({examples}{suffix}). Run assets sync or download with the same "
                "filter first."
            )
        return result

    def _resolve_media_files(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None,
    ) -> list[Path]:
        if resources is not None:
            return [
                file_path
                for file_path in self._resolve_existing_resource_files(
                    context,
                    resources,
                    AssetType.media,
                )
                if file_path.suffix.lower() == ".zip"
            ]

        media_folder = context.workspace.raw_media
        if not media_folder.exists():
            return []
        return list(media_folder.rglob("*.zip"))

    def _resolve_table_files(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None,
    ) -> list[Path]:
        if resources is not None:
            return self._resolve_existing_resource_files(
                context,
                resources,
                AssetType.table,
            )

        table_folder = context.workspace.raw_tables
        if not table_folder.exists():
            return []
        return [
            file_path for file_path in table_folder.iterdir() if file_path.is_file()
        ]

    @staticmethod
    def _resolve_existing_resource_files(
        context: ExecutionContext,
        resources: AssetCollection,
        asset_type: AssetType,
    ) -> list[Path]:
        files: list[Path] = []
        seen_paths: set[Path] = set()
        for resource in resources:
            if resource.asset_type is not asset_type:
                continue
            file_path = context.workspace.raw_resource_path(
                resource.asset_type.value,
                resource.path,
            )
            if file_path in seen_paths or not file_path.is_file():
                continue
            files.append(file_path)
            seen_paths.add(file_path)
        return files

    @staticmethod
    def _resolve_table_file_metadata(
        context: ExecutionContext,
        resources: AssetCollection | None,
    ) -> dict[str, dict[str, object]]:
        if resources is None:
            return {}
        result: dict[str, dict[str, object]] = {}
        for resource in resources:
            if resource.asset_type is not AssetType.table:
                continue
            file_path = context.workspace.raw_resource_path(
                resource.asset_type.value,
                resource.path,
            )
            if not file_path.is_file():
                continue
            if resource.metadata:
                result.setdefault(file_path.name, dict(resource.metadata))
        return result
