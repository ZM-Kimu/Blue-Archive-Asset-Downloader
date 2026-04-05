from __future__ import annotations

import multiprocessing
import os
import sqlite3
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from multiprocessing import Queue, freeze_support
from pathlib import Path
from threading import Event
from zipfile import BadZipFile

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import AssetExtractionPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.bundle import BundleExtractor
from ba_downloader.infrastructure.extractors.media import MediaExtractor
from ba_downloader.infrastructure.extractors.table import TableExtractor
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter
from ba_downloader.infrastructure.runtime.interrupts import (
    CancellationFeedbackState,
    build_future_wait_policy,
    emit_cancellation_feedback,
    install_interrupt_handler,
    wait_for_operation_futures,
)


class AssetExtractionWorkflow(AssetExtractionPort):
    POLL_INTERVAL_SECONDS = 0.2
    INTERRUPT_GRACE_SECONDS = 2.0

    def __init__(
        self,
        logger: LoggerPort,
        *,
        force_exit: Callable[[int], None] | None = None,
    ) -> None:
        self.logger = logger
        self._force_exit = force_exit or os._exit
        self._wait_policy = build_future_wait_policy(
            self.logger, self.POLL_INTERVAL_SECONDS, self.INTERRUPT_GRACE_SECONDS, "Extraction"
        )

    def extract_bundles(self, context: RuntimeContext) -> None:
        bundle_folder = Path(context.raw_dir) / "Bundle"
        if not bundle_folder.exists():
            return

        freeze_support()
        queue: multiprocessing.queues.Queue[str] = Queue()
        bundles = [str(bundle_folder / bundle.name) for bundle in bundle_folder.iterdir()]
        for bundle in bundles:
            queue.put(bundle)

        stop_event = Event()
        processes = self._build_bundle_processes(queue, context, len(bundles))

        try:
            with self._install_interrupt_handler(
                stop_event,
                on_interrupt=lambda: self._stop_bundle_processes(processes),
            ), RichProgressReporter(
                len(bundles),
                "Extracting bundles...",
            ) as progress:
                self._start_bundle_processes(processes)
                self._monitor_bundle_extraction(
                    queue=queue,
                    bundles=bundles,
                    processes=processes,
                    progress=progress,
                    stop_event=stop_event,
                )
        finally:
            if stop_event.is_set():
                self._stop_bundle_processes(processes)
            for process in processes:
                process.join(timeout=self.POLL_INTERVAL_SECONDS)
            if stop_event.is_set():
                raise KeyboardInterrupt()

    def extract_media(self, context: RuntimeContext) -> None:
        media_folder = Path(context.raw_dir) / "Media"
        if not media_folder.exists():
            return

        files = [str(file_path) for file_path in media_folder.rglob("*.zip")]
        if not files:
            return

        extractor = MediaExtractor(context)
        stop_event = Event()
        future_map: dict[Future[None], str] = {}
        executor = ThreadPoolExecutor(max_workers=min(max(context.threads, 1), len(files)))

        try:
            with self._install_interrupt_handler(stop_event), RichProgressReporter(
                len(files),
                "Extracting media...",
            ) as progress:
                future_map = {
                    executor.submit(
                        extractor.extract_zip,
                        zip_path,
                        should_stop=stop_event.is_set,
                    ): zip_path
                    for zip_path in files
                }
                self._drain_extraction_futures(
                    set(future_map),
                    future_map,
                    stop_event,
                    progress,
                    "media extraction",
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            if stop_event.is_set():
                raise KeyboardInterrupt()

    def extract_tables(self, context: RuntimeContext) -> None:
        extractor = TableExtractor.from_context(context, self.logger)
        table_folder = Path(extractor.table_file_folder)
        if not table_folder.exists():
            return

        Path(extractor.extract_folder).mkdir(parents=True, exist_ok=True)
        table_files = [
            file_path.name for file_path in table_folder.iterdir() if file_path.is_file()
        ]
        if not table_files:
            return

        stop_event = Event()
        future_map: dict[Future[None], str] = {}
        executor = ThreadPoolExecutor(
            max_workers=min(max(context.threads, 1), len(table_files))
        )

        try:
            with self._install_interrupt_handler(stop_event), RichProgressReporter(
                len(table_files),
                "Extracting table files...",
            ) as progress:
                future_map = {
                    executor.submit(
                        extractor.extract_table,
                        table_file,
                        should_stop=stop_event.is_set,
                    ): table_file
                    for table_file in table_files
                }
                self._drain_extraction_futures(
                    set(future_map),
                    future_map,
                    stop_event,
                    progress,
                    "table extraction",
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            if stop_event.is_set():
                raise KeyboardInterrupt()

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
    ) -> list[multiprocessing.Process]:
        process_count = min(
            max(context.threads, 1),
            bundle_count,
            os.cpu_count() or 1,
        )
        return [
            multiprocessing.Process(
                target=BundleExtractor.multiprocess_extract_worker,
                args=(queue, context, BundleExtractor.MAIN_EXTRACT_TYPES),
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
    ) -> None:
        cancellation_state = CancellationFeedbackState()
        while self._has_pending_bundle_work(queue, processes):
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

            progress.set_completed(len(bundles) - self._queue_size(queue))
            stop_event.wait(self.POLL_INTERVAL_SECONDS)

        progress.set_completed(len(bundles))
        if not stop_event.is_set():
            self.logger.info("Extracted bundles successfully.")

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

    def _drain_extraction_futures(
        self,
        pending_futures: set[Future[None]],
        future_map: dict[Future[None], str],
        stop_event: Event,
        progress: RichProgressReporter,
        operation_name: str,
    ) -> None:
        cancellation_state = CancellationFeedbackState()

        while pending_futures:
            done_futures, pending_futures = wait_for_operation_futures(
                pending_futures,
                stop_event,
                self._wait_policy,
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
                    self.logger.error(f"Failed to extract {file_path}: {exc}")
                except (
                    BadZipFile,
                    LookupError,
                    OSError,
                    sqlite3.Error,
                    TypeError,
                    ValueError,
                ) as exc:
                    self.logger.error(f"Failed to extract {file_path}: {exc}")
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    self.logger.error(f"Failed to extract {file_path}: {exc}")
                progress.advance()

    @staticmethod
    def _is_cancelled_error(exc: Exception) -> bool:
        return "extraction cancelled by user" in str(exc).lower()
