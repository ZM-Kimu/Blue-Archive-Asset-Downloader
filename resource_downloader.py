import argparse
import concurrent
import concurrent.futures
import json
import os
import re
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from os import path
from queue import Empty, Queue
from threading import Lock, Thread
from time import sleep, time
from typing import Literal
from urllib.parse import urljoin

import requests  # type: ignore
from cloudscraper import create_scraper

from resource_extractor import CNCatalogDecoder, Extractor, JPCatalogDecoder
from utils import utils
from utils.console import ProgressBar, bar_increase, bar_text, notice, print
from utils.resource_structure import CNResource, JPResource, Resource

# Commandline Arguments
parser = argparse.ArgumentParser(description="碧蓝档案素材下载器")
parser.add_argument_group("Required Arguments").add_argument(
    "--region", "-g", type=str, help="Server region: cn/gl/jp", required=True
)
# Optional
parser.add_argument(
    "--threads", "-t", type=int, help="Number of download threads", default=20
)
parser.add_argument(
    "--version",
    "-v",
    type=str,
    help="Game version, automatically retrieved if not specified",
    default="",
)
parser.add_argument(
    "--raw", "-r", type=str, help="Output location for raw files", default="RawData"
)
parser.add_argument(
    "--extract",
    "-e",
    type=str,
    help="Output location for extracted files",
    default="Extracted",
)
parser.add_argument(
    "--temporary",
    "-m",
    type=str,
    help="Output location for temporary files",
    default="Temp",
)
parser.add_argument(
    "--downloading-extract",
    "-d",
    action="store_true",
    help="Extract files while downloading",
)
parser.add_argument(
    "--proxy",
    "-p",
    type=str,
    help="Set HTTP proxy for downloading",
    default="",
)
parser.add_argument(
    "--max-retries",
    "-x",
    type=int,
    help="Maximum number of retries during download",
    default=5,
)
parser.add_argument(
    "--search",
    "-s",
    type=str,
    help="Search files containing specified keywords",
    default="",
)

args = parser.parse_args()


# Basic configuration for next steps.
class Configuration:
    def __init__(self, config) -> None:
        self.threads: int = config.threads
        self.version: str = config.version
        self.region: str = config.region.lower()
        self.raw_dir: str = config.raw
        self.extract_dir: str = config.extract
        self.temp_dir: str = config.temporary
        self.download_and_extract: bool = config.downloading_extract
        self.search = config.search
        self.proxy: dict | None = (
            {"http": config.proxy, "https": config.proxy} if config.proxy else None
        )
        self.retries: int = config.max_retries
        self.work_dir: str = os.getcwd()
        self.max_threads: int = self.threads * 7
        with open("CharactersMapping.json", "r", encoding="utf8") as f:
            self.character_mapping: dict = json.load(f)


class Downloader(Configuration):
    """Main downloader class."""

    def __init__(self, config) -> None:
        super().__init__(config)
        self.app = "com.nexon.bluearchive"
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.extractor = Extractor(self)
        self.stop_task = False

    def init(self) -> None:
        """Create directories for different files."""
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.extract_dir, exist_ok=True)

    # The private function is used to download file from a compressed file within a specified range and decompress it.
    def __download_and_decompress_file(
        self, apk_url: str, target_path: str, header_part: bytes, start_offset: int
    ) -> bool:
        """Request partial data from an online compressed file and then decompress it."""
        try:
            header = struct.unpack("<IHHHHHIIIHH", header_part[:30])
            _, _, _, compression, _, _, _, comp_size, _, file_name_len, extra_len = (
                header
            )
            data_start = start_offset + 30 + file_name_len + extra_len
            data_end = data_start + comp_size
            compressed_data = self.file_downloader(
                apk_url,
                False,
                {"Range": f"bytes={data_start}-{data_end - 1}"},
            )
            return self.extractor.decompress_file_part(
                compressed_data, target_path, compression
            )
        except:
            return False

    def main(self) -> None:
        """Main entry."""
        region: CNServer | GLServer | JPServer

        self.init()

        if "cn" in self.region:
            region = CNServer(self)
        elif "gl" in self.region:
            region = GLServer(self)
        elif "jp" in self.region:
            region = JPServer(self)

        if not region:
            raise ValueError("The region argument does not match one of cn/gl/jp.")

        resource = region.main()
        resource_to_download = self.get_changed_file(resource)
        # self.start_download_resource_task(resource_to_download)
        self.start_resource_download_task(resource_to_download)

    def get_changed_file(self, resource: Resource) -> Resource:
        """Verify files that already exist and have not been modified."""
        res_to_download = Resource()

        with ProgressBar(len(resource), "Verify exsist files...", "item") as bar:
            for res in resource:
                asset_path = path.join(self.raw_dir, res["path"])
                bar.item_text(asset_path)
                bar.increase()
                if path.exists(asset_path) and path.getsize(asset_path) == res["size"]:
                    verified = False
                    if res["check_type"] == "crc":
                        verified = utils.calculate_crc(asset_path) == res["checksum"]
                    elif res["check_type"] == "md5":
                        verified = utils.calculate_md5(asset_path) == res["checksum"]
                    elif res["check_type"] == "hash":
                        verified = a(asset_path) == res["checksum"]
                    if verified:
                        continue
                res_to_download.add_resource_item(res)

        notice(f"{len(res_to_download)} files need to download.")
        return res_to_download

    def download_resource_thread(self, part: list, failed_res: Resource) -> None:
        """Download and collect files failed to download."""
        for res in part:
            dir_path, file_name = path.split(res["path"])
            os.makedirs(path.join(self.raw_dir, dir_path), exist_ok=True)
            bar_text(file_name)

            if not self.file_downloader(
                res["url"], path.join(self.raw_dir, res["path"]), self.headers
            ):
                failed_res.add_resource_item(res)
            else:
                bar_increase()

    def start_download_resource_task(
        self, resource: Resource, __retries: int = 0
    ) -> None:
        """Distribute resource to different threads and support re-downloading of failed files."""
        failed_res = Resource()
        threads: list[Thread] = []

        if not resource:
            return

        with ProgressBar(len(resource), "Downloading resource...", "items"):
            res_blocks = list(utils.seperate_list_as_blocks(resource, self.threads))
            for block in res_blocks:
                utils.create_thread(
                    self.download_resource_thread, threads, block, failed_res
                )
            for thread in threads:
                thread.join()

        if __retries > self.retries:
            print(
                f"Max retries exceeded for {self.retries} times with retring failed files."
            )
            return

        if failed_res:
            notice(f"Retry for {len(failed_res)} failed files.")
            self.start_download_resource_task(failed_res, __retries + 1)

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
            os.makedirs(path.join(self.raw_dir, dir_path), exist_ok=True)
            bar_text(file_name)

            if not self.file_downloader(
                res["url"], path.join(self.raw_dir, res["path"]), self.headers
            ):
                with lock:
                    failed_res.add_resource_item(res)
            else:
                bar_increase()

            resource_queue.task_done()

    def start_resource_download_task(
        self, resource: Resource, __retries: int = 0
    ) -> None:
        """Distribute resource to different threads dynamically and support re-downloading of failed files."""
        failed_res = Resource()
        task_queue: Queue[dict] = Queue()

        if not resource:
            return
        resource.sorted_by_size()

        for res in resource:
            task_queue.put(res)

        executor = ThreadPoolExecutor(max_workers=self.max_threads)

        with ProgressBar(len(resource), "Downloading resource...", "items"):
            futures: list[concurrent.futures.Future] = []
            lock = Lock()

            try:
                while not (task_queue.empty() and all(f.done() for f in futures)):
                    queue_snapshot = list(task_queue.queue)
                    running_threads = self.threads

                    if queue_snapshot and queue_snapshot[0]["size"] <= 1024**2:
                        running_threads = self.threads + (
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
                notice("Download has been canceled.", "error")
                self.stop_task = True
                executor.shutdown(cancel_futures=True)
            finally:
                for future in futures:
                    future.result()

        executor.shutdown(wait=True)

        if failed_res:
            notice(f"Retry for {len(failed_res)} failed files.")
            self.start_download_resource_task(failed_res, __retries + 1)

        notice("All files have been download to your computer.")

    # Multi-mode downloader supporting error retries.
    def file_downloader(
        self,
        url: str,
        target: str | bool,
        headers: dict,
        __retried: int = 0,
        *,
        use_stream_in_response: bool = False,
        enable_progress: bool = False,
    ) -> bytes | requests.Response | bool:
        """Download the file resource.

        Args:
            url (str): Url of remote file.
            target (str | bool):
                str: Data will save to the path you provide.\n
                False: Return received bytes.\n
                True: Return the request instance.
            headers (dict): Headers for request url.
            __retried (int, optional): Internal recursive retry. Defaults to 0.
            use_stream_in_response (bool, optional): When target is response, set response type as stream. Defaults to False.
            enable_progress (bool, optional): True for enable progress bar increment, depend on target model. Defaults to False.

        Raises:
            ConnectionError: Retry when too slow.

        Returns:
            bytes | Response | bool:
            bytes(when target is false): The data received from response.
            Response(when target is true): The response of request.
            bool(when target is str): Is or not successful download the file.
        """
        counter = 0
        if __retried > self.retries:
            print(
                f"Max retries exceeded for {self.retries} times with file {path.split(url)[-1]}."
            )
            return False
        try:
            response = requests.get(
                url,
                headers=headers,
                stream=isinstance(target, str) or use_stream_in_response,
                proxies=self.proxy,
                timeout=10,
            )
            if isinstance(target, str):
                with open(target, "wb") as file:
                    start_time = time()
                    for chunk in response.iter_content(chunk_size=4096):
                        file.write(chunk)
                        counter += len(chunk)
                        bar_increase(len(chunk) if enable_progress else 0)
                        if counter < 4096 * (time() - start_time):
                            raise ConnectionError("Downloading too slow. Reset...")
                return True
            if target is True:
                bar_increase()
                return response
            if target is False:
                return response.content
            raise ValueError(f"Parameter target does not match type of {target}.")
        except:
            bar_increase(-counter if enable_progress else 0)
            return self.file_downloader(
                url,
                target,
                headers,
                __retried + 1,
                use_stream_in_response=use_stream_in_response,
                enable_progress=enable_progress,
            )


class CNServer:
    def __init__(self, downloader: Downloader) -> None:
        self.d = downloader
        self.urls = {
            "home": "https://bluearchive-cn.com/",
            "version": "https://bluearchive-cn.com/api/meta/setup",
            "info": "https://gs-api.bluearchive-cn.com/api/state",
            "bili": "https://line1-h5-pc-api.biligame.com/game/detail/gameinfo?game_base_id=109864",
        }

    def main(self) -> Resource:
        """Main entry for CNServer"""
        version = self.d.version
        if not version:
            notice("Version not specified. Automatically fetching latest...")
            version = self.d.version = self.get_latest_version()
        notice(f"Current resource version: {version}")
        apk_url = self.get_apk_url(version)
        self.download_extract_apk_file(apk_url)
        server_info = self.get_server_info()
        print("Pulling manifest...")
        resources = self.get_resource_manifest(server_info)
        print(f"Manifest: {resources}.")
        return resources

    def download_extract_apk_file(self, apk_url: str) -> None:
        """The CN APK might include special files."""
        print("Download APK to get table and media files...")
        apk_size = int(
            create_scraper()
            .head(apk_url, proxies=self.d.proxy, timeout=10)
            .headers.get("Content-Length", 0)
        )
        if apk_size == 0:
            notice("Unable to retrieve package size. Using bilibili.", "error")
            return self.download_extract_apk_file(self.get_apk_url("bili"))

        threads: list[Thread] = []
        os.makedirs(self.d.temp_dir, exist_ok=True)
        apk_path = path.join(self.d.temp_dir, path.split(apk_url)[-1])

        if not (path.exists(apk_path) and path.getsize(apk_path) == apk_size):
            # Create multi-thread downloading task. The CN official server might block connect by short time too many access.
            thread_num = 5
            chunk_size = apk_size // thread_num
            with ProgressBar(apk_size, "Downloading APK...", "MB", 1048576):
                for i in range(thread_num):
                    start = chunk_size * i
                    end = start + chunk_size - 1 if i != thread_num - 1 else apk_size
                    output = path.join(self.d.temp_dir, f"chunk_{i}.dat")
                    header = {"Range": f"bytes={start}-{end}"}
                    utils.create_thread(
                        self.d.file_downloader,
                        threads,
                        apk_url,
                        output,
                        header,
                        enable_progress=True,
                    )

                # self.d.set_progress_bar_message(apk_url.rsplit("/", 1)[-1])
                for thread in threads:
                    thread.join()

            with open(apk_path, "wb") as apk:
                for i in range(thread_num):
                    chunk_path = path.join(self.d.temp_dir, f"chunk_{i}.dat")
                    with open(chunk_path, "rb") as chunk:
                        apk.write(chunk.read())
                    os.remove(chunk_path)

                if path.getsize(apk_path) != apk_size:
                    notice("Failed to download apk. Retry...", "error")
                    self.download_extract_apk_file(apk_url)
                notice("Combinate files to apk success.")

        Extractor.zip_extractor(
            apk_path, path.join(self.d.temp_dir, "data"), keywords=["bin/Data"]
        )

    def get_resource_manifest(self, server_info: dict) -> Resource:
        """Get CN manifest."""
        resources = CNResource()
        base_url = server_info["AddressablesCatalogUrlRoots"][0] + "/"

        table_url = f"Manifest/TableBundles/{server_info['TableVersion']}/TableManifest"
        media_url = (
            f"Manifest/MediaResources/{server_info['MediaVersion']}/MediaManifest"
        )
        bundle_url = f"AssetBundles/Catalog/{server_info['ResourceVersion']}/Android/bundleDownloadInfo.json"

        resources.set_url_link(
            base_url,
            "AssetBundles/Android/",
            "pool/MediaResources/",
            "pool/TableBundles/",
        )
        try:

            table_data: requests.Response = self.d.file_downloader(
                urljoin(base_url, table_url), True, self.d.headers
            )

            media_data: requests.Response = self.d.file_downloader(
                urljoin(base_url, media_url), True, self.d.headers
            )

            bundle_data: requests.Response = self.d.file_downloader(
                urljoin(base_url, bundle_url), True, self.d.headers
            )

            if table_data and media_data:
                CNCatalogDecoder.decode_to_manifest(
                    table_data.content, resources, "table"
                )
                CNCatalogDecoder.decode_to_manifest(
                    media_data.content, resources, "media"
                )
            else:
                notice(
                    "Failed to fetch table or media catalog. Retry may solve the issue.",
                    "error",
                )

            if bundle_data.headers.get("Content-Type") == "application/json":
                CNCatalogDecoder.decode_to_manifest(
                    bundle_data.content, resources, "bundle"
                )
            else:
                notice(
                    "Failed to fetch bundle catalog. Retry may solve the issue.",
                    "error",
                )

            if not resources:
                raise FileNotFoundError("Cannot pull the manifest.")
        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {e}."
            ) from e

        return resources.to_resource()

    def get_server_info(self) -> dict:
        """Get CN server info. CN server using permenant server url."""
        if (
            server_info := self.d.file_downloader(
                self.urls["info"],
                True,
                {"APP-VER": self.d.version, "PLATFORM-ID": "1", "CHANNEL-ID": "2"},
            )
        ) == False:
            raise LookupError("Cannot get server url from info api.")
        server_url: requests.Response = server_info
        return server_url.json()

    def get_apk_url(self, server: Literal["official", "bili"] = "official") -> str:
        """CN server have official server and bilibili server. Bili is reserved."""
        apk_url = ""
        if server == "bili":
            bili_link: requests.Response = self.d.file_downloader(
                self.urls["bili"], True, self.d.headers
            )
            return bili_link.json()["android_download_link"]
        response: requests.Response = self.d.file_downloader(
            self.urls["home"],
            True,
            self.d.headers,
        )
        js_match = re.search(
            r'<script[^>]+type="module"[^>]+crossorigin[^>]+src="([^"]+)"[^>]*>',
            response.text,
        )
        if not js_match:
            raise LookupError(
                "Could not find the version file in the HTML response. Retrying may resolve the issue."
            )
        js_response: requests.Response = self.d.file_downloader(
            js_match.group(1), True, self.d.headers
        )
        apk_match = re.search(r'http[s]?://[^\s"<>]+?\.apk', js_response.text)
        apk_url = apk_match.group() if apk_match else ""
        if not js_match:
            raise LookupError(
                "Could not find the version file in the HTML response. Retrying may resolve the issue."
            )
        return apk_url

    def get_latest_version(self) -> str:
        """Get the latest version number from the official website."""
        version = ""
        version_match: re.Match | None = None
        response: requests.Response = self.d.file_downloader(
            self.urls["version"], True, self.d.headers
        )

        version_match = re.search(r"(\d+\.\d+\.\d+)", response.text)
        if version_match:
            version = version_match.group(1)
        elif not version:
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )
        return version


class GLServer:
    def __init__(self, downloader: Downloader) -> None:
        self.d = downloader
        self.urls = {
            "gl_uptodown": "https://blue-archive-global.en.uptodown.com/android",
            "gl": "https://api-pub.nexon.com/patch/v1.1/version-check",
        }

    def get_latest_version(self) -> str:
        """Fetch the latest version from Uptodown."""
        version = ""
        version_match: re.Match | None = None

        response = requests.get(
            self.urls["gl_uptodown"],
            headers=self.d.headers,
            proxies=self.d.proxy,
            timeout=10,
        )
        version_match = re.search(r"(\d+\.\d+\.\d+)", response.text)

        if version_match:
            version = version_match.group(1)
        elif not version:
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )
        return version


class JPServer:
    def __init__(self, downloader: Downloader) -> None:
        self.d = downloader
        self.urls = {
            "jp_info": "https://prod-noticeindex.bluearchiveyostar.com/prod/index.json",
            "apkpure": "https://d.apkpure.com/b/XAPK/com.YostarJP.BlueArchive?nc=arm64-v8a&sv=24",
        }

    def main(self) -> Resource:
        """Main entry of JPServer."""
        version = self.d.version
        if not version:
            notice("Version not specified. Automatically fetching latest...")
            version = self.d.version = self.get_latest_version()
        notice(f"Current resource version: {version}")
        apk_url = self.get_apk_url(version)
        self.download_extract_apk_file(apk_url)
        server_url = self.get_server_url()
        print("Pulling manifest...")
        resources = self.get_resource_manifest(server_url)
        print(f"Manifest: {resources}.")
        return resources

    def download_extract_apk_file(self, apk_url: str):
        """Download and extract the APK file."""
        print("Download APK to retrieve server URL...")
        data = create_scraper().get(apk_url, stream=True, proxies=self.d.proxy)
        apk_path = path.join(
            self.d.temp_dir,
            data.headers["Content-Disposition"]
            .rsplit('"', 2)[-2]
            .encode("ISO8859-1")
            .decode(),
        )
        apk_size = int(data.headers.get("Content-Length", 0))

        if not (path.exists(apk_path) and path.getsize(apk_path) == apk_size):
            with ProgressBar(apk_size, "Downloading APK...", "MB", 1048576) as bar:
                bar.item_text(apk_path.split("/")[-1])
                with open(apk_path, "wb") as apk:
                    for chunck in data.iter_content(chunk_size=4096):
                        apk.write(chunck)
                        bar.increase(len(chunck))

        apk_files = Extractor.zip_extractor(
            apk_path, path.join(self.d.temp_dir), keywords=[".apk"]
        )

        Extractor.zip_extractor(
            apk_files,
            path.join(self.d.temp_dir, "data"),
            keywords=["bin/Data"],
            zip_dir=self.d.temp_dir,
        )

    def get_apk_url(self, version: str) -> str:
        """Retrieve the link to download the APK."""
        return self.urls["apkpure"] + f"&versionCode={version.split('.')[-1]}"

    def get_latest_version(self) -> str:
        """Obtain the version number from the notification link."""
        response: requests.Response = self.d.file_downloader(
            self.urls["jp_info"], True, self.d.headers
        )
        version: str = response.json().get("LatestClientVersion", "")
        if not version:
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )
        return version

    def get_resource_manifest(self, server_url: str) -> Resource:
        """JP server use different API for each version, and media and table files are encrypted."""
        resources = JPResource()
        try:
            api: requests.Response = self.d.file_downloader(
                server_url, True, self.d.headers
            )

            base_url = (
                api.json()["ConnectionGroups"][0]["OverrideConnectionGroups"][-1][
                    "AddressablesCatalogUrlRoot"
                ]
                + "/"
            )

            resources.set_url_link(
                base_url, "Android/", "MediaResources/", "TableBundles/"
            )

            table_data: requests.Response = self.d.file_downloader(
                urljoin(resources.table_url, "TableCatalog.bytes"),
                True,
                self.d.headers,
            )

            media_data: requests.Response = self.d.file_downloader(
                urljoin(resources.media_url, "MediaCatalog.bytes"),
                True,
                self.d.headers,
            )

            bundle_data: requests.Response = self.d.file_downloader(
                urljoin(resources.bundle_url, "bundleDownloadInfo.json"),
                True,
                self.d.headers,
            )

            if (
                table_data.headers.get("Content-Type") == "binary/octet-stream"
                and media_data.headers.get("Content-Type") == "binary/octet-stream"
            ):
                JPCatalogDecoder.decode_to_manifest(
                    table_data.content, resources, "table"
                )
                JPCatalogDecoder.decode_to_manifest(
                    media_data.content, resources, "media"
                )
            else:
                notice(
                    f"Failed to fetch table or media catalog because table is {table_data.reason} and media is {media_data.reason}. Retry may solve the issue.",
                    "error",
                )

            if bundle_data.headers.get("Content-Type") == "application/json":
                bundle_catalog = bundle_data.json()["BundleFiles"]
                for bundle in bundle_catalog:
                    resources.add_bundle_resource(
                        bundle["Name"],
                        bundle["Size"],
                        bundle["Crc"],
                        bundle["IsPrologue"],
                        bundle["IsSplitDownload"],
                    )
            else:
                notice(
                    f"Failed to fetch bundle catalog because {bundle_data.reason}. Retry may solve the issue.",
                    "error",
                )

            if not resources:
                raise FileNotFoundError("Cannot pull the manifest.")
        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {e}."
            ) from e
        return resources.to_resource()

    def get_server_url(self) -> str:
        """Decrypt the server version from the game's binary files."""
        print("Retrieving game info...")
        url = version = ""
        for dir, _, files in os.walk(
            path.join(self.d.temp_dir, "data", "assets", "bin", "Data")
        ):
            for file in files:
                url_obj = Extractor.filter_unity_pack(
                    path.join(dir, file),
                    ["TextAsset"],
                    ["GameMainConfig"],
                    True,
                )
                version_obj = Extractor.filter_unity_pack(
                    path.join(dir, file), ["PlayerSettings"]
                )
                if url_obj:
                    url = Extractor.decode_server_url(url_obj[0].read().script)
                    notice(f"Get URL successfully: {url}")
                if version_obj:
                    ver = re.search(rb"\d+?\.\d+?\.\d+", version_obj[0].get_raw_data())
                    version = ver.group(0).decode() if ver else "unavailable"
                    print(f"The apk version is {version}.")

        if not url:
            raise LookupError("Cannot find server url from apk.")
        if version and version != self.d.version:
            notice("Server version is different with apk version.")
        elif not version:
            notice("Cannot retrieve apk version data.", "error")
        return url


if __name__ == "__main__":
    user_config = args
    if user_config.region == "gl":
        raise NotImplementedError(
            "Global server is not support in this time. Add soon."
        )
    downloader = Downloader(user_config)
    downloader.main()
