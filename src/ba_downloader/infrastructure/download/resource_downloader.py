from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Lock

from ba_downloader.domain.exceptions import DownloadError
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetRecord,
    ChecksumSpec,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.apk import (
    ZipEntry,
    extract_zip_entry,
    find_zip_entry,
    read_zip_entries,
)
from ba_downloader.infrastructure.download.adaptive import (
    AdaptiveDownloadState,
    classify_download_failure,
    decrease_target_concurrency,
    record_download_success,
)
from ba_downloader.infrastructure.download.immediate import ImmediateExtractionHandler
from ba_downloader.infrastructure.download.loop import (
    DownloadLoopContext,
    ResourceDownloadLoop,
)
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter
from ba_downloader.infrastructure.runtime.interrupts import (
    build_future_wait_policy,
    cancel_pending_futures,
    install_interrupt_handler,
)
from ba_downloader.shared.crypto.encryption import calculate_crc, calculate_md5

_AdaptiveDownloadState = AdaptiveDownloadState


class ResourceDownloader(ResourceDownloaderPort):
    DOWNLOAD_TIMEOUT_SECONDS = 600.0
    POLL_INTERVAL_SECONDS = 0.2
    INTERRUPT_GRACE_SECONDS = 2.0
    APK_ENTRY_SOURCE = "apk_entry"

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        *,
        force_exit: Callable[[int], None] | None = None,
        immediate_extraction_handler: ImmediateExtractionHandler | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self._zip_entry_cache: dict[tuple[str, str], ZipEntry] = {}
        self._zip_entries_by_url: dict[str, list[ZipEntry]] = {}
        self._force_exit = force_exit or os._exit
        self._immediate_extraction_handler = immediate_extraction_handler
        self._wait_policy = build_future_wait_policy(
            self.logger,
            self.POLL_INTERVAL_SECONDS,
            self.INTERRUPT_GRACE_SECONDS,
            "Downloads",
        )
        self._download_loop = ResourceDownloadLoop(
            wait_policy=self._wait_policy,
            download_resource=self._download_resource_for_loop,
            handle_successful_download=self._handle_successful_download,
        )

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
            failure_message = f"Failed to download {len(pending)} files after retries."
            failed_paths = ", ".join(resource.path for resource in pending[:5])
            if len(pending) > 5:
                failed_paths = f"{failed_paths}, ..."
            self.logger.error(failure_message)
            raise DownloadError(f"{failure_message} Failed resources: {failed_paths}")
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
            with (
                self._install_interrupt_handler(stop_event),
                RichProgressReporter(
                    len(resources),
                    "Verifying assets...",
                ) as progress,
            ):
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
        state = adaptive_state or self._create_adaptive_download_state(
            resources, context
        )
        progress_total, download_mode = self._resolve_download_progress(resources)
        stop_event = Event()
        executor = ThreadPoolExecutor(max_workers=state.upper_bound)
        progress_lock = Lock()
        failed_resources: list[AssetRecord] = []

        try:
            with (
                self._install_interrupt_handler(stop_event),
                RichProgressReporter(
                    progress_total,
                    "Downloading assets...",
                    download_mode=download_mode,
                ) as progress,
            ):
                loop_context = DownloadLoopContext(
                    progress=progress,
                    context=context,
                    progress_lock=progress_lock,
                    download_mode=download_mode,
                    executor=executor,
                    progress_callback=(
                        self._build_progress_callback(progress, progress_lock)
                        if download_mode
                        else None
                    ),
                )
                failed_resources = self._download_loop.run(
                    resources=resources,
                    loop_context=loop_context,
                    adaptive_state=state,
                    stop_event=stop_event,
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if stop_event.is_set():
            raise KeyboardInterrupt()

        return failed_resources

    @contextmanager
    def _install_interrupt_handler(self, stop_event: Event) -> Iterator[None]:
        with install_interrupt_handler(
            stop_event,
            self.logger,
            force_exit=self._force_exit,
            on_interrupt=self.http_client.close,
        ):
            yield

    def _handle_interrupt(self, stop_event: Event, interrupt_count: int) -> None:
        stop_event.set()
        self.http_client.close()
        if interrupt_count >= 2:
            self.logger.error("Force exiting immediately.")
            self._force_exit(130)

    @staticmethod
    def _resolve_download_progress(resources: list[AssetRecord]) -> tuple[int, bool]:
        total_bytes = sum(max(resource.size, 0) for resource in resources)
        download_mode = total_bytes > 0
        progress_total = total_bytes if download_mode else len(resources)
        return progress_total, download_mode

    @staticmethod
    def _build_progress_callback(
        progress: RichProgressReporter,
        progress_lock: Lock,
    ) -> Callable[[int], None]:
        def advance_progress(amount: int) -> None:
            with progress_lock:
                progress.advance(amount)

        return advance_progress

    def _handle_successful_download(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
    ) -> None:
        if not context.extract_while_download:
            return
        if self._immediate_extraction_handler is None:
            return
        self._immediate_extraction_handler(resource, context)

    def _download_resource_for_loop(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
        progress_callback: Callable[[int], None] | None,
        should_stop: Callable[[], bool],
    ) -> AssetRecord:
        return self._download_resource(
            resource,
            context,
            progress_callback,
            should_stop,
        )

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
                cancel_pending_futures(pending_futures)

            for future in done_futures:
                if future.cancelled():
                    continue
                resource_item, verified = future.result()
                progress.set_description(f"Verifying {Path(resource_item.path).name}")
                progress.advance()
                if not verified:
                    pending.append(resource_item)

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

    @staticmethod
    def _classify_download_failure(exc: Exception) -> str:
        return classify_download_failure(exc)

    @staticmethod
    def _decrease_target_concurrency(state: _AdaptiveDownloadState) -> bool:
        return decrease_target_concurrency(state)

    @staticmethod
    def _record_download_success(state: _AdaptiveDownloadState) -> bool:
        return record_download_success(state)

    def _verify_resource(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
    ) -> tuple[AssetRecord, bool]:
        asset_path = Path(context.raw_dir) / resource.path
        if not asset_path.exists():
            return resource, False
        return resource, self._get_validation_error(asset_path, resource) is None

    def _get_validation_error(
        self, asset_path: Path, resource: AssetRecord
    ) -> str | None:
        if not asset_path.exists():
            return "downloaded file is missing"

        if self._is_apk_entry_resource(resource):
            zip_entry = self._resolve_apk_zip_entry(resource)
            actual_size = asset_path.stat().st_size
            if actual_size != zip_entry.uncompressed_size:
                return (
                    "size mismatch "
                    f"(expected {zip_entry.uncompressed_size} bytes, got {actual_size} bytes)"
                )
            actual_crc = calculate_crc(str(asset_path))
            if actual_crc != zip_entry.crc32:
                return "checksum mismatch for crc"
            return None

        actual_size = asset_path.stat().st_size
        if actual_size != resource.size:
            return f"size mismatch (expected {resource.size} bytes, got {actual_size} bytes)"

        if not self._matches_checksum(asset_path, resource.checksum):
            return f"checksum mismatch for {resource.checksum.algorithm}"

        return None

    @classmethod
    def _matches_checksum(cls, asset_path: Path, checksum: ChecksumSpec) -> bool:
        normalized_value = checksum.value.strip()
        if not normalized_value:
            return False

        if checksum.algorithm == "crc":
            expected_crc_values = cls._parse_crc_values(normalized_value)
            if not expected_crc_values:
                return False
            return calculate_crc(str(asset_path)) in expected_crc_values

        if checksum.algorithm == "md5":
            return (
                calculate_md5(str(asset_path)).casefold() == normalized_value.casefold()
            )

        return False

    @staticmethod
    def _parse_crc_values(value: str) -> set[int]:
        normalized = value.strip()
        if not normalized:
            return set()

        lowered = normalized.casefold()
        if lowered.startswith("0x"):
            try:
                return {int(normalized[2:], 16)}
            except ValueError:
                return set()

        if any(character in "abcdef" for character in lowered):
            try:
                return {int(normalized, 16)}
            except ValueError:
                return set()

        values: set[int] = set()
        for base in (10, 16):
            try:
                values.add(int(normalized, base))
            except ValueError:
                continue
        return values

    def _download_resource(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
        progress_callback: Callable[[int], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> AssetRecord:
        asset_path = Path(context.raw_dir) / resource.path
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        if self._is_apk_entry_resource(resource):
            zip_entry = self._resolve_apk_zip_entry(resource)
            extract_zip_entry(
                resource.url,
                zip_entry,
                asset_path,
                self.http_client,
                timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
            )
            self._validate_downloaded_resource(asset_path, resource)
            return resource

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

    def _validate_downloaded_resource(
        self, asset_path: Path, resource: AssetRecord
    ) -> None:
        validation_error = self._get_validation_error(asset_path, resource)
        if validation_error is None:
            return

        asset_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"post-download validation failed for {resource.path}: {validation_error}"
        )

    @classmethod
    def _is_apk_entry_resource(cls, resource: AssetRecord) -> bool:
        return resource.metadata.get("source") == cls.APK_ENTRY_SOURCE

    def _resolve_apk_zip_entry(self, resource: AssetRecord) -> ZipEntry:
        entry_path = str(resource.metadata.get("apk_entry_path", "")).strip()
        if not entry_path:
            raise RuntimeError(f"APK entry metadata is missing for {resource.path}.")

        cache_key = (resource.url, entry_path)
        cached_entry = self._zip_entry_cache.get(cache_key)
        if cached_entry is not None:
            return cached_entry

        entries = self._zip_entries_by_url.get(resource.url)
        if entries is None:
            entries = read_zip_entries(resource.url, self.http_client)
            self._zip_entries_by_url[resource.url] = entries

        zip_entry = find_zip_entry(
            entries,
            preferred_path=entry_path,
            fallback_name=Path(entry_path).name,
        )
        self._zip_entry_cache[cache_key] = zip_entry
        return zip_entry
