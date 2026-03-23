from __future__ import annotations

import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Queue, freeze_support
from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import AssetExtractionPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.bundle import BundleExtractor
from ba_downloader.infrastructure.extractors.media import MediaExtractor
from ba_downloader.infrastructure.extractors.table import TableExtractor
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter


class AssetExtractionWorkflow(AssetExtractionPort):
    def __init__(self, logger: LoggerPort) -> None:
        self.logger = logger

    def extract_bundles(self, context: RuntimeContext) -> None:
        bundle_folder = Path(context.raw_dir) / "Bundle"
        if not bundle_folder.exists():
            return

        freeze_support()
        queue: multiprocessing.queues.Queue[str] = Queue()
        bundles = [str(bundle_folder / bundle.name) for bundle in bundle_folder.iterdir()]
        for bundle in bundles:
            queue.put(bundle)

        with RichProgressReporter(len(bundles), "Extracting bundles...") as progress:
            processes = [
                multiprocessing.Process(
                    target=BundleExtractor.multiprocess_extract_worker,
                    args=(queue, context, BundleExtractor.MAIN_EXTRACT_TYPES),
                )
                for _ in range(min(5, max(len(bundles), 1)))
            ]
            for process in processes:
                process.start()

            try:
                while not queue.empty():
                    progress.set_completed(len(bundles) - queue.qsize())
                    time.sleep(0.1)
                self.logger.warn("Extracted bundles successfully.")
            except KeyboardInterrupt:
                self.logger.error("Bundle extract task has been canceled.")
                for process in processes:
                    process.kill()
            finally:
                for process in processes:
                    process.join(timeout=0.2)

    def extract_media(self, context: RuntimeContext) -> None:
        media_folder = Path(context.raw_dir) / "Media"
        if not media_folder.exists():
            return

        files = [str(file_path) for file_path in media_folder.rglob("*.zip")]
        if not files:
            return

        extractor = MediaExtractor(context)
        with RichProgressReporter(len(files), "Extracting media...") as progress:
            with ThreadPoolExecutor(max_workers=min(8, len(files))) as executor:
                future_map = {
                    executor.submit(extractor.extract_zip, zip_path): zip_path
                    for zip_path in files
                }
                for future in as_completed(future_map):
                    zip_path = future_map[future]
                    progress.set_description(f"Extracting {Path(zip_path).name}")
                    future.result()
                    progress.advance()

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

        with RichProgressReporter(len(table_files), "Extracting table files...") as progress:
            with ThreadPoolExecutor(max_workers=min(max(context.threads, 1), len(table_files))) as executor:
                future_map = {
                    executor.submit(extractor.extract_table, table_file): table_file
                    for table_file in table_files
                }
                for future in as_completed(future_map):
                    table_file = future_map[future]
                    progress.set_description(f"Extracting {table_file}")
                    future.result()
                    progress.advance()
