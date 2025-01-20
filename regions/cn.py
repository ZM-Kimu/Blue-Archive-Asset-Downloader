import os
import re
from os import path
from threading import Thread
from typing import Literal
from urllib.parse import urljoin

from cloudscraper import create_scraper

from lib.console import ProgressBar, notice, print
from lib.downloader import FileDownloader
from resource_extractor import CNCatalogDecoder, Extractor
from utils import util
from utils.config import Config
from utils.resource_structure import CNResource, Resource


class CNServer:
    def __init__(self) -> None:

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
                    util.create_thread(
                        FileDownloader(
                            apk_url, headers=header, enable_progress=True
                        ).save_file,
                        threads,
                        output,
                    )

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

        Extractor.extract_zip(
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
