from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import os
import signal
from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from math import ceil
from pathlib import Path
from threading import Event, Lock, current_thread, main_thread
from time import monotonic
from collections.abc import Callable, Iterator

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetRecord,
    AssetType,
    ChecksumSpec,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.bundle import BundleExtractor
from ba_downloader.infrastructure.extractors.media import MediaExtractor
from ba_downloader.infrastructure.extractors.table import TableExtractor
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter
from ba_downloader.shared.crypto.encryption import calculate_crc, calculate_md5


@dataclass(slots=True)
class _AdaptiveDownloadState:
    upper_bound: int
    target_concurrency: int
    success_since_adjustment: int = 0


class ResourceDownloader(ResourceDownloaderPort):
    DOWNLOAD_TIMEOUT_SECONDS = 600.0
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
            self.logger.info("All files have already been downloaded.")
            return

        adaptive_state = self._create_adaptive_download_state(pending, context)
        attempt = 0
        while pending and attempt <= context.max_retries:
            if attempt:
                self.logger.warn(
                    f"Retrying {len(pending)} failed files. Attempt {attempt}/{context.max_retries}."
                )
            pending = self._download_resources(
                pending,
                context,
                adaptive_state=adaptive_state,
            )
            attempt += 1

        if pending:
            self.logger.error(f"Failed to download {len(pending)} files after retries.")
        else:
            self.logger.info("All files have been downloaded to your computer.")

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
        *,
        adaptive_state: _AdaptiveDownloadState | None = None,
    ) -> list[AssetRecord]:
        failed: list[AssetRecord] = []
        state = adaptive_state or self._create_adaptive_download_state(resources, context)
        total_bytes = sum(max(resource.size, 0) for resource in resources)
        download_mode = total_bytes > 0
        progress_total = total_bytes if download_mode else len(resources)
        progress_lock = Lock()
        completed_files = 0
        stop_event = Event()
        executor = ThreadPoolExecutor(max_workers=state.upper_bound)
        future_map: dict[Future[AssetRecord], AssetRecord] = {}
        pending_resources = deque(resources)

        try:
            with self._install_interrupt_handler(stop_event):
                with RichProgressReporter(
                    progress_total,
                    "Downloading assets...",
                    download_mode=download_mode,
                ) as progress:
                    self._update_download_progress_status(
                        progress,
                        completed_files=0,
                        total_files=len(resources),
                        failed_files=0,
                        state=state,
                    )

                    def advance_progress(amount: int) -> None:
                        if not download_mode:
                            return
                        with progress_lock:
                            progress.advance(amount)

                    cancellation_logged = False
                    force_hint_logged = False
                    grace_deadline: float | None = None
                    total_files = len(resources)

                    while pending_resources or future_map:
                        if stop_event.is_set() and not future_map:
                            break

                        self._fill_download_futures(
                            future_map,
                            pending_resources,
                            executor,
                            context,
                            progress,
                            advance_progress if download_mode else None,
                            stop_event,
                            state,
                        )

                        if not future_map:
                            if stop_event.is_set():
                                break
                            continue

                        done_futures, pending_futures = wait(
                            set(future_map),
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

                        successful_downloads: list[AssetRecord] = []
                        decrease_reason: str | None = None

                        for future in done_futures:
                            resource_item = future_map.pop(future)
                            if future.cancelled():
                                continue
                            try:
                                downloaded_item = future.result()
                            except CancelledError:
                                continue
                            except Exception as exc:
                                if stop_event.is_set() and self._is_cancelled_error(exc):
                                    continue
                                failed.append(resource_item)
                                failure_kind = self._classify_download_failure(exc)
                                if failure_kind != "other" and decrease_reason is None:
                                    decrease_reason = failure_kind
                                continue

                            successful_downloads.append(downloaded_item)

                        if decrease_reason is not None:
                            self._decrease_target_concurrency(state)
                        else:
                            for _ in successful_downloads:
                                self._record_download_success(state)

                        for downloaded_item in successful_downloads:
                            completed_files += 1
                            with progress_lock:
                                if not download_mode:
                                    progress.advance()

                            if context.extract_while_download:
                                self._extract_resource(downloaded_item, context)

                        with progress_lock:
                            self._update_download_progress_status(
                                progress,
                                completed_files=completed_files,
                                total_files=total_files,
                                failed_files=len(failed),
                                state=state,
                            )
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

    def _create_adaptive_download_state(
        self,
        resources: list[AssetRecord],
        context: RuntimeContext,
    ) -> _AdaptiveDownloadState:
        upper_bound = min(max(context.threads, 1), max(len(resources), 1))
        return _AdaptiveDownloadState(
            upper_bound=upper_bound,
            target_concurrency=upper_bound,
        )

    def _fill_download_futures(
        self,
        future_map: dict[Future[AssetRecord], AssetRecord],
        pending_resources: deque[AssetRecord],
        executor: ThreadPoolExecutor,
        context: RuntimeContext,
        progress: RichProgressReporter,
        progress_callback: Callable[[int], None] | None,
        stop_event: Event,
        state: _AdaptiveDownloadState,
    ) -> None:
        while (
            not stop_event.is_set()
            and len(future_map) < state.target_concurrency
            and pending_resources
        ):
            resource = pending_resources.popleft()
            future = executor.submit(
                self._download_resource,
                resource,
                context,
                progress_callback,
                stop_event.is_set,
            )
            future_map[future] = resource
            progress.set_description(Path(resource.path).name)

    def _update_download_progress_status(
        self,
        progress: RichProgressReporter,
        *,
        completed_files: int,
        total_files: int,
        failed_files: int,
        state: _AdaptiveDownloadState,
    ) -> None:
        progress.set_status(self._build_download_file_status(completed_files, total_files))
        progress.set_secondary_status(self._build_download_concurrency_status(total_files, state))
        progress.set_failed_status(self._build_download_failed_status(failed_files))

    @staticmethod
    def _build_download_file_status(
        completed_files: int,
        total_files: int,
    ) -> str:
        return f"{completed_files}/{total_files} files"

    @staticmethod
    def _build_download_concurrency_status(
        total_files: int,
        state: _AdaptiveDownloadState,
    ) -> str:
        current_concurrency = min(state.target_concurrency, max(total_files, 1))
        return f"conc. {current_concurrency}/{state.upper_bound}"

    @staticmethod
    def _build_download_failed_status(failed_files: int) -> str:
        return f"failed {failed_files}"

    @staticmethod
    def _classify_download_failure(exc: Exception) -> str:
        message = str(exc).lower()
        if "timed out" in message:
            return "timeout"
        if "429" in message or "403" in message:
            return "throttled"
        if any(
            marker in message
            for marker in ("connection", "reset", "aborted", "broken pipe")
        ):
            return "connection"
        return "other"

    @staticmethod
    def _decrease_target_concurrency(state: _AdaptiveDownloadState) -> bool:
        state.success_since_adjustment = 0
        next_target = max(1, ceil(state.target_concurrency / 2))
        if next_target == state.target_concurrency:
            return False
        state.target_concurrency = next_target
        return True

    @staticmethod
    def _record_download_success(state: _AdaptiveDownloadState) -> bool:
        state.success_since_adjustment += 1
        if state.success_since_adjustment < 2:
            return False

        state.success_since_adjustment = 0
        if state.target_concurrency >= state.upper_bound:
            return False

        state.target_concurrency += 1
        return True

    def _verify_resource(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
    ) -> tuple[AssetRecord, bool]:
        asset_path = Path(context.raw_dir) / resource.path
        return resource, self._get_validation_error(asset_path, resource) is None

    @classmethod
    def _get_validation_error(cls, asset_path: Path, resource: AssetRecord) -> str | None:
        if not asset_path.exists():
            return "downloaded file is missing"

        actual_size = asset_path.stat().st_size
        if actual_size != resource.size:
            return f"size mismatch (expected {resource.size} bytes, got {actual_size} bytes)"

        if not cls._matches_checksum(asset_path, resource.checksum):
            return f"checksum mismatch for {resource.checksum.algorithm}"

        return None

    @classmethod
    def _matches_checksum(cls, asset_path: Path, checksum: ChecksumSpec) -> bool:
        normalized_value = checksum.value.strip()
        if not normalized_value:
            return False

        if checksum.algorithm == "crc":
            expected_crc = cls._parse_crc_value(normalized_value)
            if expected_crc is None:
                return False
            return calculate_crc(str(asset_path)) == expected_crc

        if checksum.algorithm == "md5":
            return calculate_md5(str(asset_path)).casefold() == normalized_value.casefold()

        return False

    @staticmethod
    def _parse_crc_value(value: str) -> int | None:
        normalized = value.strip()
        if not normalized:
            return None

        lowered = normalized.casefold()
        if lowered.startswith("0x"):
            normalized = normalized[2:]
            lowered = lowered[2:]

        if not normalized:
            return None

        base = 16 if any(character in "abcdef" for character in lowered) else 10
        try:
            return int(normalized, base)
        except ValueError:
            return None

    def _download_resource(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
        progress_callback: Callable[[int], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> AssetRecord:
        asset_path = Path(context.raw_dir) / resource.path
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        download_result = self.http_client.download_to_file(
            resource.url,
            str(asset_path),
            timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        if download_result.status_code >= 400:
            asset_path.unlink(missing_ok=True)
            raise RuntimeError(f"unexpected HTTP status {download_result.status_code}")

        self._validate_downloaded_resource(asset_path, resource)
        return resource

    def _validate_downloaded_resource(self, asset_path: Path, resource: AssetRecord) -> None:
        validation_error = self._get_validation_error(asset_path, resource)
        if validation_error is None:
            return

        asset_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"post-download validation failed for {resource.path}: {validation_error}"
        )

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
