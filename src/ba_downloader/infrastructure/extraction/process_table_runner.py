from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from multiprocessing import Queue, freeze_support
from pathlib import Path
from queue import Empty
from threading import Event
from typing import Any

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.extractor import TableExtractor
from ba_downloader.infrastructure.extraction.threaded_runner import (
    ExtractionFailure,
    ExtractionFailureError,
)
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter
from ba_downloader.infrastructure.runtime.interrupts import (
    CancellationFeedbackState,
    emit_cancellation_feedback,
    install_interrupt_handler,
)


@dataclass(frozen=True, slots=True)
class TableExtractionEvent:
    level: str
    file_path: str
    message: str = ""


@dataclass(slots=True)
class TableExtractionRunState:
    failures: list[ExtractionFailure]
    completed_files: set[str]


class QueueTableLogger(LoggerPort):
    def __init__(
        self,
        events: multiprocessing.queues.Queue[TableExtractionEvent],
        file_path: str,
    ) -> None:
        self.events = events
        self.file_path = file_path

    def info(self, message: str) -> None:
        self.events.put(TableExtractionEvent("info", self.file_path, message))

    def warn(self, message: str) -> None:
        self.events.put(TableExtractionEvent("warn", self.file_path, message))

    def error(self, message: str) -> None:
        self.events.put(TableExtractionEvent("error", self.file_path, message))


def table_extraction_process_worker(
    queue: multiprocessing.queues.Queue[Any],
    context: RuntimeContext,
    events: multiprocessing.queues.Queue[TableExtractionEvent],
) -> None:
    while True:
        try:
            queue_item = queue.get_nowait()
        except Empty:
            return
        if isinstance(queue_item, tuple):
            table_file, metadata = queue_item
        else:
            table_file, metadata = queue_item, {}

        logger = QueueTableLogger(events, table_file)
        try:
            events.put(TableExtractionEvent("started", table_file))

            def report_progress(status: str, file_path: str = table_file) -> None:
                events.put(TableExtractionEvent("progress", file_path, status))

            extractor = TableExtractor.from_context(context, logger)
            extractor.extract_table(
                table_file,
                progress_callback=report_progress,
                metadata=metadata,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            events.put(TableExtractionEvent("failed", table_file, str(exc)))
            continue
        events.put(TableExtractionEvent("done", table_file))


class ProcessTableExtractionRunner:
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

    def run(
        self,
        files: list[str],
        context: RuntimeContext,
        *,
        metadata_by_file: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        if not files:
            return

        freeze_support()
        queue: multiprocessing.queues.Queue[Any] = Queue()
        events: multiprocessing.queues.Queue[TableExtractionEvent] = Queue()
        for file_path in files:
            queue.put((file_path, dict((metadata_by_file or {}).get(file_path, {}))))

        stop_event = Event()
        processes = self._build_processes(queue, context, len(files), events)
        run_state = TableExtractionRunState(failures=[], completed_files=set())

        try:
            with (
                install_interrupt_handler(
                    stop_event,
                    self.logger,
                    force_exit=self.force_exit,
                    on_interrupt=lambda: self._stop_processes(processes),
                ),
                RichProgressReporter(
                    len(files),
                    "Extracting table files...",
                    extract_mode=True,
                ) as progress,
            ):
                self._start_processes(processes)
                self._monitor(
                    events=events,
                    files=files,
                    processes=processes,
                    progress=progress,
                    stop_event=stop_event,
                    run_state=run_state,
                )
        finally:
            if stop_event.is_set():
                self._stop_processes(processes)
            for process in processes:
                process.join(timeout=self.poll_interval_seconds)
            self._drain_events(events, None, run_state)
            if not stop_event.is_set():
                self._record_abandoned_files(files, run_state)
            self._finalize_queue(queue, cancelled=stop_event.is_set())
            self._finalize_queue(events, cancelled=stop_event.is_set())
            if stop_event.is_set():
                raise KeyboardInterrupt()
            if run_state.failures:
                raise ExtractionFailureError("table extraction", run_state.failures)

    def _build_processes(
        self,
        queue: multiprocessing.queues.Queue[Any],
        context: RuntimeContext,
        file_count: int,
        events: multiprocessing.queues.Queue[TableExtractionEvent],
    ) -> list[multiprocessing.Process]:
        process_count = min(max(context.threads, 1), file_count, os.cpu_count() or 1)
        return [
            multiprocessing.Process(
                target=table_extraction_process_worker,
                args=(queue, context, events),
            )
            for _ in range(process_count)
        ]

    @staticmethod
    def _start_processes(processes: list[multiprocessing.Process]) -> None:
        for process in processes:
            process.start()

    def _monitor(
        self,
        *,
        events: multiprocessing.queues.Queue[TableExtractionEvent],
        files: list[str],
        processes: list[multiprocessing.Process],
        progress: RichProgressReporter,
        stop_event: Event,
        run_state: TableExtractionRunState,
    ) -> None:
        cancellation_state = CancellationFeedbackState()
        progress.set_status(f"0/{len(files)} files")

        while len(run_state.completed_files) < len(files) and self._has_live_processes(
            processes
        ):
            self._drain_events(events, progress, run_state)
            progress.set_status(f"{len(run_state.completed_files)}/{len(files)} files")
            if stop_event.is_set():
                self._stop_processes(processes)
                emit_cancellation_feedback(
                    self.logger,
                    cancellation_state,
                    grace_seconds=self.interrupt_grace_seconds,
                    cancellation_message="Cancelling table extraction...",
                    still_stopping_message=(
                        "Extraction is still stopping. Press Ctrl+C again to force exit."
                    ),
                    has_pending_work=self._has_live_processes(processes),
                )
                if not self._has_live_processes(processes):
                    break
            stop_event.wait(self.poll_interval_seconds)

        self._drain_events(events, progress, run_state)
        progress.set_status(f"{len(run_state.completed_files)}/{len(files)} files")

    def _drain_events(
        self,
        events: multiprocessing.queues.Queue[TableExtractionEvent],
        progress: RichProgressReporter | None,
        run_state: TableExtractionRunState,
    ) -> None:
        while True:
            try:
                event = events.get_nowait()
            except Empty:
                return

            if event.level == "info":
                self.logger.info(event.message)
            elif event.level == "warn":
                self.logger.warn(event.message)
            elif event.level == "error":
                self.logger.error(event.message)
            elif event.level in {"started", "progress"} and progress is not None:
                progress.set_description(f"Extracting {Path(event.file_path).name}")
                if event.message:
                    progress.set_secondary_status(event.message)
            elif event.level in {"done", "failed"}:
                if event.file_path not in run_state.completed_files:
                    run_state.completed_files.add(event.file_path)
                    if progress is not None:
                        progress.advance()
                if event.level == "failed":
                    run_state.failures.append(
                        ExtractionFailure(event.file_path, RuntimeError(event.message))
                    )
                    self.logger.error(
                        f"Failed to extract {event.file_path}: {event.message}"
                    )

    def _record_abandoned_files(
        self,
        files: list[str],
        run_state: TableExtractionRunState,
    ) -> None:
        for file_path in files:
            if file_path in run_state.completed_files:
                continue
            run_state.completed_files.add(file_path)
            error = RuntimeError("table extraction worker exited before completion")
            run_state.failures.append(ExtractionFailure(file_path, error))
            self.logger.error(f"Failed to extract {file_path}: {error}")

    @classmethod
    def _has_live_processes(cls, processes: list[multiprocessing.Process]) -> bool:
        return any(process.is_alive() for process in processes)

    @staticmethod
    def _stop_processes(processes: list[multiprocessing.Process]) -> None:
        for process in processes:
            if process.is_alive():
                process.kill()

    @staticmethod
    def _finalize_queue(
        queue: multiprocessing.queues.Queue[Any],
        *,
        cancelled: bool,
    ) -> None:
        cancel_join_thread = getattr(queue, "cancel_join_thread", None)
        close = getattr(queue, "close", None)
        join_thread = getattr(queue, "join_thread", None)

        if cancelled and callable(cancel_join_thread):
            cancel_join_thread()
        if callable(close):
            close()
        if not cancelled and callable(join_thread):
            try:
                join_thread()
            except (AssertionError, OSError, RuntimeError, ValueError):
                return
