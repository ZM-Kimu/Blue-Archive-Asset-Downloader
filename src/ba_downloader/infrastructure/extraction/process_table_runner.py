from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from multiprocessing import freeze_support
from pathlib import Path
from queue import Empty
from time import monotonic
from typing import Any

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import (
    ProgressReporterFactoryPort,
    ProgressReporterPort,
)
from ba_downloader.infrastructure.extraction.table.extractor import TableExtractor
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
    build_default_table_profile_for_context,
)
from ba_downloader.infrastructure.extraction.threaded_runner import (
    ExtractionFailure,
    ExtractionFailureError,
)
from ba_downloader.infrastructure.progress import NullProgressReporterFactory
from ba_downloader.infrastructure.runtime.interrupts import (
    CancellationFeedbackState,
    emit_cancellation_feedback,
    install_interrupt_handler,
)
from ba_downloader.infrastructure.runtime.process_supervisor import (
    ProcessSupervisor,
    WorkerCommand,
)

TableProfileFactory = Callable[
    [ExecutionContext, DatabaseSourceIdentity | None], TableExtractionProfile
]


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
    context: ExecutionContext,
    events: multiprocessing.queues.Queue[TableExtractionEvent],
    table_profile_factory: TableProfileFactory = build_default_table_profile_for_context,
    stop_event: Any | None = None,
) -> None:
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        queue_item = queue.get()
        if queue_item is None:
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

            extractor = TableExtractor.from_context(
                context,
                logger,
                table_profile=table_profile_factory(context, None),
            )
            extractor.extract_table(
                table_file,
                should_stop=(stop_event.is_set if stop_event is not None else None),
                progress_callback=report_progress,
                metadata=metadata,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            if stop_event is not None and stop_event.is_set():
                return
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
        table_profile_factory: TableProfileFactory = build_default_table_profile_for_context,
        force_exit: Callable[[int], None] | None = None,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.logger = logger
        self.poll_interval_seconds = poll_interval_seconds
        self.interrupt_grace_seconds = interrupt_grace_seconds
        self.table_profile_factory = table_profile_factory
        self.force_exit = force_exit or os._exit
        self.progress_factory = progress_factory or NullProgressReporterFactory()
        self.cancellation = cancellation or NeverCancelled()

    def run(
        self,
        files: list[str],
        context: ExecutionContext,
        *,
        concurrency: int,
        metadata_by_file: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        self.cancellation.raise_if_cancelled()
        if not files:
            return

        freeze_support()
        process_context = multiprocessing.get_context("spawn")
        queue: multiprocessing.queues.Queue[Any] = process_context.Queue()
        events: multiprocessing.queues.Queue[TableExtractionEvent] = (
            process_context.Queue()
        )
        process_count = self._process_count(concurrency, len(files))
        for file_path in files:
            queue.put((file_path, dict((metadata_by_file or {}).get(file_path, {}))))
        for _ in range(process_count):
            queue.put(None)

        stop_event = process_context.Event()
        supervisor = self._build_supervisor(
            queue,
            context,
            events,
            stop_event,
            process_context,
            process_count,
        )
        run_state = TableExtractionRunState(failures=[], completed_files=set())

        try:
            with (
                install_interrupt_handler(
                    stop_event,
                    self.logger,
                    force_exit=self.force_exit,
                    on_interrupt=lambda: supervisor.stop(0.0),
                ),
                self.progress_factory.create(
                    len(files),
                    "Extracting table files...",
                    extract_mode=True,
                ) as progress,
            ):
                supervisor.start()
                self._monitor(
                    events=events,
                    files=files,
                    supervisor=supervisor,
                    progress=progress,
                    stop_event=stop_event,
                    run_state=run_state,
                )
        finally:
            if stop_event.is_set():
                supervisor.stop(self.interrupt_grace_seconds)
            terminal_results = supervisor.close(self.interrupt_grace_seconds)
            self._drain_terminal_events(events, files, run_state)
            if not stop_event.is_set():
                self._record_abandoned_files(files, run_state)
                for result in terminal_results:
                    if result.status == "failed":
                        self.logger.error(
                            f"{result.name} failed: {result.error or 'unknown error'}"
                        )
            self._finalize_queue(queue, cancelled=stop_event.is_set())
            self._finalize_queue(events, cancelled=stop_event.is_set())
            if stop_event.is_set():
                raise OperationCancelledError("Table extraction cancelled by user.")
            if run_state.failures:
                raise ExtractionFailureError("table extraction", run_state.failures)

    def _build_supervisor(
        self,
        queue: multiprocessing.queues.Queue[Any],
        context: ExecutionContext,
        events: multiprocessing.queues.Queue[TableExtractionEvent],
        stop_event: Any,
        process_context: Any,
        process_count: int,
    ) -> ProcessSupervisor:
        return ProcessSupervisor(
            [
                WorkerCommand(
                    name=f"table-extractor-{index + 1}",
                    target=table_extraction_process_worker,
                    arguments=(
                        queue,
                        context,
                        events,
                        self.table_profile_factory,
                        stop_event,
                    ),
                )
                for index in range(process_count)
            ],
            context=process_context,
        )

    @staticmethod
    def _process_count(concurrency: int, file_count: int) -> int:
        return min(max(concurrency, 1), file_count, os.cpu_count() or 1)

    def _monitor(
        self,
        *,
        events: multiprocessing.queues.Queue[TableExtractionEvent],
        files: list[str],
        supervisor: ProcessSupervisor,
        progress: ProgressReporterPort,
        stop_event: Any,
        run_state: TableExtractionRunState,
    ) -> None:
        cancellation_state = CancellationFeedbackState()
        cancellation_started: float | None = None
        progress.set_status(f"0/{len(files)} files")

        while supervisor.is_alive:
            self._drain_events(events, progress, run_state)
            progress.set_status(f"{len(run_state.completed_files)}/{len(files)} files")
            if self.cancellation.is_cancelled():
                stop_event.set()
            if stop_event.is_set():
                cancellation_started = cancellation_started or monotonic()
                if monotonic() - cancellation_started >= self.interrupt_grace_seconds:
                    supervisor.stop(0.0)
                emit_cancellation_feedback(
                    self.logger,
                    cancellation_state,
                    grace_seconds=self.interrupt_grace_seconds,
                    cancellation_message="Cancelling table extraction...",
                    still_stopping_message=(
                        "Extraction is still stopping. Press Ctrl+C again to force exit."
                    ),
                    has_pending_work=supervisor.is_alive,
                )
                if not supervisor.is_alive:
                    break
            stop_event.wait(self.poll_interval_seconds)

        self._drain_events(events, progress, run_state)
        progress.set_status(f"{len(run_state.completed_files)}/{len(files)} files")

    def _drain_events(
        self,
        events: multiprocessing.queues.Queue[TableExtractionEvent],
        progress: ProgressReporterPort | None,
        run_state: TableExtractionRunState,
    ) -> None:
        while True:
            try:
                event = events.get_nowait()
            except Empty:
                return
            self._handle_event(event, progress, run_state)

    def _drain_terminal_events(
        self,
        events: multiprocessing.queues.Queue[TableExtractionEvent],
        files: list[str],
        run_state: TableExtractionRunState,
    ) -> None:
        deadline = monotonic() + self.interrupt_grace_seconds
        while len(run_state.completed_files) < len(files):
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            try:
                event = events.get(timeout=min(self.poll_interval_seconds, remaining))
            except Empty:
                continue
            self._handle_event(event, None, run_state)
        self._drain_events(events, None, run_state)

    def _handle_event(
        self,
        event: TableExtractionEvent,
        progress: ProgressReporterPort | None,
        run_state: TableExtractionRunState,
    ) -> None:
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
