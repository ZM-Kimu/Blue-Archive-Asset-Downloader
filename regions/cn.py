import json
import os
import re
from io import BytesIO
from os import path
from typing import Literal
from urllib.parse import urljoin

from lib.console import ProgressBar, notice, print
from lib.downloader import FileDownloader
from lib.structure import CNResource, Resource
from utils.config import Config
from utils.util import TaskManager, ZipUtils


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
        apk_path = self.download_apk_file(apk_url)
        self.extract_apk_file(apk_path)
        server_info = self.get_server_info()

        print("Pulling catalog...")
        resources = self.get_resource_manifest(server_info)
        notice(f"Catalog: {resources}.")
        return resources

    def download_apk_worker(self, task_manager: TaskManager, url: str) -> None:
        """Worker to download apk."""
        task = task_manager.tasks.get()
        FileDownloader(url, headers=task["header"], enable_progress=True).save_file(
            task["path"]
        )
        task_manager.tasks.task_done()

    def download_apk_file(self, apk_url: str) -> str:
        """The CN APK might include special files."""
        print("Download APK to get table and media files...")

        apk_size = 0
        if apk_head := FileDownloader(
            apk_url, headers={}, request_method="head", use_cloud_scraper=True
        ).get_response():
            apk_size = int(apk_head.headers.get("Content-Length", 0))

        os.makedirs(Config.temp_dir, exist_ok=True)
        apk_path = path.join(Config.temp_dir, path.split(apk_url)[-1])

        if path.exists(apk_path) and path.getsize(apk_path) == apk_size:
            return apk_path

        # Create multi-thread downloading task. The CN official server might block connect by short time too many access.
        if not apk_size:
            FileDownloader(apk_url).save_file(apk_path)
        else:
            worker_num = 5
            chunk_size = apk_size // worker_num
            parts: list[dict] = []
            for i in range(worker_num):
                start = chunk_size * i
                end = start + chunk_size - 1 if i != worker_num - 1 else apk_size
                output = path.join(Config.temp_dir, f"chunk_{i}.dat")
                header = {"Range": f"bytes={start}-{end}", "User-Agent": "Chrome/122.0"}
                parts.append({"header": header, "path": output})

            with ProgressBar(apk_size, "Downloading APK...", "MB", 1048576):
                with TaskManager(
                    worker_num, worker_num, self.download_apk_worker
                ) as download_apk:
                    download_apk.import_tasks(parts)
                    download_apk.run(apk_url)

            with open(apk_path, "wb") as apk:
                for part in parts:
                    with open(part["path"], "rb") as chunk:
                        apk.write(chunk.read())
                    os.remove(part["path"])

                if path.getsize(apk_path) != apk_size:
                    notice("Failed when download apk. Retry...", "error")
                    self.download_apk_file(apk_url)

        notice("Combinate files to apk success.")
        return apk_path

    def extract_apk_file(self, apk_path: str) -> None:
        """Extract the APK file."""
        ZipUtils.extract_zip(apk_path, Config.temp_dir)

    def get_apk_url(self, server: Literal["official", "bili"] = "official") -> str:
        """CN server have official server and bilibili server. Bili is reserved."""
        try:
            if server == "bili" and (
                bili_link := FileDownloader(self.urls["bili"]).get_response()
            ):
                return bili_link.json()["data"]["android_download_link"]

            if not (response := FileDownloader(self.urls["home"]).get_response()):
                raise LookupError

            if not (
                js_match := re.search(
                    r'<script[^>]+type="module"[^>]+crossorigin[^>]+src="([^"]+)"[^>]*>',
                    response.text,
                )
            ):
                raise LookupError

            if js_response := FileDownloader(js_match.group(1)).get_response():
                if apk_match := re.search(
                    r'http[s]?://[^\s"<>]+?\.apk', js_response.text
                ):
                    return apk_match.group()

            raise LookupError
        except Exception as e:
            if server == "bili":
                raise LookupError(
                    "Could not find the latest version. Retrying may resolve the issue."
                ) from e
            return self.get_apk_url("bili")

    def get_latest_version(self) -> str:
        """Get the latest version number from the official website."""
        version_match: re.Match | None = None
        if response := FileDownloader(self.urls["version"]).get_response():
            version_match = re.search(r"(\d+\.\d+\.\d+)", response.text)
            if version_match:
                version = version_match.group(1)
                return version
        raise LookupError(
            "Unable to retrieve the version. Retry might solve this issue."
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

            bundle_data = FileDownloader(urljoin(base_url, bundle_url)).get_response()

            if table_data := FileDownloader(urljoin(base_url, table_url)).get_bytes():
                CNCatalogDecoder.decode_to_manifest(table_data, resources, "table")
            else:
                notice(
                    "Failed to fetch table catalog. Retry may solve the issue.",
                    "error",
                )

            if media_data := FileDownloader(urljoin(base_url, media_url)).get_bytes():
                CNCatalogDecoder.decode_to_manifest(media_data, resources, "media")
            else:
                notice(
                    "Failed to fetch media catalog. Retry may solve the issue.",
                    "error",
                )
            if (
                bundle_data := FileDownloader(
                    urljoin(base_url, bundle_url)
                ).get_response()
            ) and bundle_data.headers.get("Content-Type") == "application/json":
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

            return resources.to_resource()

        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {e}."
            ) from e

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


class CNCatalogDecoder:
    media_types = {1: "ogg", 2: "mp4", 3: "jpg", 4: "png", 5: "acb", 6: "awb"}

    @staticmethod
    def decode_to_manifest(
        raw_data: bytes,
        container: CNResource,
        type: Literal["bundle", "table", "media"],
    ) -> dict[str, object]:
        """Used to decode bytes file to readable data structure. Data will return decoded and add to container.

        Args:
            raw_data (bytes): Binary data.
            container (CNResource): Container to storage manifest.
            type (Literal[&quot;table&quot;, &quot;media&quot;]): Data type.

        Returns:
            dict([str, object]): Manifest list.
        """
        manifest: dict[str, object] = {}
        data = BytesIO(raw_data)

        if type == "bundle":
            bundle_data = json.loads(raw_data)
            for item in bundle_data["BundleFiles"]:
                CNCatalogDecoder.__decode_bundle_manifest(item, container)

        if type == "media":
            while item := data.readline():
                key, obj = CNCatalogDecoder.__decode_media_manifest(item, container)
                manifest[key] = obj

        if type == "table":
            table_data: dict = json.loads(raw_data).get("Table", {})
            for file, item in table_data.items():
                key, obj = CNCatalogDecoder.__decode_table_manifest(
                    file, item, container
                )
                manifest[key] = obj

        return manifest

    @classmethod
    def __decode_bundle_manifest(
        cls, data: dict, container: CNResource
    ) -> tuple[str, dict[str, object]]:
        container.add_bundle_resource(
            data["Name"],
            data["Size"],
            data["Crc"],
            data["IsPrologue"],
            data["IsSplitDownload"],
        )

        return data["Name"], {
            "name": data["Name"],
            "size": data["Size"],
            "md5": data["Crc"],
            "is_prologue": data["IsPrologue"],
            "is_split_download": data["IsSplitDownload"],
        }

    @classmethod
    def __decode_media_manifest(
        cls, data: bytes, container: CNResource
    ) -> tuple[str, dict[str, object]]:
        path, md5, media_type_str, size_str, _ = data.decode().split(",")

        media_type = int(media_type_str)
        size = int(size_str)

        if media_type in cls.media_types:
            path += f".{cls.media_types[media_type]}"
        else:
            notice(f"Unidentifiable media type {media_type}.")
        file_url_path = md5[:2] + "/" + md5

        container.add_media_resource(
            file_url_path, path, cls.media_types[media_type], size, md5
        )

        file_path, file_name = os.path.split(path)
        return file_url_path, {
            "path": file_path,
            "file_name": file_name,
            "type": media_type,
            "bytes": size,
            "md5": md5,
        }

    @classmethod
    def __decode_table_manifest(
        cls, key: str, item: dict, container: CNResource
    ) -> tuple[str, dict[str, object]]:

        path: str = item["Name"]
        md5: str = item["Crc"]
        size: int = item["Size"]
        includes: list = item["Includes"]

        size = int(size)
        file_url_path = md5[:2] + "/" + md5

        container.add_table_resource(file_url_path, path, size, md5, includes)

        return key, {
            "name": item["Name"],
            "size": item["Size"],
            "crc": item["Crc"],
            "includes": item["Includes"],
        }
