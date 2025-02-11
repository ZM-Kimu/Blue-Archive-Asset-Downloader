import os
from os import path
from queue import Empty, Queue
from threading import Event

from lib.console import ProgressBar, bar_increase, bar_text, notice
from lib.downloader import FileDownloader
from lib.encryption import calculate_crc, calculate_md5
from lib.structure import Resource, ResourceItem, ResourceType
from regions.cn import CNServer
from regions.gl import GLServer
from regions.jp import JPServer
from utils.config import Config
from utils.util import TaskManager
from xtractor.bundle import BundleExtractor
from xtractor.media import MediaExtractor
from xtractor.table import TableExtractor


class Downloader:
    """Main downloader class."""

    def __init__(self) -> None:
        """Create directories for different files."""
        os.makedirs(Config.temp_dir, exist_ok=True)
        os.makedirs(Config.raw_dir, exist_ok=True)
        os.makedirs(Config.extract_dir, exist_ok=True)

    def main(self) -> Resource:
        """Main entry."""
        region: CNServer | GLServer | JPServer

        if "cn" in Config.region:
            region = CNServer()
        elif "gl" in Config.region:
            region = GLServer()
        elif "jp" in Config.region:
            region = JPServer()

        resource = region.main()

        return resource

    def verify_worker(
        self,
        task_manager: TaskManager,
        res_to_download: Queue[ResourceItem],
        bar: ProgressBar,
    ) -> None:
        """Verify files that already exist and have not been modified."""
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            res: ResourceItem = task_manager.tasks.get()
            asset_path = path.join(Config.raw_dir, res.path)
            bar.item_text(res.path)
            verified = False
            if path.exists(asset_path) and path.getsize(asset_path) == res.size:
                if res.check_type == "crc":
                    verified = calculate_crc(asset_path) == res.checksum
                elif res.check_type == "md5":
                    verified = calculate_md5(asset_path) == res.checksum

            if not verified:
                with task_manager.lock:
                    res_to_download.put(res)

            bar.total = task_manager.tasks.qsize() or res_to_download.qsize()

            task_manager.tasks.task_done()

    def download_worker(
        self, task_manager: TaskManager, completed_res: Queue, failed_res: Resource
    ) -> None:
        """Worker thread that continuously takes tasks from the queue and downloads."""
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            # Break when queue is empty.
            try:
                res: ResourceItem = task_manager.tasks.get(block=True, timeout=0.5)
            except Empty:
                break

            # Dynamic change thread count.
            if res.size <= 1024**2:
                target_threads = Config.threads + ((8**7) // (res.size + 1e-3))
                if len(task_manager.futures) < target_threads:
                    task_manager.increase_worker()

            dir_path, file_name = path.split(res.path)
            os.makedirs(path.join(Config.raw_dir, dir_path), exist_ok=True)
            bar_text(file_name)

            if not FileDownloader(res.url).save_file(
                path.join(Config.raw_dir, res.path)
            ):
                with task_manager.lock:
                    failed_res.add_item(res)
            else:
                bar_increase()
                completed_res.put(res)

            task_manager.tasks.task_done()

    def extract_worker(self, task_manager: TaskManager, bundle_working: Event) -> None:
        """Extract a file after a file downloaded."""
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            res: ResourceItem = task_manager.tasks.get()
            res_path = path.join(Config.raw_dir, res.path)

            if res.resource_type == ResourceType.bundle:
                if not bundle_working.is_set():
                    bundle_working.set()
                    BundleExtractor().extract_bundle(
                        res_path, BundleExtractor.MAIN_EXTRACT_TYPES
                    )
                    bundle_working.clear()
                else:
                    task_manager.tasks.put(res)
            if res.resource_type == ResourceType.media and res.path.endswith(".zip"):
                MediaExtractor().extract_zip(res_path)
            if res.resource_type == ResourceType.table:
                TableExtractor(
                    path.join(Config.raw_dir, "Table"),
                    path.join(Config.extract_dir, "Table"),
                    f"{Config.extract_dir}.FlatData",
                ).extract_table(res_path)

            task_manager.tasks.task_done()

    def verify_and_download(self, resource: Resource, retries: int = 0) -> None:
        """To verify and download file with thread pools."""
        res_to_download: Queue[ResourceItem] = Queue()
        res_to_extract: Queue[ResourceItem] = Queue()
        failed_res = Resource()

        if not resource:
            return

        resource.sorted_by_size()  # Necessary for auto thread increment.

        # In this implementation, download will wait for verify to provide data, and extract will wait for download to provide data.
        with ProgressBar(len(resource), "Verify and download files...", "item") as bar:
            verify_task = TaskManager(
                Config.threads, Config.threads, self.verify_worker
            )
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
                Config.threads, Config.max_threads, self.extract_worker, res_to_extract
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

        if failed_res:
            notice(f"Retry for {len(failed_res)} failed files.")
            self.verify_and_download(failed_res, retries=retries + 1)

        if not failed_res:
            notice("All files have been download to your computer.")


if __name__ == "__main__":
    downloader = Downloader()
    downloader.main()
