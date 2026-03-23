from __future__ import annotations

import os
import signal
from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Lock, current_thread, main_thread
from time import monotonic
from typing import Callable, Iterator

from ba_downloader.domain.models.asset import AssetCollection, AssetRecord, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.bundle import BundleExtractor
from ba_downloader.infrastructure.extractors.media import MediaExtractor
from ba_downloader.infrastructure.extractors.table import TableExtractor
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter
from ba_downloader.shared.crypto.encryption import calculate_crc, calculate_md5


class ResourceDownloader(ResourceDownloaderPort):
    DOWNLOAD_TIMEOUT_SECONDS = 300.0
    POLL_INTERVAL_SECONDS = 0.2
    INTERRUPT_GRACE_SECONDS = 2.0

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        *,
        force_exit: Callable[[int], None] | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self._bundle_lock = Lock()
        self._force_exit = force_exit or os._exit

    def verify_and_download(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> None:
        if not resources:
            return

        Path(context.temp_dir).mkdir(parents=True, exist_ok=True)
        Path(context.raw_dir).mkdir(parents=True, exist_ok=True)
        Path(context.extract_dir).mkdir(parents=True, exist_ok=True)

        resources.sorted_by_size()
        pending = self._verify_resources(resources, context)
        if not pending:
            self.logger.warn("All files have already been downloaded.")
            return

        attempt = 0
        while pending and attempt <= context.max_retries:
            if attempt:
                self.logger.warn(
                    f"Retrying {len(pending)} failed files. Attempt {attempt}/{context.max_retries}."
                )
            pending = self._download_resources(pending, context)
            attempt += 1

        if pending:
            self.logger.error(f"Failed to download {len(pending)} files after retries.")
        else:
            self.logger.warn("All files have been downloaded to your computer.")

    def _verify_resources(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> list[AssetRecord]:
        pending: list[AssetRecord] = []
        workers = min(max(context.threads, 1), max(len(resources), 1))
        stop_event = Event()
        executor = ThreadPoolExecutor(max_workers=workers)
        future_map: dict[Future[tuple[AssetRecord, bool]], AssetRecord] = {}

        try:
            with self._install_interrupt_handler(stop_event):
                with RichProgressReporter(len(resources), "Verifying assets...") as progress:
                    future_map = {
                        executor.submit(self._verify_resource, resource, context): resource
                        for resource in resources
                    }
                    self._drain_verification_futures(
                        set(future_map),
                        future_map,
                        stop_event,
                        progress,
                        pending,
                    )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if stop_event.is_set():
            raise KeyboardInterrupt()

        return pending

    def _download_resources(
        self,
        resources: list[AssetRecord],
        context: RuntimeContext,
    ) -> list[AssetRecord]:
        failed: list[AssetRecord] = []
        workers = min(max(context.threads, 1), max(len(resources), 1))
        total_bytes = sum(max(resource.size, 0) for resource in resources)
        download_mode = total_bytes > 0
        progress_total = total_bytes if download_mode else len(resources)
        progress_lock = Lock()
        completed_files = 0
        stop_event = Event()
        executor = ThreadPoolExecutor(max_workers=workers)
        future_map: dict[Future[AssetRecord], AssetRecord] = {}

        try:
            with self._install_interrupt_handler(stop_event):
                with RichProgressReporter(
                    progress_total,
                    f"Downloading assets (0/{len(resources)} files)",
                    download_mode=download_mode,
                ) as progress:

                    def advance_progress(amount: int) -> None:
                        if not download_mode:
                            return
                        with progress_lock:
                            progress.advance(amount)

                    future_map = {
                        executor.submit(
                            self._download_resource,
                            resource,
                            context,
                            advance_progress if download_mode else None,
                            stop_event.is_set,
                        ): resource
                        for resource in resources
                    }

                    cancellation_logged = False
                    force_hint_logged = False
                    grace_deadline: float | None = None
                    pending_futures = set(future_map)

                    while pending_futures:
                        done_futures, pending_futures = wait(
                            pending_futures,
                            timeout=self.POLL_INTERVAL_SECONDS,
                            return_when=FIRST_COMPLETED,
                        )

                        if stop_event.is_set():
                            if not cancellation_logged:
                                self.logger.warn("Cancelling active downloads...")
                                cancellation_logged = True
                                grace_deadline = monotonic() + self.INTERRUPT_GRACE_SECONDS
                            for pending_future in pending_futures:
                                pending_future.cancel()
                            if (
                                pending_futures
                                and grace_deadline is not None
                                and monotonic() >= grace_deadline
                                and not force_hint_logged
                            ):
                                self.logger.warn(
                                    "Downloads are still stopping. Press Ctrl+C again to force exit."
                                )
                                force_hint_logged = True

                        for future in done_futures:
                            resource_item = future_map[future]
                            if future.cancelled():
                                continue
                            try:
                                downloaded_item = future.result()
                            except CancelledError:
                                continue
                            except Exception as exc:
                                if stop_event.is_set() and self._is_cancelled_error(exc):
                                    continue
                                self.logger.error(
                                    f"Failed to download {resource_item.path}: {exc}"
                                )
                                failed.append(resource_item)
                                continue

                            completed_files += 1
                            with progress_lock:
                                progress.set_description(
                                    f"Downloading assets ({completed_files}/{len(resources)} files)"
                                )
                                if not download_mode:
                                    progress.advance()

                            if context.extract_while_download:
                                self._extract_resource(downloaded_item, context)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if stop_event.is_set():
            raise KeyboardInterrupt()

        return failed

    @contextmanager
    def _install_interrupt_handler(self, stop_event: Event) -> Iterator[None]:
        if current_thread() is not main_thread():
            yield
            return

        previous_handler = signal.getsignal(signal.SIGINT)
        interrupt_count = 0

        def handle_interrupt(signum: int, frame: object | None) -> None:
            nonlocal interrupt_count
            _ = (signum, frame)
            interrupt_count += 1
            self._handle_interrupt(stop_event, interrupt_count)

        try:
            signal.signal(signal.SIGINT, handle_interrupt)
            yield
        finally:
            signal.signal(signal.SIGINT, previous_handler)

    def _handle_interrupt(self, stop_event: Event, interrupt_count: int) -> None:
        stop_event.set()
        self.http_client.close()
        if interrupt_count >= 2:
            self.logger.error("Force exiting immediately.")
            self._force_exit(130)

    def _drain_verification_futures(
        self,
        pending_futures: set[Future[tuple[AssetRecord, bool]]],
        future_map: dict[Future[tuple[AssetRecord, bool]], AssetRecord],
        stop_event: Event,
        progress: RichProgressReporter,
        pending: list[AssetRecord],
    ) -> None:
        while pending_futures:
            done_futures, pending_futures = wait(
                pending_futures,
                timeout=self.POLL_INTERVAL_SECONDS,
                return_when=FIRST_COMPLETED,
            )
            if stop_event.is_set():
                for pending_future in pending_futures:
                    pending_future.cancel()

            for future in done_futures:
                if future.cancelled():
                    continue
                resource_item, verified = future.result()
                progress.set_description(f"Verifying {Path(resource_item.path).name}")
                progress.advance()
                if not verified:
                    pending.append(resource_item)

    @staticmethod
    def _is_cancelled_error(exc: Exception) -> bool:
        return "download cancelled by user" in str(exc).lower()

    def _verify_resource(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
    ) -> tuple[AssetRecord, bool]:
        asset_path = Path(context.raw_dir) / resource.path
        if not asset_path.exists() or asset_path.stat().st_size != resource.size:
            return resource, False

        if resource.checksum.algorithm == "crc":
            return resource, calculate_crc(str(asset_path)) == resource.checksum.value
        if resource.checksum.algorithm == "md5":
            return resource, calculate_md5(str(asset_path)) == resource.checksum.value
        return resource, False

    def _download_resource(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
        progress_callback: Callable[[int], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> AssetRecord:
        asset_path = Path(context.raw_dir) / resource.path
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        self.http_client.download_to_file(
            resource.url,
            str(asset_path),
            timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        return resource

    def _extract_resource(self, resource: AssetRecord, context: RuntimeContext) -> None:
        resource_path = str(Path(context.raw_dir) / resource.path)

        if resource.asset_type == AssetType.bundle:
            with self._bundle_lock:
                BundleExtractor(context, self.logger).extract_bundle(
                    resource_path,
                    BundleExtractor.MAIN_EXTRACT_TYPES,
                )
            return

        if resource.asset_type == AssetType.media and resource.path.endswith(".zip"):
            MediaExtractor(context).extract_zip(resource_path)
            return

        if resource.asset_type == AssetType.table:
            TableExtractor.from_context(context, self.logger).extract_table(resource_path)
