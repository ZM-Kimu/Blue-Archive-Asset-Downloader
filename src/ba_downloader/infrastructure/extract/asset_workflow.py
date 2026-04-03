from __future__ import annotations

import os
import multiprocessing
import signal
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from multiprocessing import Queue, freeze_support
from pathlib import Path
from threading import Event, current_thread, main_thread
from collections.abc import Callable, Iterator

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import AssetExtractionPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.bundle import BundleExtractor
from ba_downloader.infrastructure.extractors.media import MediaExtractor
from ba_downloader.infrastructure.extractors.table import TableExtractor
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter


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
        processes = [
            multiprocessing.Process(
                target=BundleExtractor.multiprocess_extract_worker,
                args=(queue, context, BundleExtractor.MAIN_EXTRACT_TYPES),
            )
            for _ in range(min(5, max(len(bundles), 1)))
        ]

        try:
            with self._install_interrupt_handler(stop_event):
                with RichProgressReporter(len(bundles), "Extracting bundles...") as progress:
                    for process in processes:
                        process.start()

                    cancellation_logged = False
                    force_hint_logged = False
                    grace_deadline: float | None = None

                    while self._has_pending_bundle_work(queue, processes):
                        if stop_event.is_set():
                            if not cancellation_logged:
                                self.logger.warn("Cancelling bundle extraction...")
                                cancellation_logged = True
                                grace_deadline = time.monotonic() + self.INTERRUPT_GRACE_SECONDS
                                self._stop_bundle_processes(processes)
                            elif (
                                self._has_live_processes(processes)
                                and grace_deadline is not None
                                and time.monotonic() >= grace_deadline
                                and not force_hint_logged
                            ):
                                self.logger.warn(
                                    "Extraction is still stopping. Press Ctrl+C again to force exit."
                                )
                                force_hint_logged = True
                            if not self._has_live_processes(processes):
                                break

                        progress.set_completed(len(bundles) - self._queue_size(queue))
                        time.sleep(self.POLL_INTERVAL_SECONDS)

                    progress.set_completed(len(bundles))
                    if not stop_event.is_set():
                        self.logger.info("Extracted bundles successfully.")
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
        executor = ThreadPoolExecutor(max_workers=min(8, len(files)))

        try:
            with self._install_interrupt_handler(stop_event):
                with RichProgressReporter(len(files), "Extracting media...") as progress:
                    future_map = {
                        executor.submit(extractor.extract_zip, zip_path): zip_path
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
        executor = ThreadPoolExecutor(max_workers=min(max(context.threads, 1), len(table_files)))

        try:
            with self._install_interrupt_handler(stop_event):
                with RichProgressReporter(len(table_files), "Extracting table files...") as progress:
                    future_map = {
                        executor.submit(extractor.extract_table, table_file): table_file
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
        if interrupt_count >= 2:
            self.logger.error("Force exiting immediately.")
            self._force_exit(130)

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
        cancellation_logged = False
        force_hint_logged = False
        grace_deadline: float | None = None

        while pending_futures:
            done_futures, pending_futures = wait(
                pending_futures,
                timeout=self.POLL_INTERVAL_SECONDS,
                return_when=FIRST_COMPLETED,
            )

            if stop_event.is_set():
                if not cancellation_logged:
                    self.logger.warn(f"Cancelling {operation_name}...")
                    cancellation_logged = True
                    grace_deadline = time.monotonic() + self.INTERRUPT_GRACE_SECONDS
                for pending_future in pending_futures:
                    pending_future.cancel()
                if (
                    pending_futures
                    and grace_deadline is not None
                    and time.monotonic() >= grace_deadline
                    and not force_hint_logged
                ):
                    self.logger.warn(
                        "Extraction is still stopping. Press Ctrl+C again to force exit."
                    )
                    force_hint_logged = True

            for future in done_futures:
                if future.cancelled():
                    continue
                file_path = future_map[future]
                progress.set_description(f"Extracting {Path(file_path).name}")
                future.result()
                progress.advance()
