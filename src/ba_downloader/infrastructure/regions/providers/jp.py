import base64
import json
import os
import re
import struct
from dataclasses import dataclass
from io import BytesIO
from os import path
from typing import Any, Literal
from urllib.parse import urljoin

from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.infrastructure.apk import download_package_file, extract_xapk_file
from ba_downloader.domain.models.resource import JPResource, Resource
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.unity import UnityAssetReader
from ba_downloader.shared.crypto.encryption import convert_string, create_key


@dataclass(frozen=True)
class APKPackageInfo:
    version: str
    download_url: str


class JPServer:
    PUREAPK_VERSION_URL = (
        "https://api.pureapk.com/m/v3/cms/app_version"
        "?hl=en-US&package_name=com.YostarJP.BlueArchive"
    )
    PUREAPK_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        "x-sv": "29",
        "x-abis": "arm64-v8a,armeabi-v7a,armeabi",
        "x-gp": "1",
    }
    PUREAPK_PACKAGE_PATTERN = re.compile(
        rb"com\.YostarJP\.BlueArchive.*?"
        rb"(\d+\.\d+\.\d+).*?"
        rb"("
        rb"https://download\.pureapk\.com/b/XAPK/"
        rb"[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%_-]+"
        rb")",
        re.S,
    )
    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def apk_extract_folder(self, context: RuntimeContext) -> str:
        return path.join(context.temp_dir, "Data")

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        """Main entry of JPServer."""
        if context.version:
            self.logger.warn("Specifying a version is not allowed with JPServer.")

        self.logger.warn("Automatically fetching latest package info...")
        package_info = self.get_latest_package_info()
        version = package_info.version
        resolved_context = context.with_updates(version=version)
        self.logger.warn(f"Current resource version: {version}")

        apk_path = self.download_apk_file(package_info.download_url, resolved_context)
        self.extract_apk_file(apk_path, resolved_context)
        server_url = self.get_server_url(resolved_context)

        self.logger.info("Pulling catalog...")
        resources = self.get_resource_manifest(server_url)
        self.logger.warn(f"Catalog: {resources}.")
        return RegionCatalogResult(resources=resources, context=resolved_context)

    def download_apk_file(self, apk_url: str, context: RuntimeContext) -> str:
        """Download the APK file."""
        self.logger.info("Downloading APK to retrieve server URL...")
        return download_package_file(
            self.http_client,
            self.logger,
            apk_url,
            context.temp_dir,
        )

    def extract_apk_file(self, apk_path: str, context: RuntimeContext) -> None:
        """Extract the XAPK file."""
        extract_xapk_file(
            apk_path,
            self.apk_extract_folder(context),
            context.temp_dir,
        )

    def deprecated_get_apk_url(self, version: str) -> str:
        """Retrieve the link to download the APK."""
        return (
            "https://d.apkpure.com/b/XAPK/com.YostarJP.BlueArchive"
            f"?versionCode={version.split('.')[-1]}&nc=arm64-v8a&sv=24"
        )

    @classmethod
    def parse_package_info(cls, payload: bytes) -> APKPackageInfo:
        """Parse the latest JP package info from the PureAPK metadata response."""
        matches = cls.PUREAPK_PACKAGE_PATTERN.findall(payload)
        if not matches:
            raise LookupError("Unable to parse latest JP package info from PureAPK.")

        candidates = [
            APKPackageInfo(
                version=version.decode("utf-8"),
                download_url=download_url.decode("ascii"),
            )
            for version, download_url in matches
        ]

        return max(candidates, key=lambda item: tuple(int(part) for part in item.version.split(".")))

    def get_latest_package_info(self) -> APKPackageInfo:
        """Fetch the latest JP package metadata from PureAPK."""
        payload = self.http_client.request(
            "GET",
            self.PUREAPK_VERSION_URL,
            headers=self.PUREAPK_HEADERS,
        ).content

        return self.parse_package_info(payload)

    def get_latest_version(self) -> str:
        """Obtain the latest JP package version."""
        return self.get_latest_package_info().version

    def get_resource_manifest(self, server_url: str) -> Resource:
        """JP server use different API for each version, and media and table files are encrypted."""
        resources = JPResource()
        try:
            api = self.http_client.request("GET", server_url)

            base_url = (
                api.json()["ConnectionGroups"][0]["OverrideConnectionGroups"][-1][
                    "AddressablesCatalogUrlRoot"
                ]
                + "/"
            )

            resources.set_url_link(
                base_url, "Android/", "MediaResources/", "TableBundles/"
            )

            if table_data := self.http_client.request(
                "GET",
                urljoin(resources.table_url, "TableCatalog.bytes"),
            ).content:
                JPCatalogDecoder.decode_to_manifest(table_data, resources, "table")
            else:
                self.logger.error(
                    "Failed to fetch table catalog. Retry may solve this issue.",
                )

            if media_data := self.http_client.request(
                "GET",
                urljoin(resources.media_url, "Catalog/MediaCatalog.bytes"),
            ).content:
                JPCatalogDecoder.decode_to_manifest(media_data, resources, "media")
            else:
                self.logger.error(
                    "Failed to fetch media catalog. Retry may solve this issue.",
                )

            bundle_data = self.http_client.request(
                "GET",
                urljoin(resources.bundle_url, "bundleDownloadInfo.json"),
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
                self.logger.error(
                    "Failed to fetch bundle catalog. Retry may solve this issue.",
                )

            if not resources:
                raise FileNotFoundError("Cannot pull the manifest.")

            return resources.to_resource()

        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {e}."
            ) from e

    def __decode_server_url(self, data: bytes) -> str:
        """
        Decodes the server URL from the given data.

        Args:
            data (bytes): Binary data to decode.

        Returns:
            str: Decoded server URL.
        """
        ciphers = {
            "ServerInfoDataUrl": "X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==",
            "DefaultConnectionGroup": "tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=",
            "SkipTutorial": "8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI",
            "Language": "wL4EWsDv8QX5vgRaye/zBQ==",
        }
        b64_data = base64.b64encode(data).decode()
        json_str = convert_string(b64_data, create_key("GameMainConfig"))
        obj = json.loads(json_str)
        encrypted_url = obj[ciphers["ServerInfoDataUrl"]]
        url = convert_string(encrypted_url, create_key("ServerInfoDataUrl"))
        return url

    def get_server_url(self, context: RuntimeContext) -> str:
        """Decrypt the server version from the game's binary files."""
        self.logger.info("Retrieving game info...")
        url = version = ""
        for dir, _, files in os.walk(
            path.join(self.apk_extract_folder(context), "assets", "bin", "Data")
        ):
            for file in files:
                if url_obj := UnityAssetReader.search_objects(
                    path.join(dir, file), ["TextAsset"], ["GameMainConfig"], True
                ):
                    url = self.__decode_server_url(url_obj[0].read().m_Script.encode("utf-8", "surrogateescape"))  # type: ignore
                    self.logger.warn(f"Get URL successfully: {url}")
                if version_obj := UnityAssetReader.search_objects(
                    path.join(dir, file), ["PlayerSettings"]
                ):
                    try:
                        version = version_obj[0].read().bundleVersion  # type: ignore
                    except Exception:
                        version = "unavailable"
                    self.logger.info(f"The apk version is {version}.")

                if url and version:
                    break

        if not url:
            raise LookupError("Cannot find server url from apk.")
        if version and version != context.version:
            self.logger.warn("Server version is different with apk version.")
        elif not version:
            self.logger.warn("Cannot retrieve apk version data.")
        return url


I8: str = "b"
I32: str = "i"
I64: str = "q"
BOOL: str = "?"


class JPCatalogDecoder:

    class Reader:
        def __init__(self, initial_bytes) -> None:
            self.io = BytesIO(initial_bytes)

        def read(self, fmt: str) -> Any:
            """Use struct read bytes by giving a format char."""
            return struct.unpack(fmt, self.io.read(struct.calcsize(fmt)))[0]

        def read_string(self) -> str:
            """Read string."""
            return self.io.read(self.read(I32)).decode(
                encoding="utf-8", errors="replace"
            )

        def read_table_includes(self) -> list[str]:
            """Read talbe inculdes."""
            size = self.read(I32)
            if size == -1:
                return []
            self.read(I32)
            includes = []
            for i in range(size):
                includes.append(self.read_string())
                if i != size - 1:
                    self.read(I32)
            return includes

    @staticmethod
    def decode_to_manifest(
        raw_data: bytes, container: JPResource, type: Literal["table", "media"]
    ) -> dict[str, object]:
        """Used to decode bytes file to readable data structure. Data will return decoded and add to container.

        Args:
            raw_data (bytes): Binary data.
            container (JPResource): Container to storage manifest.
            type (Literal[&quot;table&quot;, &quot;media&quot;]): Data type.

        Returns:
            dict([str, object]): Manifest list.
        """
        data = JPCatalogDecoder.Reader(raw_data)

        manifest: dict[str, object] = {}

        data.read(I8)
        item_num = data.read(I32)

        for _ in range(item_num):
            if type == "media":
                key, obj = JPCatalogDecoder.__decode_media_manifest(data, container)
            else:
                key, obj = JPCatalogDecoder.__decode_table_manifest(data, container)
            manifest[key] = obj
        return manifest

    @classmethod
    def __decode_media_manifest(
        cls, data: Reader, container: JPResource
    ) -> tuple[str, dict[str, object]]:
        data.read(I32)
        key = data.read_string()
        data.read(I8)
        data.read(I32)
        path = data.read_string()
        data.read(I32)
        file_name = data.read_string()
        bytes = data.read(I64)
        crc = data.read(I64)
        is_prologue = data.read(BOOL)
        is_split_download = data.read(BOOL)
        media_type = data.read(I32)

        path = path.replace("\\", "/")
        container.add_media_resource(
            key, path, file_name, media_type, bytes, crc, is_prologue, is_split_download
        )

        return key, {
            "path": path,
            "file_name": file_name,
            "type": media_type,
            "bytes": bytes,
            "crc": crc,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
        }

    @classmethod
    def __decode_table_manifest(
        cls, data: Reader, container: JPResource
    ) -> tuple[str, dict[str, object]]:
        data.read(I32)
        key = data.read_string()
        data.read(I8)
        data.read(I32)
        name = data.read_string()
        size = data.read(I64)
        crc = data.read(I64)
        is_in_build = data.read(BOOL)
        is_changed = data.read(BOOL)
        is_prologue = data.read(BOOL)
        is_split_download = data.read(BOOL)
        includes = data.read_table_includes()

        container.add_table_resource(
            key,
            name,
            size,
            crc,
            is_in_build,
            is_changed,
            is_prologue,
            is_split_download,
            includes,
        )

        return key, {
            "name": name,
            "size": size,
            "crc": crc,
            "is_in_build": is_in_build,
            "is_changed": is_changed,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
            "includes": includes,
        }
