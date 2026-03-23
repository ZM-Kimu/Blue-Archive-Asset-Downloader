import concurrent
import concurrent.futures
import os
from concurrent.futures import ThreadPoolExecutor
from os import path
from queue import Empty, Queue
from threading import Lock
from time import sleep

from lib.console import ProgressBar, bar_increase, bar_text, notice
from lib.downloader import FileDownloader
from lib.encryption import calculate_crc, calculate_md5
from regions.cn import CNServer
from regions.gl import GLServer
from regions.jp import JPServer
from utils.config import Config
from utils.resource_structure import Resource


class Downloader:
    """Main downloader class."""

    def __init__(self) -> None:
        self.stop_task = False

    def init(self) -> None:
        """Create directories for different files."""
        os.makedirs(Config.temp_dir, exist_ok=True)
        os.makedirs(Config.raw_dir, exist_ok=True)
        os.makedirs(Config.extract_dir, exist_ok=True)

    def main(self) -> None:
        """Main entry."""
        region: CNServer | GLServer | JPServer

        self.init()

        if "cn" in Config.region:
            region = CNServer()
        elif "gl" in Config.region:
            region = GLServer()
        elif "jp" in Config.region:
            region = JPServer()

        resource = region.main()
        resource_to_download = self.get_changed_file(resource)
        self.start_download_resource_task(resource_to_download)

    def get_changed_file(self, resource: Resource) -> Resource:
        """Verify files that already exist and have not been modified."""
        res_to_download = Resource()

        with ProgressBar(len(resource), "Verify exsist files...", "item") as bar:
            for res in resource:
                asset_path = path.join(Config.raw_dir, res["path"])
                bar.item_text(asset_path)
                bar.increase()
                if path.exists(asset_path) and path.getsize(asset_path) == res["size"]:
                    verified = False
                    if res["check_type"] == "crc":
                        verified = calculate_crc(asset_path) == res["checksum"]
                    elif res["check_type"] == "md5":
                        verified = calculate_md5(asset_path) == res["checksum"]
                    if verified:
                        continue
                res_to_download.add_resource_item(res)

        notice(f"{len(res_to_download)} files need to download.")
        return res_to_download

    def download_worker(
        self, resource_queue: Queue, failed_res: Resource, lock: Lock
    ) -> None:
        """Worker thread that continuously takes tasks from the queue and downloads."""
        while not self.stop_task:
            # Break when queue is empty.
            try:
                res: dict = resource_queue.get(block=True, timeout=0.5)
            except Empty:
                break

            dir_path, file_name = path.split(res["path"])
            os.makedirs(path.join(Config.raw_dir, dir_path), exist_ok=True)
            bar_text(file_name)

            if not FileDownloader(res["url"]).save_file(
                path.join(Config.raw_dir, res["path"])
            ):
                with lock:
                    failed_res.add_resource_item(res)
            else:
                bar_increase()

            resource_queue.task_done()

    def start_download_resource_task(
        self, resource: Resource, retries: int = 0
    ) -> None:
        """Distribute resource to different threads dynamically and support re-downloading of failed files."""
        failed_res = Resource()
        task_queue: Queue[dict] = Queue()

        if not resource:
            return
        resource.sorted_by_size()  # Necessary for auto thread increment.

        for res in resource:
            task_queue.put(res)

        executor = ThreadPoolExecutor(max_workers=Config.max_threads)

        with ProgressBar(len(resource), "Downloading resource...", "items"):
            futures: list[concurrent.futures.Future] = []
            lock = Lock()

            try:
                while not (task_queue.empty() and all(f.done() for f in futures)):
                    queue_snapshot = list(task_queue.queue)
                    running_threads = Config.threads

                    if queue_snapshot and queue_snapshot[0]["size"] <= 1024**2:
                        running_threads = Config.threads + (
                            (8**7) // queue_snapshot[0]["size"] + 1e-3
                        )

                    while len(futures) < running_threads and not task_queue.empty():
                        futures.append(
                            executor.submit(
                                self.download_worker, task_queue, failed_res, lock
                            )
                        )

                    sleep(0.1)

            except KeyboardInterrupt:
                notice(
                    "Download has been canceled. Waiting for threads complete.", "error"
                )
                self.stop_task = True
                executor.shutdown(cancel_futures=True)
            finally:
                for future in futures:
                    future.result()

        executor.shutdown(wait=True)

        if failed_res:
            notice(f"Retry for {len(failed_res)} failed files.")
            self.start_download_resource_task(failed_res, retries=retries + 1)

        if not (self.stop_task or failed_res):
            notice("All files have been download to your computer.")


if __name__ == "__main__":
    downloader = Downloader()
    downloader.main()
