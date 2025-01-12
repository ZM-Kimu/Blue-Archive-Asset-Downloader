import concurrent
import concurrent.futures
import os
import re
from concurrent.futures import ThreadPoolExecutor
from os import path
from queue import Empty, Queue
from threading import Lock, Thread
from time import sleep
from typing import Literal
from urllib.parse import urljoin

from cloudscraper import create_scraper

from resource_extractor import CNCatalogDecoder, Extractor, JPCatalogDecoder
from utils import utils
from utils.config import Config
from utils.console import ProgressBar, bar_increase, bar_text, notice, print
from utils.downloader import FileDownloader
from utils.resource_structure import CNResource, GLResource, JPResource, Resource

# TODO:When CN&JP both in Temp will cuz URL extraction conflict.


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
            region = CNServer(self)
        elif "gl" in Config.region:
            region = GLServer(self)
        elif "jp" in Config.region:
            region = JPServer(self)

        if not region:
            raise ValueError("The region argument does not match one of cn/gl/jp.")

        resource = region.main()
        resource_to_download = self.get_changed_file(resource)
        # self.start_download_resource_task(resource_to_download)
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
                        verified = utils.calculate_crc(asset_path) == res["checksum"]
                    elif res["check_type"] == "md5":
                        verified = utils.calculate_md5(asset_path) == res["checksum"]
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
                    "Download has been canceled. Waiting for thread complete.", "error"
                )
                self.stop_task = True
                executor.shutdown(cancel_futures=True)
            finally:
                for future in futures:
                    future.result()

        executor.shutdown(wait=True)

        if failed_res:
            notice(f"Retry for {len(failed_res)} failed files.")
            self.start_download_resource_task(failed_res, __retries + 1)

        if not (self.stop_task or failed_res):
            notice("All files have been download to your computer.")


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
        if Config.version:
            notice("Specifying a version is not allowed with CNServer.")

        notice("Automatically fetching latest version...")
        version = Config.version = self.get_latest_version()
        notice(f"Current resource version: {version}")

        apk_url = self.get_apk_url()
        self.download_extract_apk_file(apk_url)
        server_info = self.get_server_info()

        print("Pulling manifest...")
        resources = self.get_resource_manifest(server_info)
        notice(f"Manifest: {resources}.")
        return resources

    def download_extract_apk_file(self, apk_url: str) -> None:
        """The CN APK might include special files."""
        print("Download APK to get table and media files...")
        apk_size = int(
            create_scraper()
            .head(apk_url, proxies=Config.proxy, timeout=10)
            .headers.get("Content-Length", 0)
        )
        if apk_size == 0:
            notice("Unable to retrieve package size. Using bilibili.", "error")
            self.download_extract_apk_file(self.get_apk_url("bili"))
            return

        threads: list[Thread] = []
        os.makedirs(Config.temp_dir, exist_ok=True)
        apk_path = path.join(Config.temp_dir, path.split(apk_url)[-1])

        if not (path.exists(apk_path) and path.getsize(apk_path) == apk_size):
            # Create multi-thread downloading task. The CN official server might block connect by short time too many access.
            thread_num = 5
            chunk_size = apk_size // thread_num
            with ProgressBar(apk_size, "Downloading APK...", "MB", 1048576):
                for i in range(thread_num):
                    start = chunk_size * i
                    end = start + chunk_size - 1 if i != thread_num - 1 else apk_size
                    output = path.join(Config.temp_dir, f"chunk_{i}.dat")
                    header = {"Range": f"bytes={start}-{end}"}
                    utils.create_thread(
                        FileDownloader(
                            apk_url, headers=header, enable_progress=True
                        ).save_file,
                        threads,
                        output,
                    )

                # self.d.set_progress_bar_message(apk_url.rsplit("/", 1)[-1])
                for thread in threads:
                    thread.join()

            with open(apk_path, "wb") as apk:
                for i in range(thread_num):
                    chunk_path = path.join(Config.temp_dir, f"chunk_{i}.dat")
                    with open(chunk_path, "rb") as chunk:
                        apk.write(chunk.read())
                    os.remove(chunk_path)

                if path.getsize(apk_path) != apk_size:
                    notice("Failed to download apk. Retry...", "error")
                    self.download_extract_apk_file(apk_url)
                notice("Combinate files to apk success.")

        Extractor.zip_extractor(
            apk_path, path.join(Config.temp_dir, "data"), keywords=["bin/Data"]
        )

    def get_apk_url(self, server: Literal["official", "bili"] = "official") -> str:
        """CN server have official server and bilibili server. Bili is reserved."""
        apk_url = ""
        if server == "bili":
            bili_link = FileDownloader(self.urls["bili"]).get_response()
            return bili_link.json()["android_download_link"]
        response = FileDownloader(self.urls["home"]).get_response()
        js_match = re.search(
            r'<script[^>]+type="module"[^>]+crossorigin[^>]+src="([^"]+)"[^>]*>',
            response.text,
        )
        if not js_match:
            raise LookupError(
                "Could not find the version file in the HTML response. Retrying may resolve the issue."
            )
        js_response = FileDownloader(js_match.group(1)).get_response()
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
        response = FileDownloader(self.urls["version"]).get_response()

        version_match = re.search(r"(\d+\.\d+\.\d+)", response.text)
        if version_match:
            version = version_match.group(1)
        elif not version:
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )
        return version

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

            table_data = FileDownloader(urljoin(base_url, table_url)).get_response()

            media_data = FileDownloader(urljoin(base_url, media_url)).get_response()

            bundle_data = FileDownloader(urljoin(base_url, bundle_url)).get_response()

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
            server_info := FileDownloader(
                self.urls["info"],
                headers={
                    "APP-VER": Config.version,
                    "PLATFORM-ID": "1",
                    "CHANNEL-ID": "2",
                },
            ).get_response()
        ) == False:
            raise LookupError("Cannot get server url from info api.")

        return server_info.json()


class GLServer:
    def __init__(self, downloader: Downloader) -> None:
        self.d = downloader
        self.urls = {
            "uptodown": "https://blue-archive-global.en.uptodown.com/android",
            "manifest": "https://api-pub.nexon.com/patch/v1.1/version-check",
        }

    def main(self) -> Resource:
        """Main entry of GLServer."""
        version = Config.version
        if not version:
            notice("Version not specified. Automatically fetching latest...")
            version = Config.version = self.get_latest_version()
        notice(f"Current resource version: {version}")
        server_url = self.get_server_url(version)
        print("Pulling manifest...")
        resources = self.get_resource_manifest(server_url)
        notice(f"Manifest: {resources}.")
        return resources

    def get_latest_version(self) -> str:
        """Fetch the latest version from Uptodown."""
        version_match: re.Match | None = None
        response = FileDownloader(self.urls["uptodown"]).get_response()

        if version_match := re.search(r"(\d+\.\d+\.\d+)", response.text):
            return version_match.group(1)

        if not version_match:
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )
        return ""

    def get_resource_manifest(self, server_url: str) -> Resource:
        """GLServer uses persistent API and allows specifying the version."""
        resources = GLResource()
        try:
            resource_data = FileDownloader(server_url).get_response()

            resources.set_url_link(server_url.rsplit("/", 1)[0] + "/")

            if not (resource := resource_data.json()):
                notice(
                    f"Failed to fetch resource because {resource_data.reason}. Retry may solve the issue.",
                    "error",
                )

            for res in resource.get("resources", []):
                resources.add_resource(
                    res["group"],
                    res["resource_path"],
                    res["resource_size"],
                    res["resource_hash"],
                )

            if not resources:
                raise FileNotFoundError("Cannot pull the manifest.")
        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {e}."
            ) from e
        return resources.to_resource()

    def get_server_url(self, version: str) -> str:
        """Get server url from game API."""
        request_body = {
            "market_game_id": "com.nexon.bluearchive",
            "market_code": "playstore",
            "curr_build_version": version,
            "curr_build_number": version.split(".")[-1],
        }

        server_url = FileDownloader(
            self.urls["manifest"], request_method="post", json=request_body
        ).get_response()

        return server_url.json().get("patch", {}).get("resource_path", "")


class JPServer:
    def __init__(self, downloader: Downloader) -> None:
        self.d = downloader
        self.urls = {
            "info": "https://prod-noticeindex.bluearchiveyostar.com/prod/index.json",
            "uptodown_info": "https://blue-archive.jp.uptodown.com/android",
            "apkpure": "https://d.apkpure.com/b/XAPK/com.YostarJP.BlueArchive?nc=arm64-v8a&sv=24",
        }

    def main(self) -> Resource:
        """Main entry of JPServer."""
        version = Config.version
        if not version:
            notice("Version not specified. Automatically fetching latest...")
            version = Config.version = self.get_latest_version()
        notice(f"Current resource version: {version}")
        apk_url = self.get_apk_url(version)
        self.download_extract_apk_file(apk_url)
        server_url = self.get_server_url()
        print("Pulling manifest...")
        resources = self.get_resource_manifest(server_url)
        notice(f"Manifest: {resources}.")
        return resources

    def download_extract_apk_file(self, apk_url: str):
        """Download and extract the APK file."""
        print("Download APK to retrieve server URL...")
        data = create_scraper().get(apk_url, stream=True, proxies=Config.proxy)
        apk_path = path.join(
            Config.temp_dir,
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
            apk_path, path.join(Config.temp_dir), keywords=[".apk"]
        )

        Extractor.zip_extractor(
            apk_files,
            path.join(Config.temp_dir, "data"),
            keywords=["bin/Data"],
            zip_dir=Config.temp_dir,
        )

    def get_apk_url(self, version: str) -> str:
        """Retrieve the link to download the APK."""
        return self.urls["apkpure"] + f"&versionCode={version.split('.')[-1]}"

    def get_latest_version(self) -> str:
        """Obtain the version number from the notification link."""
        uptodown_version = ""

        info_official = FileDownloader(self.urls["info"]).get_response()

        official_version: str = info_official.json().get("LatestClientVersion", "")

        info_uptodown = FileDownloader(self.urls["uptodown_info"]).get_response()

        uptodown_match = re.search(r"(\d+\.\d+\.\d+)", info_uptodown.text)

        if uptodown_match:
            uptodown_version = uptodown_match.group(1)

        if not (official_version or uptodown_version):
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )

        if (
            official_version
            and uptodown_version
            and official_version != uptodown_version
            and int(uptodown_version.rsplit(".", 1)[-1])
            > int(official_version.rsplit(".", 1)[-1])
        ):
            return uptodown_version

        return official_version

    def get_resource_manifest(self, server_url: str) -> Resource:
        """JP server use different API for each version, and media and table files are encrypted."""
        resources = JPResource()
        try:
            api = FileDownloader(server_url).get_response()

            base_url = (
                api.json()["ConnectionGroups"][0]["OverrideConnectionGroups"][-1][
                    "AddressablesCatalogUrlRoot"
                ]
                + "/"
            )

            resources.set_url_link(
                base_url, "Android/", "MediaResources/", "TableBundles/"
            )

            table_data = FileDownloader(
                urljoin(resources.table_url, "TableCatalog.bytes")
            ).get_response()

            media_data = FileDownloader(
                urljoin(resources.media_url, "MediaCatalog.bytes")
            ).get_response()

            bundle_data = FileDownloader(
                urljoin(resources.bundle_url, "bundleDownloadInfo.json")
            ).get_response()

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
            path.join(Config.temp_dir, "data", "assets", "bin", "Data")
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
        if version and version != Config.version:
            notice("Server version is different with apk version.")
        elif not version:
            notice("Cannot retrieve apk version data.", "error")
        return url


if __name__ == "__main__":
    downloader = Downloader()
    downloader.main()
