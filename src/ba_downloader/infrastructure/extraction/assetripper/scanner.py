from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
)
from ba_downloader.infrastructure.extraction.assetripper.events import (
    AssetRipperProcessEvent,
    AssetRipperScanProgressEvent,
)
from ba_downloader.infrastructure.extraction.assetripper.scan_cache import (
    BundleDependencyScanCache,
)


class BundleDependencyScanBackend(Protocol):
    def scan(
        self,
        context: ExecutionContext,
        archives: list[BundleArchiveInput],
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> tuple[BundleArchiveScan, ...]: ...


class CachedBundleDependencyScanner:
    def __init__(
        self,
        backend: BundleDependencyScanBackend,
        cache: BundleDependencyScanCache,
        *,
        tool_key: str,
    ) -> None:
        self._backend = backend
        self._cache = cache
        self._tool_key = tool_key

    def scan(
        self,
        context: ExecutionContext,
        archives: list[BundleArchiveInput],
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> tuple[BundleArchiveScan, ...]:
        if not archives:
            return ()
        total = len(archives)
        result_by_id: dict[str, BundleArchiveScan] = {}
        misses: list[BundleArchiveInput] = []
        completed_ids: set[str] = set()

        def report(archive_id: str) -> None:
            if archive_id in completed_ids:
                return
            completed_ids.add(archive_id)
            if event_callback is not None:
                event_callback(
                    AssetRipperScanProgressEvent(
                        len(completed_ids),
                        total,
                        archive_id,
                    )
                )

        for archive in archives:
            cached = self._cache.load(archive, tool_key=self._tool_key)
            if cached is None:
                misses.append(archive)
                continue
            result_by_id[archive.archive_id] = cached
            report(archive.archive_id)

        if misses:
            missing_ids = {archive.archive_id for archive in misses}

            def handle_event(event: AssetRipperProcessEvent) -> None:
                if isinstance(event, AssetRipperScanProgressEvent):
                    if event.archive_id in missing_ids:
                        report(event.archive_id)
                    return
                if event_callback is not None:
                    event_callback(event)

            scanned = self._backend.scan(context, misses, handle_event)
            miss_by_id = {archive.archive_id: archive for archive in misses}
            for scan in scanned:
                miss_archive = miss_by_id.get(scan.archive_id)
                if miss_archive is None or scan.archive_id in result_by_id:
                    raise ValueError(
                        "Dependency scan results do not match cache misses."
                    )
                self._cache.store(miss_archive, scan, tool_key=self._tool_key)
                result_by_id[scan.archive_id] = scan
                report(scan.archive_id)
            if set(result_by_id) != {archive.archive_id for archive in archives}:
                raise ValueError("Dependency scan results do not match bundle inputs.")

        return tuple(result_by_id[archive.archive_id] for archive in archives)
