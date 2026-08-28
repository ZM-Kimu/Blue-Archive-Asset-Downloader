from __future__ import annotations

import os
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from contextlib import contextmanager, suppress
from dataclasses import replace
from pathlib import Path
from threading import Event, Lock, Thread

from ba_downloader.domain.exceptions import (
    DownloadError,
    NetworkError,
    OperationCancelledError,
)
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetRecord,
    ChecksumSpec,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import (
    ProgressMeasure,
    ProgressReporterFactoryPort,
    ProgressReporterPort,
    ProgressStage,
    ProgressState,
    ProgressWorkers,
)
from ba_downloader.infrastructure.download.adaptive import (
    AdaptiveDownloadState,
    classify_download_failure,
    decrease_target_concurrency,
    record_download_success,
)
from ba_downloader.infrastructure.download.bundle_members import (
    BUNDLE_MEMBER_SOURCE,
    build_member_download_plan,
    extract_local_bundle_member,
    is_bundle_member_selection,
    materialize_member_alias,
    read_local_zip_entries,
)
from ba_downloader.infrastructure.download.loop import (
    DownloadLoopContext,
    DownloadProgress,
    ResourceDownloadLoop,
)
from ba_downloader.infrastructure.files.checksum import calculate_crc, calculate_md5
from ba_downloader.infrastructure.files.size import format_file_size
from ba_downloader.infrastructure.packages import (
    ZipEntry,
    extract_zip_entry,
    find_zip_entry,
    read_zip_entries,
)
from ba_downloader.infrastructure.packages.zip_range_reader import (
    UnsupportedZipLayoutError,
    ZipCentralDirectoryError,
)
from ba_downloader.infrastructure.progress import NullProgressReporterFactory
from ba_downloader.infrastructure.runtime.interrupts import (
    SignalInterruptState,
    build_future_wait_policy,
    cancel_pending_futures,
    install_interrupt_handler,
)

_AdaptiveDownloadState = AdaptiveDownloadState


class _TrackedDownloadProgress:
    def __init__(self, progress: DownloadProgress, lock: Lock) -> None:
        self._progress = progress
        self._lock = lock

    def __call__(self, amount: int) -> None:
        with self._lock:
            self._progress.advance(amount)

    def adjust_total(self, amount: int) -> None:
        with self._lock:
            self._progress.adjust_total(amount)


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
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self._zip_entry_cache: dict[tuple[str, str], ZipEntry] = {}
        self._zip_entries_by_url: dict[str, list[ZipEntry]] = {}
        self._bundle_archive_locks: dict[str, Lock] = {}
        self._bundle_archive_locks_guard = Lock()
        self._force_exit = force_exit or os._exit
        self._progress_factory = progress_factory or NullProgressReporterFactory()
        self._cancellation = cancellation or NeverCancelled()
        self._wait_policy = build_future_wait_policy(
            self.logger,
            self.POLL_INTERVAL_SECONDS,
            self.INTERRUPT_GRACE_SECONDS,
            "Downloads",
        )
        self._download_loop = ResourceDownloadLoop(
            wait_policy=self._wait_policy,
            download_resource=self._download_resource_for_loop,
            cancellation=self._cancellation,
        )

    def verify_and_download(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        *,
        concurrency: int,
    ) -> None:
        member_archives = AssetCollection(
            resource
            for resource in resources
            if context.region.casefold() == "jp"
            and is_bundle_member_selection(resource)
        )
        regular = AssetCollection(
            resource for resource in resources if resource not in member_archives.assets
        )
        if regular:
            self._verify_and_download_standard(
                regular, context, concurrency=concurrency
            )
        if member_archives:
            self._verify_and_download_bundle_members(
                member_archives,
                context,
                concurrency=concurrency,
            )

    def _verify_and_download_standard(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        *,
        concurrency: int,
    ) -> None:
        self._cancellation.raise_if_cancelled()
        if not resources:
            return

        Path(context.workspace.temp_state).mkdir(parents=True, exist_ok=True)
        Path(context.workspace.raw).mkdir(parents=True, exist_ok=True)
        Path(context.workspace.extracted).mkdir(parents=True, exist_ok=True)

        resources.sorted_by_size()
        pending = self._verify_resources(resources, context, concurrency)
        if not pending:
            self.logger.info("All files have already been downloaded.")
            return

        adaptive_state = self._create_adaptive_download_state(pending, concurrency)
        attempt = 0
        while pending and attempt <= context.max_retries:
            self._cancellation.raise_if_cancelled()
            if attempt:
                self.logger.warn(
                    f"Retrying {len(pending)} failed files. Attempt {attempt}/{context.max_retries}."
                )
            pending = self._download_resources(
                pending,
                context,
                adaptive_state=adaptive_state,
                concurrency=concurrency,
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
        self._cancellation.raise_if_cancelled()

    def _verify_resources(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        concurrency: int,
    ) -> list[AssetRecord]:
        self._canonicalize_resource_paths(resources, context)
        if len(resources) == 1:
            stop_event = Event()
            resource_name = Path(resources[0].path).name
            initial = ProgressState(
                "Assets",
                "verifying",
                overall=ProgressMeasure(0, 1, "files"),
                item=resource_name,
                pending=0,
            )
            with (
                self._install_interrupt_handler(stop_event),
                self._progress_factory.create(initial) as progress,
            ):
                try:
                    resource, verified = self._verify_resource(resources[0], context)
                except OperationCancelledError:
                    progress.update(
                        ProgressState(
                            "Assets",
                            "cancelled",
                            overall=ProgressMeasure(0, 1, "files"),
                            item=resource_name,
                            pending=0,
                        )
                    )
                    raise
                except BaseException:
                    progress.update(
                        ProgressState(
                            "Assets",
                            "failed",
                            overall=ProgressMeasure(0, 1, "files"),
                            item=resource_name,
                            pending=0,
                            failures=1,
                        )
                    )
                    raise
                progress.update(
                    ProgressState(
                        "Assets",
                        "cancelled" if stop_event.is_set() else "complete",
                        overall=ProgressMeasure(1, 1, "files"),
                        item=Path(resource.path).name,
                        pending=0 if verified else 1,
                    )
                )
            if stop_event.is_set():
                raise OperationCancelledError("Download cancelled by user.")
            return [] if verified else [resource]

        pending: list[AssetRecord] = []
        workers = min(max(concurrency, 1), max(len(resources), 1))
        stop_event = Event()
        executor = ThreadPoolExecutor(max_workers=workers)

        try:
            initial = ProgressState(
                "Assets",
                "verifying",
                overall=ProgressMeasure(0, len(resources), "files"),
                item=Path(resources[0].path).name,
                pending=0,
            )
            with (
                self._install_interrupt_handler(stop_event),
                self._progress_factory.create(initial) as progress,
            ):
                completed = 0
                pending_futures = {
                    executor.submit(self._verify_resource, resource, context): resource
                    for resource in resources
                }
                try:
                    completed = self._drain_verification_futures(
                        pending_futures,
                        stop_event,
                        progress,
                        pending,
                    )
                except OperationCancelledError:
                    progress.update(
                        self._verification_terminal_state(
                            "cancelled",
                            completed,
                            len(resources),
                            pending,
                        )
                    )
                    raise
                except BaseException:
                    progress.update(
                        self._verification_terminal_state(
                            "failed",
                            completed,
                            len(resources),
                            pending,
                            failures=1,
                        )
                    )
                    raise
                progress.update(
                    self._verification_terminal_state(
                        "cancelled" if stop_event.is_set() else "complete",
                        completed,
                        len(resources),
                        pending,
                    )
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if stop_event.is_set():
            raise OperationCancelledError("Download cancelled by user.")

        return pending

    def _download_resources(
        self,
        resources: list[AssetRecord],
        context: ExecutionContext,
        *,
        adaptive_state: _AdaptiveDownloadState | None = None,
        concurrency: int,
    ) -> list[AssetRecord]:
        state = adaptive_state or self._create_adaptive_download_state(
            resources, concurrency
        )
        progress_total, download_mode = self._resolve_download_progress(resources)
        stop_event = Event()
        executor = ThreadPoolExecutor(max_workers=state.upper_bound)
        progress_lock = Lock()
        failed_resources: list[AssetRecord] = []

        try:
            initial = ProgressState(
                "Assets",
                "downloading",
                overall=ProgressMeasure(
                    0,
                    progress_total,
                    "bytes" if download_mode else "files",
                ),
                current=ProgressMeasure(0, len(resources), "files"),
                item=Path(resources[0].path).name,
                workers=ProgressWorkers(
                    min(state.target_concurrency, len(resources)),
                    state.upper_bound,
                ),
            )
            with (
                self._install_interrupt_handler(stop_event),
                self._progress_factory.create(initial) as progress,
            ):
                tracker = DownloadProgress(
                    progress,
                    total=progress_total,
                    download_mode=download_mode,
                )
                loop_context = DownloadLoopContext(
                    progress=tracker,
                    context=context,
                    progress_lock=progress_lock,
                    download_mode=download_mode,
                    executor=executor,
                    progress_callback=(
                        self._build_progress_callback(tracker, progress_lock)
                        if download_mode
                        else None
                    ),
                )
                try:
                    failed_resources = self._download_loop.run(
                        resources=resources,
                        loop_context=loop_context,
                        adaptive_state=state,
                        stop_event=stop_event,
                    )
                except OperationCancelledError:
                    tracker.finish("cancelled")
                    raise
                except BaseException:
                    tracker.finish("failed")
                    raise
                tracker.finish(
                    "cancelled"
                    if stop_event.is_set()
                    else "failed"
                    if failed_resources
                    else "complete"
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if stop_event.is_set():
            raise OperationCancelledError("Download cancelled by user.")

        return failed_resources

    @contextmanager
    def _install_interrupt_handler(self, stop_event: Event) -> Iterator[None]:
        interrupt_state = SignalInterruptState()
        dispatcher_stop = Event()

        def dispatch_interrupt() -> None:
            while not dispatcher_stop.wait(self.POLL_INTERVAL_SECONDS):
                if interrupt_state.is_set():
                    stop_event.set()
                    self.http_client.close()
                    return

        dispatcher = Thread(
            target=dispatch_interrupt,
            name="download-interrupt-dispatcher",
            daemon=True,
        )
        dispatcher.start()
        try:
            with install_interrupt_handler(
                interrupt_state,
                self.logger,
                force_exit=self._force_exit,
            ):
                yield
        finally:
            if interrupt_state.is_set() and not stop_event.is_set():
                stop_event.set()
                self.http_client.close()
            dispatcher_stop.set()
            dispatcher.join(timeout=self.POLL_INTERVAL_SECONDS * 2)

    @staticmethod
    def _resolve_download_progress(resources: list[AssetRecord]) -> tuple[int, bool]:
        total_bytes = sum(
            max(int(resource.metadata.get("transfer_size", resource.size)), 0)
            for resource in resources
        )
        download_mode = total_bytes > 0
        progress_total = total_bytes if download_mode else len(resources)
        return progress_total, download_mode

    def _build_progress_callback(
        self,
        progress: DownloadProgress,
        progress_lock: Lock,
    ) -> Callable[[int], None]:
        return _TrackedDownloadProgress(progress, progress_lock)

    def _download_resource_for_loop(
        self,
        resource: AssetRecord,
        context: ExecutionContext,
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
        pending_futures: dict[Future[tuple[AssetRecord, bool]], AssetRecord],
        stop_event: Event,
        progress: ProgressReporterPort,
        pending: list[AssetRecord],
    ) -> int:
        completed = 0
        total = len(pending_futures)
        while pending_futures:
            if self._cancellation.is_cancelled():
                stop_event.set()
            done_futures, _ = wait(
                set(pending_futures),
                timeout=self.POLL_INTERVAL_SECONDS,
                return_when=FIRST_COMPLETED,
            )
            if stop_event.is_set():
                cancel_pending_futures(set(pending_futures) - done_futures)

            completed_entries = [
                (future, pending_futures.pop(future)) for future in done_futures
            ]
            for future, _resource in completed_entries:
                if future.cancelled():
                    continue
                try:
                    resource_item, verified = future.result()
                except BaseException:
                    progress.update(
                        self._verification_terminal_state(
                            "failed",
                            completed,
                            total,
                            pending,
                            failures=1,
                        )
                    )
                    raise
                completed += 1
                if not verified:
                    pending.append(resource_item)
                oldest = next(iter(pending_futures.values()), None)
                progress.update(
                    ProgressState(
                        "Assets",
                        "verifying",
                        overall=ProgressMeasure(completed, total, "files"),
                        item=Path(oldest.path).name if oldest is not None else None,
                        pending=len(pending),
                    )
                )
        return completed

    @staticmethod
    def _verification_terminal_state(
        stage: ProgressStage,
        completed: int,
        total: int,
        pending: list[AssetRecord],
        *,
        failures: int = 0,
    ) -> ProgressState:
        return ProgressState(
            "Assets",
            stage,
            overall=ProgressMeasure(min(completed, total), total, "files"),
            pending=len(pending),
            failures=failures,
        )

    def _create_adaptive_download_state(
        self,
        resources: list[AssetRecord],
        concurrency: int,
    ) -> _AdaptiveDownloadState:
        upper_bound = min(max(concurrency, 1), max(len(resources), 1))
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
        context: ExecutionContext,
    ) -> tuple[AssetRecord, bool]:
        self._cancellation.raise_if_cancelled()
        asset_path = context.workspace.raw_resource_path(
            resource.asset_type.value,
            resource.path,
        )
        result = self._get_validation_error(asset_path, resource) is None
        self._cancellation.raise_if_cancelled()
        return resource, result

    def _get_validation_error(
        self, asset_path: Path, resource: AssetRecord
    ) -> str | None:
        try:
            actual_size = asset_path.stat().st_size
        except FileNotFoundError:
            return "downloaded file is missing"

        if self._is_apk_entry_resource(resource):
            zip_entry = self._resolve_apk_zip_entry(resource)
            if actual_size != zip_entry.uncompressed_size:
                return (
                    "size mismatch "
                    f"(expected {format_file_size(zip_entry.uncompressed_size)}, "
                    f"got {format_file_size(actual_size)})"
                )
            actual_crc = calculate_crc(str(asset_path))
            if actual_crc != zip_entry.crc32:
                return "checksum mismatch for crc"
            return None

        if actual_size != resource.size:
            return (
                f"size mismatch (expected {format_file_size(resource.size)}, "
                f"got {format_file_size(actual_size)})"
            )

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
        context: ExecutionContext,
        progress_callback: Callable[[int], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> AssetRecord:
        self._cancellation.raise_if_cancelled()
        asset_path = context.workspace.raw_resource_path(
            resource.asset_type.value,
            resource.path,
        )
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        if resource.metadata.get("source") == BUNDLE_MEMBER_SOURCE:
            self._download_bundle_member(
                resource,
                context,
                asset_path,
                progress_callback,
                should_stop,
            )
            self._validate_downloaded_resource(asset_path, resource)
            self._cancellation.raise_if_cancelled()
            return resource
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
            self._cancellation.raise_if_cancelled()
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
        self._cancellation.raise_if_cancelled()
        return resource

    def _verify_and_download_bundle_members(
        self,
        archives: AssetCollection,
        context: ExecutionContext,
        *,
        concurrency: int,
    ) -> None:
        entries_by_archive: dict[str, Sequence[ZipEntry]] = {}
        range_enabled: dict[str, bool] = {}
        fallback: list[AssetRecord] = []
        stop_event = Event()
        archive_list = list(archives)
        initial = ProgressState(
            "Assets",
            "scanning",
            overall=ProgressMeasure(0, len(archive_list), "archives"),
        )
        with (
            self._install_interrupt_handler(stop_event),
            self._progress_factory.create(initial) as progress,
        ):
            for index, archive in enumerate(archive_list, start=1):
                self._cancellation.raise_if_cancelled()
                if stop_event.is_set():
                    raise OperationCancelledError("Download cancelled by user.")
                archive_path = context.workspace.raw_resource_path(
                    archive.asset_type.value,
                    archive.path,
                )
                try:
                    if self._get_validation_error(archive_path, archive) is None:
                        entries = read_local_zip_entries(archive_path)
                        range_enabled[archive.path.casefold()] = False
                    else:
                        entries = tuple(
                            self._read_remote_bundle_entries(
                                archive,
                                context,
                                should_stop=stop_event.is_set,
                            )
                        )
                        range_enabled[archive.path.casefold()] = True
                    entries_by_archive[archive.path.casefold()] = entries
                except (
                    NetworkError,
                    OSError,
                    RuntimeError,
                    UnsupportedZipLayoutError,
                    ZipCentralDirectoryError,
                ):
                    fallback.append(archive)
                progress.update(
                    ProgressState(
                        "Assets",
                        "scanning",
                        overall=ProgressMeasure(index, len(archive_list), "archives"),
                        item=Path(archive.path).name,
                    )
                )

        if fallback:
            fallback_resources = AssetCollection(
                replace(resource, selected_member_paths=None) for resource in fallback
            )
            self._verify_and_download_standard(
                fallback_resources,
                context,
                concurrency=concurrency,
            )
            for archive in fallback:
                archive_path = context.workspace.raw_resource_path(
                    archive.asset_type.value,
                    archive.path,
                )
                entries_by_archive[archive.path.casefold()] = read_local_zip_entries(
                    archive_path
                )
                range_enabled[archive.path.casefold()] = False

        try:
            plan = build_member_download_plan(
                archive_list,
                entries_by_archive,
                range_enabled_by_archive=range_enabled,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise DownloadError(
                f"Unable to prepare direct bundle members: {exc}"
            ) from exc

        self._verify_and_download_standard(
            plan.primary,
            context,
            concurrency=concurrency,
        )
        primary_by_path = {resource.path: resource for resource in plan.primary}
        for primary_path, aliases in plan.aliases.items():
            source_resource = primary_by_path[primary_path]
            source = context.workspace.raw_resource_path(
                source_resource.asset_type.value,
                source_resource.path,
            )
            for alias in aliases:
                destination = context.workspace.raw_resource_path(
                    alias.asset_type.value,
                    alias.path,
                )
                if self._get_validation_error(destination, alias) is None:
                    continue
                materialize_member_alias(source, destination)
                self._validate_downloaded_resource(destination, alias)

        invalid = [
            member.path
            for member in plan.all_members
            if self._get_validation_error(
                context.workspace.raw_resource_path(
                    member.asset_type.value,
                    member.path,
                ),
                member,
            )
            is not None
        ]
        if invalid:
            examples = ", ".join(invalid[:3])
            raise DownloadError(
                f"Direct bundle member cache is incomplete: {examples}."
            )

    def _read_remote_bundle_entries(
        self,
        archive: AssetRecord,
        context: ExecutionContext,
        *,
        should_stop: Callable[[], bool],
    ) -> Sequence[ZipEntry]:
        failures = 0
        while True:
            self._cancellation.raise_if_cancelled()
            if should_stop():
                raise OperationCancelledError("Download cancelled by user.")
            try:
                return read_zip_entries(
                    archive.url,
                    self.http_client,
                    timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
                    file_size=archive.size if archive.size > 0 else None,
                )
            except (NetworkError, ZipCentralDirectoryError):
                failures += 1
                if failures > context.max_retries:
                    raise

    def _download_bundle_member(
        self,
        resource: AssetRecord,
        context: ExecutionContext,
        destination: Path,
        progress_callback: Callable[[int], None] | None,
        should_stop: Callable[[], bool] | None,
    ) -> None:
        entry = resource.metadata.get("zip_entry")
        archive = resource.metadata.get("archive_resource")
        if not isinstance(entry, ZipEntry) or not isinstance(archive, AssetRecord):
            raise RuntimeError("Bundle member download metadata is invalid.")

        transferred = 0

        def track(amount: int) -> None:
            nonlocal transferred
            transferred += amount
            if progress_callback is not None:
                progress_callback(amount)

        if resource.metadata.get("range_enabled") is True:
            if should_stop is not None and should_stop():
                raise OperationCancelledError("Download cancelled by user.")
            try:
                extract_zip_entry(
                    resource.url,
                    entry,
                    destination,
                    self.http_client,
                    timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
                    progress_callback=track,
                )
                return
            except UnsupportedZipLayoutError:
                pass
            except ZipCentralDirectoryError:
                failures = int(resource.metadata.get("range_validation_failures", 0))
                failures += 1
                resource.metadata["range_validation_failures"] = failures
                if failures <= context.max_retries:
                    raise

        transfer_size = int(resource.metadata.get("transfer_size", resource.size))
        lock = self._bundle_archive_lock(archive.path)
        with lock:
            archive_path = context.workspace.raw_resource_path(
                archive.asset_type.value,
                archive.path,
            )
            needs_download = (
                self._get_validation_error(archive_path, archive) is not None
            )
            adjust_total = getattr(progress_callback, "adjust_total", None)
            if callable(adjust_total):
                replacement = transferred - transfer_size
                if needs_download:
                    replacement += archive.size
                adjust_total(replacement)
            if needs_download:
                result = self.http_client.download_to_file(
                    archive.url,
                    str(archive_path),
                    timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
                    progress_callback=progress_callback,
                    should_stop=should_stop,
                )
                if result.status_code >= 400:
                    archive_path.unlink(missing_ok=True)
                    raise RuntimeError(f"unexpected HTTP status {result.status_code}")
                self._validate_downloaded_resource(archive_path, archive)
            extract_local_bundle_member(archive_path, entry, destination)

    def _bundle_archive_lock(self, archive_path: str) -> Lock:
        key = archive_path.replace("\\", "/").casefold()
        with self._bundle_archive_locks_guard:
            return self._bundle_archive_locks.setdefault(key, Lock())

    def _canonicalize_resource_paths(
        self,
        resources: Iterable[AssetRecord],
        context: ExecutionContext,
    ) -> None:
        expected_by_parent: dict[Path, set[str]] = defaultdict(set)
        for resource in resources:
            self._cancellation.raise_if_cancelled()
            asset_path = context.workspace.raw_resource_path(
                resource.asset_type.value,
                resource.path,
            )
            expected_by_parent[asset_path.parent].add(asset_path.name)

        for parent, expected_names in expected_by_parent.items():
            self._cancellation.raise_if_cancelled()
            if not parent.is_dir():
                continue
            try:
                entries = tuple(parent.iterdir())
            except OSError:
                continue
            for source, target in self._plan_case_renames(
                parent,
                entries,
                expected_names,
            ):
                self._cancellation.raise_if_cancelled()
                cls = type(self)
                temp_path = cls._case_rename_temp_path(target)
                if temp_path is None:
                    continue
                try:
                    source.rename(temp_path)
                    temp_path.rename(target)
                except OSError:
                    with suppress(OSError):
                        if temp_path.exists():
                            temp_path.rename(source)

    @staticmethod
    def _plan_case_renames(
        parent: Path,
        entries: Sequence[Path],
        expected_names: set[str],
    ) -> tuple[tuple[Path, Path], ...]:
        exact_names = {entry.name for entry in entries}
        entries_by_folded_name: dict[str, list[Path]] = defaultdict(list)
        for entry in entries:
            entries_by_folded_name[entry.name.casefold()].append(entry)
        expected_fold_counts = Counter(name.casefold() for name in expected_names)

        renames: list[tuple[Path, Path]] = []
        for expected_name in sorted(
            expected_names, key=lambda value: (value.casefold(), value)
        ):
            if expected_name in exact_names:
                continue
            folded_name = expected_name.casefold()
            matches = entries_by_folded_name.get(folded_name, ())
            if expected_fold_counts[folded_name] != 1 or len(matches) != 1:
                continue
            renames.append((matches[0], parent / expected_name))
        return tuple(renames)

    @staticmethod
    def _case_rename_temp_path(asset_path: Path) -> Path | None:
        parent = asset_path.parent
        for index in range(100):
            temp_path = parent / (
                f".{asset_path.name}.casefix-{os.getpid()}-{index}.tmp"
            )
            if not temp_path.exists():
                return temp_path
        return None

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
