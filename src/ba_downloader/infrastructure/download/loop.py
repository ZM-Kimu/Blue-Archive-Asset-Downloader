from __future__ import annotations

from collections import deque
from collections.abc import Callable
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Any, Protocol

from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.domain.models.asset import AssetRecord
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.download.adaptive import (
    AdaptiveDownloadState,
    classify_download_failure,
    decrease_target_concurrency,
    record_download_success,
)
from ba_downloader.infrastructure.runtime.interrupts import (
    CancellationFeedbackState,
    wait_for_operation_futures,
)


class DownloadProgress(Protocol):
    def advance(self, amount: int = 1) -> None: ...

    def set_description(self, description: str) -> None: ...

    def set_status(self, status: str) -> None: ...

    def set_secondary_status(self, status: str) -> None: ...

    def set_failed_status(self, status: str) -> None: ...


DownloadFunction = Callable[
    [AssetRecord, RuntimeContext, Callable[[int], None] | None, Callable[[], bool]],
    AssetRecord,
]
SuccessfulDownloadHandler = Callable[[AssetRecord, RuntimeContext], None]


@dataclass(slots=True)
class DownloadSessionState:
    total_files: int
    completed_files: int = 0
    failed_files: int = 0
    failed_resources: list[AssetRecord] | None = None

    def __post_init__(self) -> None:
        if self.failed_resources is None:
            self.failed_resources = []


@dataclass(slots=True)
class DownloadLoopContext:
    progress: DownloadProgress
    context: RuntimeContext
    progress_lock: Lock
    download_mode: bool
    executor: ThreadPoolExecutor
    progress_callback: Callable[[int], None] | None


class ResourceDownloadLoop:
    def __init__(
        self,
        *,
        wait_policy: Any,
        download_resource: DownloadFunction,
        handle_successful_download: SuccessfulDownloadHandler,
    ) -> None:
        self._wait_policy = wait_policy
        self._download_resource = download_resource
        self._handle_successful_download = handle_successful_download

    def run(
        self,
        *,
        resources: list[AssetRecord],
        loop_context: DownloadLoopContext,
        adaptive_state: AdaptiveDownloadState,
        stop_event: Event,
    ) -> list[AssetRecord]:
        future_map: dict[Future[AssetRecord], AssetRecord] = {}
        pending_resources = deque(resources)
        session_state = DownloadSessionState(total_files=len(resources))

        self._update_progress_status(
            loop_context.progress,
            session_state,
            adaptive_state,
        )
        cancellation_state = CancellationFeedbackState()

        while pending_resources or future_map:
            if stop_event.is_set() and not future_map:
                break

            self._fill_futures(
                future_map,
                pending_resources,
                loop_context,
                stop_event,
                adaptive_state,
            )
            if not future_map:
                continue

            done_futures, _pending_futures = wait_for_operation_futures(
                set(future_map),
                stop_event,
                self._wait_policy,
                cancellation_state,
                "active downloads",
            )

            successful_downloads, decrease_reason = self._collect_results(
                done_futures,
                future_map,
                session_state,
                stop_event,
            )
            self._update_adaptive_concurrency(
                adaptive_state,
                successful_downloads,
                decrease_reason,
            )
            self._finalize_successful_downloads(
                successful_downloads,
                loop_context,
                session_state,
            )
            with loop_context.progress_lock:
                self._update_progress_status(
                    loop_context.progress,
                    session_state,
                    adaptive_state,
                )

        return list(session_state.failed_resources or [])

    def _fill_futures(
        self,
        future_map: dict[Future[AssetRecord], AssetRecord],
        pending_resources: deque[AssetRecord],
        loop_context: DownloadLoopContext,
        stop_event: Event,
        state: AdaptiveDownloadState,
    ) -> None:
        while (
            not stop_event.is_set()
            and len(future_map) < state.target_concurrency
            and pending_resources
        ):
            resource = pending_resources.popleft()
            future = loop_context.executor.submit(
                self._download_resource,
                resource,
                loop_context.context,
                loop_context.progress_callback,
                stop_event.is_set,
            )
            future_map[future] = resource
            loop_context.progress.set_description(Path(resource.path).name)

    def _collect_results(
        self,
        done_futures: set[Future[AssetRecord]],
        future_map: dict[Future[AssetRecord], AssetRecord],
        session_state: DownloadSessionState,
        stop_event: Event,
    ) -> tuple[list[AssetRecord], str | None]:
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
            except (NetworkError, RuntimeError, OSError) as exc:
                if stop_event.is_set() and self._is_cancelled_error(exc):
                    continue
                session_state.failed_files += 1
                if session_state.failed_resources is not None:
                    session_state.failed_resources.append(resource_item)
                failure_kind = classify_download_failure(exc)
                if failure_kind != "other" and decrease_reason is None:
                    decrease_reason = failure_kind
                continue

            successful_downloads.append(downloaded_item)

        return successful_downloads, decrease_reason

    @staticmethod
    def _update_adaptive_concurrency(
        state: AdaptiveDownloadState,
        successful_downloads: list[AssetRecord],
        decrease_reason: str | None,
    ) -> None:
        if decrease_reason is not None:
            decrease_target_concurrency(state)
            return

        for _resource in successful_downloads:
            record_download_success(state)

    def _finalize_successful_downloads(
        self,
        successful_downloads: list[AssetRecord],
        loop_context: DownloadLoopContext,
        session_state: DownloadSessionState,
    ) -> None:
        for downloaded_item in successful_downloads:
            session_state.completed_files += 1
            if not loop_context.download_mode:
                with loop_context.progress_lock:
                    loop_context.progress.advance()
            self._handle_successful_download(downloaded_item, loop_context.context)

    @staticmethod
    def _update_progress_status(
        progress: DownloadProgress,
        session_state: DownloadSessionState,
        state: AdaptiveDownloadState,
    ) -> None:
        progress.set_status(
            _build_download_file_status(
                session_state.completed_files,
                session_state.total_files,
            )
        )
        progress.set_secondary_status(
            _build_download_concurrency_status(session_state.total_files, state)
        )
        progress.set_failed_status(
            _build_download_failed_status(session_state.failed_files)
        )

    @staticmethod
    def _is_cancelled_error(exc: Exception) -> bool:
        return "download cancelled by user" in str(exc).lower()


def _build_download_file_status(
    completed_files: int,
    total_files: int,
) -> str:
    return f"{completed_files}/{total_files} files"


def _build_download_concurrency_status(
    total_files: int,
    state: AdaptiveDownloadState,
) -> str:
    current_concurrency = min(state.target_concurrency, max(total_files, 1))
    return f"conc. {current_concurrency}/{state.upper_bound}"


def _build_download_failed_status(failed_files: int) -> str:
    return f"failed {failed_files}"
