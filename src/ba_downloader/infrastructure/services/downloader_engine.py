import os
from os import path
from queue import Empty, Queue
from threading import Event

from ba_downloader.infrastructure.regions.registry import DEFAULT_REGION_REGISTRY
from ba_downloader.lib.console import ProgressBar, bar_increase, bar_text, notice
from ba_downloader.lib.downloader import FileDownloader
from ba_downloader.lib.encryption import calculate_crc, calculate_md5
from ba_downloader.lib.structure import Resource, ResourceItem, ResourceType
from ba_downloader.utils.config import Config
from ba_downloader.utils.util import TaskManager
from ba_downloader.extractors.bundle import BundleExtractor
from ba_downloader.extractors.media import MediaExtractor
from ba_downloader.extractors.table import TableExtractor


class DownloaderEngine:
    """Download engine with verify and optional extraction."""

    def __init__(self) -> None:
        os.makedirs(Config.temp_dir, exist_ok=True)
        os.makedirs(Config.raw_dir, exist_ok=True)
        os.makedirs(Config.extract_dir, exist_ok=True)

    def main(self) -> Resource:
        region = DEFAULT_REGION_REGISTRY.resolve(Config.region)
        return region.main()

    def verify_worker(
        self,
        task_manager: TaskManager,
        res_to_download: Queue[ResourceItem],
        bar: ProgressBar,
    ) -> None:
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            resource: ResourceItem = task_manager.tasks.get()
            asset_path = path.join(Config.raw_dir, resource.path)
            bar.item_text(resource.path)
            verified = False

            if path.exists(asset_path) and path.getsize(asset_path) == resource.size:
                if resource.check_type == "crc":
                    verified = calculate_crc(asset_path) == resource.checksum
                elif resource.check_type == "md5":
                    verified = calculate_md5(asset_path) == resource.checksum

            if not verified:
                with task_manager.lock:
                    res_to_download.put(resource)

            bar.total = task_manager.tasks.qsize() or res_to_download.qsize()
            task_manager.tasks.task_done()

    def download_worker(
        self,
        task_manager: TaskManager,
        completed_res: Queue[ResourceItem],
        failed_res: Resource,
    ) -> None:
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            try:
                resource: ResourceItem = task_manager.tasks.get(block=True, timeout=0.5)
            except Empty:
                break

            if resource.size <= 1024**2:
                target_threads = Config.threads + ((8**7) // (resource.size + 1e-3))
                if len(task_manager.futures) < target_threads:
                    task_manager.increase_worker()

            directory_path, file_name = path.split(resource.path)
            os.makedirs(path.join(Config.raw_dir, directory_path), exist_ok=True)
            bar_text(file_name)

            if not FileDownloader(resource.url).save_file(path.join(Config.raw_dir, resource.path)):
                with task_manager.lock:
                    failed_res.add_item(resource)
            else:
                bar_increase()
                completed_res.put(resource)

            task_manager.tasks.task_done()

    def extract_worker(self, task_manager: TaskManager, bundle_working: Event) -> None:
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            resource: ResourceItem = task_manager.tasks.get()
            resource_path = path.join(Config.raw_dir, resource.path)

            if resource.resource_type == ResourceType.bundle:
                if not bundle_working.is_set():
                    bundle_working.set()
                    BundleExtractor().extract_bundle(resource_path, BundleExtractor.MAIN_EXTRACT_TYPES)
                    bundle_working.clear()
                else:
                    task_manager.tasks.put(resource)

            if resource.resource_type == ResourceType.media and resource.path.endswith(".zip"):
                MediaExtractor().extract_zip(resource_path)

            if resource.resource_type == ResourceType.table:
                TableExtractor(
                    path.join(Config.raw_dir, "Table"),
                    path.join(Config.extract_dir, "Table"),
                    f"{Config.extract_dir}.FlatData",
                ).extract_table(resource_path)

            task_manager.tasks.task_done()

    def verify_and_download(self, resource: Resource, retries: int = 0) -> None:
        res_to_download: Queue[ResourceItem] = Queue()
        res_to_extract: Queue[ResourceItem] = Queue()
        failed_res = Resource()

        if not resource:
            return

        resource.sorted_by_size()

        with ProgressBar(len(resource), "Verify and download files...", "item") as bar:
            verify_task = TaskManager(Config.threads, Config.threads, self.verify_worker)
            verify_task.import_tasks(resource)

            down_task = TaskManager(
                Config.threads,
                Config.max_threads,
                self.download_worker,
                res_to_download,
            )
            down_task.set_cancel_callback(
                notice,
                "Download has been canceled. Waiting for threads complete.",
                "error",
            )
            down_task.set_relation("shut", verify_task)

            bundle_working = Event()
            extract_task = TaskManager(
                Config.threads,
                Config.max_threads,
                self.extract_worker,
                res_to_extract,
            )
            extract_task.set_relation("shut", down_task)

            verify_task.run_without_block(res_to_download, bar)
            if Config.downloading_extract:
                down_task.run_without_block(res_to_extract, failed_res)
                extract_task.run(bundle_working)
            else:
                down_task.run(res_to_extract, failed_res)

            extract_task.done()
            down_task.done()
            verify_task.done()

        if verify_task.stop_task or down_task.stop_task:
            raise InterruptedError("Download has been canceled!")

        if failed_res and retries < Config.retries:
            notice(f"Retry for {len(failed_res)} failed files.")
            self.verify_and_download(failed_res, retries=retries + 1)
        elif failed_res:
            notice(f"Failed to download {len(failed_res)} files after retries.", "error")
        else:
            notice("All files have been download to your computer.")
