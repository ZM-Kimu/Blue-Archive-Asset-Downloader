from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from zipfile import BadZipFile

from ba_downloader.domain.exceptions import ExtractError
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter
from ba_downloader.infrastructure.runtime.interrupts import (
    CancellationFeedbackState,
    build_future_wait_policy,
    install_interrupt_handler,
    wait_for_operation_futures,
)

ExtractionTask = Callable[
    [str, Callable[[], bool], Callable[[str], None]],
    None,
]


@dataclass(frozen=True, slots=True)
class ExtractionFailure:
    file_path: str
    error: Exception


class ExtractionFailureError(ExtractError):
    def __init__(self, operation_name: str, failures: list[ExtractionFailure]) -> None:
        self.operation_name = operation_name
        self.failures = failures
        file_word = "file" if len(failures) == 1 else "files"
        examples = ", ".join(Path(failure.file_path).name for failure in failures[:5])
        suffix = f": {examples}" if examples else ""
        super().__init__(
            f"{operation_name} failed for {len(failures)} {file_word}{suffix}"
        )

    @classmethod
    def from_count(
        cls,
        operation_name: str,
        failure_count: int,
    ) -> ExtractionFailureError:
        failures = [
            ExtractionFailure(file_path=f"<unknown #{index}>", error=RuntimeError(""))
            for index in range(1, failure_count + 1)
        ]
        return cls(operation_name, failures)


class ThreadedExtractionRunner:
    def __init__(
        self,
        logger: LoggerPort,
        *,
        poll_interval_seconds: float,
        interrupt_grace_seconds: float,
        force_exit: Callable[[int], None] | None = None,
    ) -> None:
        self.logger = logger
        self.poll_interval_seconds = poll_interval_seconds
        self.interrupt_grace_seconds = interrupt_grace_seconds
        self.force_exit = force_exit or os._exit
        self.wait_policy = build_future_wait_policy(
            self.logger,
            self.poll_interval_seconds,
            self.interrupt_grace_seconds,
            "Extraction",
        )

    def run(
        self,
        files: list[str],
        context: RuntimeContext,
        *,
        progress_title: str,
        operation_name: str,
        task: ExtractionTask,
    ) -> None:
        if not files:
            return

        stop_event = Event()
        future_map: dict[Future[None], str] = {}
        executor = ThreadPoolExecutor(
            max_workers=min(max(context.threads, 1), len(files))
        )

        try:
            with (
                install_interrupt_handler(
                    stop_event,
                    self.logger,
                    force_exit=self.force_exit,
                ),
                RichProgressReporter(
                    len(files),
                    progress_title,
                    extract_mode=True,
                ) as progress,
            ):
                future_map = {
                    executor.submit(
                        task,
                        file_path,
                        stop_event.is_set,
                        self._build_sub_progress_callback(progress, file_path),
                    ): file_path
                    for file_path in files
                }
                failures = self._drain_futures(
                    set(future_map),
                    future_map,
                    stop_event,
                    progress,
                    operation_name,
                )
                if failures:
                    raise ExtractionFailureError(operation_name, failures)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            if stop_event.is_set():
                raise KeyboardInterrupt()

    def _drain_futures(
        self,
        pending_futures: set[Future[None]],
        future_map: dict[Future[None], str],
        stop_event: Event,
        progress: RichProgressReporter,
        operation_name: str,
    ) -> list[ExtractionFailure]:
        cancellation_state = CancellationFeedbackState()
        completed_files = 0
        total_files = len(future_map)
        failures: list[ExtractionFailure] = []
        progress.set_status(f"0/{total_files} files")

        while pending_futures:
            done_futures, pending_futures = wait_for_operation_futures(
                pending_futures,
                stop_event,
                self.wait_policy,
                cancellation_state,
                operation_name,
            )

            for future in done_futures:
                if future.cancelled():
                    continue
                file_path = future_map[future]
                progress.set_description(f"Extracting {Path(file_path).name}")
                try:
                    future.result()
                except RuntimeError as exc:
                    if stop_event.is_set() and self._is_cancelled_error(exc):
                        continue
                    self._record_failure(failures, file_path, exc)
                except (
                    BadZipFile,
                    LookupError,
                    OSError,
                    sqlite3.Error,
                    TypeError,
                    ValueError,
                ) as exc:
                    self._record_failure(failures, file_path, exc)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    self._record_failure(failures, file_path, exc)
                progress.advance()
                completed_files += 1
                progress.set_status(f"{completed_files}/{total_files} files")
        return failures

    def _record_failure(
        self,
        failures: list[ExtractionFailure],
        file_path: str,
        exc: Exception,
    ) -> None:
        failures.append(ExtractionFailure(file_path, exc))
        self.logger.error(f"Failed to extract {file_path}: {exc}")

    @staticmethod
    def _build_sub_progress_callback(
        progress: RichProgressReporter,
        file_path: str,
    ) -> Callable[[str], None]:
        def update_progress(status: str) -> None:
            progress.set_description(f"Extracting {Path(file_path).name}")
            progress.set_secondary_status(status)

        return update_progress

    @staticmethod
    def _is_cancelled_error(exc: Exception) -> bool:
        return "extraction cancelled by user" in str(exc).lower()
