from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from multiprocessing import Queue, freeze_support
from pathlib import Path
from queue import Empty
from threading import Event
from typing import Any

from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import AssetExtractionPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.bundle.exporter import (
    BundleExtractor,
    BundleLogEvent,
)
from ba_downloader.infrastructure.extraction.media.exporter import MediaExtractor
from ba_downloader.infrastructure.extraction.process_table_runner import (
    ProcessTableExtractionRunner,
    TableProfileFactory,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    build_default_table_profile_for_context,
)
from ba_downloader.infrastructure.extraction.threaded_runner import (
    ExtractionFailureError,
    ThreadedExtractionRunner,
)
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter
from ba_downloader.infrastructure.runtime.interrupts import (
    CancellationFeedbackState,
    emit_cancellation_feedback,
    install_interrupt_handler,
)


class AssetExtractionWorkflow(AssetExtractionPort):
    POLL_INTERVAL_SECONDS = 0.2
    INTERRUPT_GRACE_SECONDS = 2.0

    def __init__(
        self,
        logger: LoggerPort,
        *,
        table_profile_factory: TableProfileFactory = build_default_table_profile_for_context,
        force_exit: Callable[[int], None] | None = None,
    ) -> None:
        self.logger = logger
        self._force_exit = force_exit or os._exit
        self._table_profile_factory = table_profile_factory
        self._threaded_runner = ThreadedExtractionRunner(
            logger,
            poll_interval_seconds=self.POLL_INTERVAL_SECONDS,
            interrupt_grace_seconds=self.INTERRUPT_GRACE_SECONDS,
            force_exit=self._force_exit,
        )
        self._process_table_runner = ProcessTableExtractionRunner(
            logger,
            poll_interval_seconds=self.POLL_INTERVAL_SECONDS,
            interrupt_grace_seconds=self.INTERRUPT_GRACE_SECONDS,
            table_profile_factory=self._table_profile_factory,
            force_exit=self._force_exit,
        )

    def extract_bundles(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        bundles = [
            str(bundle_path)
            for bundle_path in self._resolve_bundle_files(context, resources)
        ]
        if not bundles:
            return

        freeze_support()
        queue: multiprocessing.queues.Queue[str] = Queue()
        log_event_queue: multiprocessing.queues.Queue[BundleLogEvent] = Queue()
        error_count = multiprocessing.Value("i", 0)
        for bundle in bundles:
            queue.put(bundle)

        stop_event = Event()
        processes = self._build_bundle_processes(
            queue,
            context,
            len(bundles),
            error_count,
            log_event_queue,
        )

        try:
            failure_count = 0
            with (
                self._install_interrupt_handler(
                    stop_event,
                    on_interrupt=lambda: self._stop_bundle_processes(processes),
                ),
                RichProgressReporter(
                    len(bundles),
                    "Extracting bundles...",
                    extract_mode=True,
                ) as progress,
            ):
                self._start_bundle_processes(processes)
                failure_count = self._monitor_bundle_extraction(
                    queue=queue,
                    bundles=bundles,
                    processes=processes,
                    progress=progress,
                    stop_event=stop_event,
                    error_count=error_count,
                    log_events=log_event_queue,
                )
        finally:
            if stop_event.is_set():
                self._stop_bundle_processes(processes)
            for process in processes:
                process.join(timeout=self.POLL_INTERVAL_SECONDS)
            self._drain_bundle_log_events(log_event_queue)
            self._finalize_bundle_queue(queue, cancelled=stop_event.is_set())
            self._finalize_bundle_queue(
                log_event_queue,
                cancelled=stop_event.is_set(),
            )
            if stop_event.is_set():
                raise KeyboardInterrupt()
            if failure_count:
                raise ExtractionFailureError.from_count(
                    "bundle extraction",
                    failure_count,
                )

    def extract_media(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        files = [
            str(file_path)
            for file_path in self._resolve_media_files(context, resources)
        ]
        if not files:
            return

        extractor = MediaExtractor(context)
        self._threaded_runner.run(
            files,
            context,
            progress_title="Extracting media...",
            operation_name="media extraction",
            task=lambda zip_path, should_stop, progress_callback: extractor.extract_zip(
                zip_path,
                should_stop=should_stop,
                progress_callback=progress_callback,
            ),
        )

    def extract_tables(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        table_files = [
            table_path.name
            for table_path in self._resolve_table_files(context, resources)
        ]
        if not table_files:
            return

        table_file_metadata = self._resolve_table_file_metadata(context, resources)
        Path(context.extract_dir, "Table").mkdir(parents=True, exist_ok=True)
        if table_file_metadata:
            self._process_table_runner.run(
                table_files,
                context,
                metadata_by_file=table_file_metadata,
            )
            return

        self._process_table_runner.run(table_files, context)

    def _resolve_bundle_files(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None,
    ) -> list[Path]:
        if resources is not None:
            return self._resolve_existing_resource_files(
                context,
                resources,
                AssetType.bundle,
            )

        bundle_folder = Path(context.raw_dir) / "Bundle"
        if not bundle_folder.exists():
            return []
        return [
            bundle_folder / bundle.name
            for bundle in bundle_folder.iterdir()
            if bundle.is_file()
        ]

    def _resolve_media_files(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None,
    ) -> list[Path]:
        if resources is not None:
            return [
                file_path
                for file_path in self._resolve_existing_resource_files(
                    context,
                    resources,
                    AssetType.media,
                )
                if file_path.suffix.lower() == ".zip"
            ]

        media_folder = Path(context.raw_dir) / "Media"
        if not media_folder.exists():
            return []
        return list(media_folder.rglob("*.zip"))

    def _resolve_table_files(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None,
    ) -> list[Path]:
        if resources is not None:
            return self._resolve_existing_resource_files(
                context,
                resources,
                AssetType.table,
            )

        table_folder = Path(context.raw_dir) / "Table"
        if not table_folder.exists():
            return []
        return [
            file_path for file_path in table_folder.iterdir() if file_path.is_file()
        ]

    @staticmethod
    def _resolve_existing_resource_files(
        context: RuntimeContext,
        resources: AssetCollection,
        asset_type: AssetType,
    ) -> list[Path]:
        raw_dir = Path(context.raw_dir)
        files: list[Path] = []
        seen_paths: set[Path] = set()
        for resource in resources:
            if resource.asset_type is not asset_type:
                continue
            file_path = raw_dir / resource.path
            if file_path in seen_paths or not file_path.is_file():
                continue
            files.append(file_path)
            seen_paths.add(file_path)
        return files

    @staticmethod
    def _resolve_table_file_metadata(
        context: RuntimeContext,
        resources: AssetCollection | None,
    ) -> dict[str, dict[str, object]]:
        if resources is None:
            return {}
        raw_dir = Path(context.raw_dir)
        result: dict[str, dict[str, object]] = {}
        for resource in resources:
            if resource.asset_type is not AssetType.table:
                continue
            file_path = raw_dir / resource.path
            if not file_path.is_file():
                continue
            if resource.metadata:
                result.setdefault(file_path.name, dict(resource.metadata))
        return result

    @contextmanager
    def _install_interrupt_handler(
        self,
        stop_event: Event,
        *,
        on_interrupt: Callable[[], None] | None = None,
    ) -> Iterator[None]:
        with install_interrupt_handler(
            stop_event,
            self.logger,
            force_exit=self._force_exit,
            on_interrupt=on_interrupt,
        ):
            yield

    def _build_bundle_processes(
        self,
        queue: multiprocessing.queues.Queue[str],
        context: RuntimeContext,
        bundle_count: int,
        error_count: Any,
        log_events: multiprocessing.queues.Queue[BundleLogEvent],
    ) -> list[multiprocessing.Process]:
        process_count = min(
            max(context.threads, 1),
            bundle_count,
            os.cpu_count() or 1,
        )
        return [
            multiprocessing.Process(
                target=BundleExtractor.multiprocess_extract_worker,
                args=(
                    queue,
                    context,
                    BundleExtractor.MAIN_EXTRACT_TYPES,
                    error_count,
                    log_events,
                ),
            )
            for _ in range(process_count)
        ]

    @staticmethod
    def _start_bundle_processes(processes: list[multiprocessing.Process]) -> None:
        for process in processes:
            process.start()

    def _monitor_bundle_extraction(
        self,
        *,
        queue: multiprocessing.queues.Queue[str],
        bundles: list[str],
        processes: list[multiprocessing.Process],
        progress: RichProgressReporter,
        stop_event: Event,
        error_count: Any,
        log_events: multiprocessing.queues.Queue[BundleLogEvent],
    ) -> int:
        cancellation_state = CancellationFeedbackState()
        completed_bundles = 0
        failure_count = 0
        progress.set_status(f"0/{len(bundles)} bundles")
        while self._has_pending_bundle_work(queue, processes):
            self._drain_bundle_log_events(log_events)
            completed_bundles = max(0, len(bundles) - self._queue_size(queue))
            progress.set_completed(completed_bundles)
            progress.set_status(f"{completed_bundles}/{len(bundles)} bundles")
            if stop_event.is_set():
                self._stop_bundle_processes(processes)
                emit_cancellation_feedback(
                    self.logger,
                    cancellation_state,
                    grace_seconds=self.INTERRUPT_GRACE_SECONDS,
                    cancellation_message="Cancelling bundle extraction...",
                    still_stopping_message=(
                        "Extraction is still stopping. Press Ctrl+C again to force exit."
                    ),
                    has_pending_work=self._has_live_processes(processes),
                )
                if not self._has_live_processes(processes):
                    break

            stop_event.wait(self.POLL_INTERVAL_SECONDS)

        self._drain_bundle_log_events(log_events)
        if not stop_event.is_set():
            progress.set_completed(len(bundles))
            progress.set_status(f"{len(bundles)}/{len(bundles)} bundles")
            failure_count = max(0, int(error_count.value))
            if failure_count:
                self.logger.warn(
                    f"Extracted bundles with {failure_count} errors. "
                    "Check previous log lines for failed bundle paths."
                )
            else:
                self.logger.info("Extracted bundles successfully.")
        self._drain_bundle_log_events(log_events)
        return failure_count

    def _drain_bundle_log_events(
        self,
        log_events: multiprocessing.queues.Queue[BundleLogEvent],
    ) -> None:
        while True:
            try:
                event = log_events.get_nowait()
            except Empty:
                return
            if event.level == "info":
                self.logger.info(event.message)
            elif event.level == "warn":
                self.logger.warn(event.message)
            else:
                self.logger.error(event.message)

    @staticmethod
    def _queue_size(queue: multiprocessing.queues.Queue[str]) -> int:
        try:
            return queue.qsize()
        except (NotImplementedError, AttributeError):
            return 0

    @classmethod
    def _has_live_processes(cls, processes: list[multiprocessing.Process]) -> bool:
        return any(process.is_alive() for process in processes)

    @classmethod
    def _has_pending_bundle_work(
        cls,
        queue: multiprocessing.queues.Queue[str],
        processes: list[multiprocessing.Process],
    ) -> bool:
        return cls._queue_size(queue) > 0 or cls._has_live_processes(processes)

    @staticmethod
    def _stop_bundle_processes(processes: list[multiprocessing.Process]) -> None:
        for process in processes:
            if process.is_alive():
                process.kill()

    @staticmethod
    def _finalize_bundle_queue(
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
