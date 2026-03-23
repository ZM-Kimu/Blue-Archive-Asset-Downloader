from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
from io import BytesIO
from os import path
from typing import Literal
from urllib.parse import urljoin
from zipfile import ZipFile

from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.resource import CNResource, Resource
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter


class CNServer:
    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

        self.urls = {
            "home": "https://bluearchive-cn.com/",
            "version": "https://bluearchive-cn.com/api/meta/setup",
            "info": "https://gs-api.bluearchive-cn.com/api/state",
            "bili": "https://line1-h5-pc-api.biligame.com/game/detail/gameinfo?game_base_id=109864",
        }

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        """Main entry for CNServer"""
        if context.version:
            self.logger.warn("Specifying a version is not allowed with CNServer.")

        self.logger.warn("Automatically fetching latest version...")
        version = self.get_latest_version()
        resolved_context = context.with_updates(version=version)
        self.logger.warn(f"Current resource version: {version}")

        apk_url = self.get_apk_url()
        apk_path = self.download_apk_file(apk_url, resolved_context)
        self.extract_apk_file(apk_path, resolved_context)
        server_info = self.get_server_info(resolved_context)

        self.logger.info("Pulling catalog...")
        resources = self.get_resource_manifest(server_info)
        self.logger.warn(f"Catalog: {resources}.")
        return RegionCatalogResult(resources=resources, context=resolved_context)

    def _download_chunk(self, url: str, header: dict[str, str], target_path: str) -> str:
        self.http_client.download_to_file(url, target_path, headers=header)
        return target_path

    def download_apk_file(self, apk_url: str, context: RuntimeContext) -> str:
        """The CN APK might include special files."""
        self.logger.info("Downloading APK to get table and media files...")

        apk_head = self.http_client.request("HEAD", apk_url)
        apk_size = int(apk_head.headers.get("Content-Length", "0") or 0)

        os.makedirs(context.temp_dir, exist_ok=True)
        apk_path = path.join(context.temp_dir, path.split(apk_url)[-1])

        if path.exists(apk_path) and path.getsize(apk_path) == apk_size:
            return apk_path

        # Create multi-thread downloading task. The CN official server might block connect by short time too many access.
        if not apk_size:
            self.http_client.download_to_file(apk_url, apk_path)
        else:
            worker_num = 5
            chunk_size = apk_size // worker_num
            parts: list[dict] = []
            for i in range(worker_num):
                start = chunk_size * i
                end = start + chunk_size - 1 if i != worker_num - 1 else apk_size
                output = path.join(context.temp_dir, f"chunk_{i}.dat")
                header = {"Range": f"bytes={start}-{end}", "User-Agent": "Chrome/122.0"}
                parts.append({"header": header, "path": output})

            progress = RichProgressReporter(apk_size, "Downloading APK...", download_mode=True)
            with progress, ThreadPoolExecutor(max_workers=worker_num) as executor:
                futures = [
                    executor.submit(
                        self._download_chunk, apk_url, part["header"], part["path"]
                    )
                    for part in parts
                ]
                for future in as_completed(futures):
                    chunk_path = future.result()
                    progress.advance(path.getsize(chunk_path))

            with open(apk_path, "wb") as apk:
                for part in parts:
                    with open(part["path"], "rb") as chunk:
                        apk.write(chunk.read())
                    os.remove(part["path"])

                if path.getsize(apk_path) != apk_size:
                    raise LookupError("Failed to download apk correctly. Retry may solve this issue.")

        self.logger.warn("Combined files to apk successfully.")
        return apk_path

    def extract_apk_file(self, apk_path: str, context: RuntimeContext) -> None:
        """Extract the APK file."""
        with ZipFile(apk_path, "r") as apk_zip:
            apk_zip.extractall(context.temp_dir)

    def get_apk_url(self, server: Literal["official", "bili"] = "official") -> str:
        """CN server have official server and bilibili server. Bili is reserved."""
        try:
            if server == "bili" and (
                bili_link := self.http_client.request("GET", self.urls["bili"])
            ):
                return bili_link.json()["data"]["android_download_link"]

            response = self.http_client.request("GET", self.urls["home"])

            if not (
                js_match := re.search(
                    r'<script[^>]+type="module"[^>]+crossorigin[^>]+src="([^"]+)"[^>]*>',
                    response.text,
                )
            ):
                raise LookupError

            if js_response := self.http_client.request("GET", js_match.group(1)):
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
        response = self.http_client.request("GET", self.urls["version"])
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

            if table_data := self.http_client.request(
                "GET", urljoin(base_url, table_url)
            ).content:
                CNCatalogDecoder.decode_to_manifest(table_data, resources, "table")
            else:
                self.logger.error(
                    "Failed to fetch table catalog. Retry may solve the issue.",
                )

            if media_data := self.http_client.request(
                "GET", urljoin(base_url, media_url)
            ).content:
                CNCatalogDecoder.decode_to_manifest(media_data, resources, "media")
            else:
                self.logger.error(
                    "Failed to fetch media catalog. Retry may solve the issue.",
                )
            bundle_data = self.http_client.request("GET", urljoin(base_url, bundle_url))
            if bundle_data.headers.get("Content-Type") == "application/json":
                CNCatalogDecoder.decode_to_manifest(
                    bundle_data.content, resources, "bundle"
                )
            else:
                self.logger.error(
                    "Failed to fetch bundle catalog. Retry may solve the issue.",
                )

            if not resources:
                raise FileNotFoundError("Cannot pull the manifest.")

            return resources.to_resource()

        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {e}."
            ) from e

    def get_server_info(self, context: RuntimeContext) -> dict:
        """Get CN server info. CN server using permenant server url."""
        server_info = self.http_client.request(
            "GET",
            self.urls["info"],
            headers={
                "APP-VER": context.version,
                "PLATFORM-ID": "1",
                "CHANNEL-ID": "2",
            },
        )
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
            # Unknown media types are retained as-is.
            pass
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

