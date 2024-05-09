import os
from threading import Thread
from time import sleep, time
from zipfile import ZipFile


class Extractor:

    def __init__(self, dl) -> None:
        self.downloader = dl

    def extractApkFile(self, apk_path) -> None:
        with ZipFile(os.path.join(apk_path), "r") as zip:
            files = [
                item if item.startswith("assets/") else None for item in zip.namelist()
            ]
            Thread(
                target=self.downloader.progressBar,
                args=(len(files), "Extracting APK...", "items"),
            ).start()
            for item in files:
                self.downloader.shared_counter += 1
                self.downloader.shared_message = item
                if item and not (
                    os.path.exists(os.path.join(self.downloader.raw_dir, item))
                    and zip.getinfo(item).file_size
                    == os.path.getsize(os.path.join(self.downloader.raw_dir, item))
                ):
                    zip.extract(item, self.downloader.raw_dir)
            self.downloader.shared_interrupter = True
            sleep(0.2)

    def extractBundleFile(self) -> None:
        os.walk()
