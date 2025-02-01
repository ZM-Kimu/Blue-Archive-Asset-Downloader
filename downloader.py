import os
from os import path
from queue import Empty, Queue

from lib.console import ProgressBar, bar_increase, bar_text, notice
from lib.downloader import FileDownloader
from lib.encryption import calculate_crc, calculate_md5
from lib.structure import Resource
from regions.cn import CNServer
from regions.gl import GLServer
from regions.jp import JPServer
from utils.config import Config
from utils.util import TaskManager


class Downloader:
    """Main downloader class."""

    def __init__(self) -> None:
        """Create directories for different files."""
        os.makedirs(Config.temp_dir, exist_ok=True)
        os.makedirs(Config.raw_dir, exist_ok=True)
        os.makedirs(Config.extract_dir, exist_ok=True)

    def main(self) -> None:
        """Main entry."""
        region: CNServer | GLServer | JPServer

        if "cn" in Config.region:
            region = CNServer()
        elif "gl" in Config.region:
            region = GLServer()
        elif "jp" in Config.region:
            region = JPServer()

        resource = region.main()

        self.verify_and_download(resource)
        # resource_to_download = self.get_changed_file(resource)
        # self.start_download_task(resource_to_download)

    def verify_worker(
        self, task_manager: TaskManager, res_to_download: Queue[dict], bar: ProgressBar
    ) -> None:
        """Verify files that already exist and have not been modified."""
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            res = task_manager.tasks.get()
            asset_path = path.join(Config.raw_dir, res["path"])
            bar.item_text(res["path"])
            verified = False
            if path.exists(asset_path) and path.getsize(asset_path) == res["size"]:
                if res["check_type"] == "crc":
                    verified = calculate_crc(asset_path) == res["checksum"]
                elif res["check_type"] == "md5":
                    verified = calculate_md5(asset_path) == res["checksum"]

            if not verified:
                with task_manager.lock:
                    res_to_download.put(res)

            bar.total = task_manager.tasks.qsize() or res_to_download.qsize()

            task_manager.tasks.task_done()

    def download_worker(self, task_manager: TaskManager, failed_res: Resource) -> None:
        """Worker thread that continuously takes tasks from the queue and downloads."""
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            # Break when queue is empty.
            try:
                res: dict = task_manager.tasks.get(block=True, timeout=0.5)
            except Empty:
                break

            # Dynamic change thread count.
            if res["size"] <= 1024**2:
                target_threads = Config.threads + ((8**7) // (res["size"] + 1e-3))
                if len(task_manager.futures) < target_threads:
                    task_manager.increase_worker()

            dir_path, file_name = path.split(res["path"])
            os.makedirs(path.join(Config.raw_dir, dir_path), exist_ok=True)
            bar_text(file_name)

            if not FileDownloader(res["url"]).save_file(
                path.join(Config.raw_dir, res["path"])
            ):
                with task_manager.lock:
                    failed_res.add_resource_item(res)
            else:
                bar_increase()

            task_manager.tasks.task_done()

    def verify_and_download(self, resource: Resource, retries: int = 0) -> None:
        """To verify and download file with thread pools."""
        res_to_download: Queue[dict] = Queue()
        failed_res = Resource()

        resource.sorted_by_size()  # Necessary for auto thread increment.

        if not resource:
            return

        with ProgressBar(len(resource), "Verify and download files...", "item") as bar:
            verify_task = TaskManager(
                Config.threads, Config.threads, self.verify_worker
            )
            verify_task.import_tasks(resource)
            verify_task.run_without_block(verify_task, res_to_download, bar)

            with TaskManager(
                Config.threads,
                Config.max_threads,
                self.download_worker,
                res_to_download,
            ) as down_task:
                down_task.set_cancel_callback(
                    notice,
                    "Download has been canceled. Waiting for threads complete.",
                    "error",
                )
                down_task.set_relate("event", verify_task)
                down_task.run(down_task, failed_res)

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
