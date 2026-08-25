from __future__ import annotations

from collections import deque
from collections.abc import Callable
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Any

from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.domain.models.asset import AssetRecord
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.progress import (
    ProgressMeasure,
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
from ba_downloader.infrastructure.runtime.interrupts import (
    CancellationFeedbackState,
    wait_for_operation_futures,
)


class DownloadProgress:
    def __init__(
        self,
        reporter: ProgressReporterPort,
        *,
        total: int,
        download_mode: bool,
    ) -> None:
        self._reporter = reporter
        self._total = total
        self._download_mode = download_mode
        self._completed = 0
        self._item: str | None = None
        self._session: DownloadSessionState | None = None
        self._adaptive: AdaptiveDownloadState | None = None
        self._active_workers = 0

    def advance(self, amount: int = 1) -> None:
        self._completed = min(self._completed + amount, self._total)
        if self._session is not None and self._adaptive is not None:
            self.emit(self._session, self._adaptive)

    def set_item(self, item: str) -> None:
        self._item = item

    def set_active_workers(self, active: int) -> None:
        self._active_workers = max(active, 0)

    def emit(
        self,
        session: DownloadSessionState,
        state: AdaptiveDownloadState,
    ) -> None:
        self._session = session
        self._adaptive = state
        completed = self._completed if self._download_mode else session.completed_files
        unit = "bytes" if self._download_mode else "files"
        active = min(self._active_workers, state.upper_bound)
        self._reporter.update(
            ProgressState(
                "Assets",
                "downloading",
                overall=ProgressMeasure(completed, self._total, unit),
                current=ProgressMeasure(
                    session.completed_files, session.total_files, "files"
                ),
                item=self._item,
                workers=ProgressWorkers(active, state.upper_bound),
                failures=session.failed_files,
            )
        )

    def finish(self, stage: ProgressStage) -> None:
        if self._session is None or self._adaptive is None:
            return
        session = self._session
        state = self._adaptive
        completed = self._completed if self._download_mode else session.completed_files
        unit = "bytes" if self._download_mode else "files"
        active = (
            0
            if stage != "downloading"
            else min(
                state.target_concurrency,
                max(session.total_files - session.completed_files, 0),
            )
        )
        self._reporter.update(
            ProgressState(
                "Assets",
                stage,
                overall=ProgressMeasure(completed, self._total, unit),
                current=ProgressMeasure(
                    session.completed_files,
                    session.total_files,
                    "files",
                ),
                item=self._item,
                workers=ProgressWorkers(active, state.upper_bound),
                failures=session.failed_files,
            )
        )


DownloadFunction = Callable[
    [AssetRecord, ExecutionContext, Callable[[int], None] | None, Callable[[], bool]],
    AssetRecord,
]


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
    context: ExecutionContext
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
        cancellation: CancellationPort | None = None,
    ) -> None:
        self._wait_policy = wait_policy
        self._download_resource = download_resource
        self._cancellation = cancellation or NeverCancelled()

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
            active_workers=0,
        )
        cancellation_state = CancellationFeedbackState()

        while pending_resources or future_map:
            if self._cancellation.is_cancelled():
                stop_event.set()
            if stop_event.is_set() and not future_map:
                break

            self._fill_futures(
                future_map,
                pending_resources,
                loop_context,
                stop_event,
                adaptive_state,
            )
            self._set_oldest_item(loop_context.progress, future_map)
            with loop_context.progress_lock:
                self._update_progress_status(
                    loop_context.progress,
                    session_state,
                    adaptive_state,
                    active_workers=len(future_map),
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
                self._set_oldest_item(loop_context.progress, future_map)
                self._update_progress_status(
                    loop_context.progress,
                    session_state,
                    adaptive_state,
                    active_workers=len(future_map),
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
            loop_context.progress.set_active_workers(len(future_map) + 1)
            future = loop_context.executor.submit(
                self._download_resource,
                resource,
                loop_context.context,
                loop_context.progress_callback,
                stop_event.is_set,
            )
            future_map[future] = resource

    @staticmethod
    def _set_oldest_item(
        progress: DownloadProgress,
        future_map: dict[Future[AssetRecord], AssetRecord],
    ) -> None:
        oldest = next(iter(future_map.values()), None)
        if oldest is not None:
            progress.set_item(Path(oldest.path).name)

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
        for _downloaded_item in successful_downloads:
            session_state.completed_files += 1
            if not loop_context.download_mode:
                with loop_context.progress_lock:
                    loop_context.progress.advance()

    @staticmethod
    def _update_progress_status(
        progress: DownloadProgress,
        session_state: DownloadSessionState,
        state: AdaptiveDownloadState,
        *,
        active_workers: int,
    ) -> None:
        progress.set_active_workers(active_workers)
        progress.emit(session_state, state)

    @staticmethod
    def _is_cancelled_error(exc: Exception) -> bool:
        return "download cancelled by user" in str(exc).lower()
