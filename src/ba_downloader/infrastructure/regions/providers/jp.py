import base64
import json
import os
import re
import struct
from collections.abc import Callable, Mapping
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
            base_url = self._resolve_catalog_root(api.json())

            resources.set_url_link(
                base_url,
                "Android_PatchPack/",
                "MediaResources/",
                "TableBundles/",
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
                urljoin(resources.bundle_url, "BundlePackingInfo.json"),
            )
            try:
                self._load_bundle_catalog(bundle_data.json(), resources)
            except Exception:
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

    @staticmethod
    def _resolve_catalog_root(addressable_payload: Mapping[str, Any]) -> str:
        connection_groups = addressable_payload.get("ConnectionGroups", [])
        if not connection_groups:
            raise LookupError("ConnectionGroups not found in JP addressables response.")

        override_groups = connection_groups[0].get("OverrideConnectionGroups", [])
        roots = [
            str(group.get("AddressablesCatalogUrlRoot", "")).rstrip("/")
            for group in override_groups
            if group.get("AddressablesCatalogUrlRoot")
        ]

        if len(roots) >= 2:
            return roots[1] + "/"
        if roots:
            return roots[-1] + "/"

        raise LookupError("AddressablesCatalogUrlRoot not found in JP addressables response.")

    @staticmethod
    def _load_bundle_catalog(
        payload: Mapping[str, Any],
        resources: JPResource,
    ) -> None:
        for section_name in ("FullPatchPacks", "UpdatePacks"):
            packs = payload.get(section_name, [])
            if not isinstance(packs, list):
                continue

            for pack in packs:
                if not isinstance(pack, Mapping):
                    continue

                pack_name = str(pack.get("PackName", "")).strip()
                if not pack_name:
                    continue

                bundle_files = [
                    str(bundle.get("Name", "")).strip()
                    for bundle in pack.get("BundleFiles", [])
                    if isinstance(bundle, Mapping) and bundle.get("Name")
                ]
                resources.add_bundle_resource(
                    pack_name,
                    int(pack.get("PackSize", 0) or 0),
                    int(pack.get("Crc", 0) or 0),
                    bool(pack.get("IsPrologue", False)),
                    bool(pack.get("IsSplitDownload", False)),
                    bundle_files,
                )

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


NULL_OBJECT_HEADER = 255
NULL_COLLECTION_HEADER = -1


class JPCatalogDecoder:

    class Reader:
        def __init__(self, initial_bytes: bytes) -> None:
            self.io = BytesIO(initial_bytes)

        def _read_exact(self, size: int) -> bytes:
            data = self.io.read(size)
            if len(data) != size:
                raise EOFError("Unexpected end of MemoryPack stream.")
            return data

        def read_int32(self) -> int:
            return struct.unpack("<i", self._read_exact(4))[0]

        def read_int64(self) -> int:
            return struct.unpack("<q", self._read_exact(8))[0]

        def read_uint8(self) -> int:
            return struct.unpack("<B", self._read_exact(1))[0]

        def read_bool(self) -> bool:
            return struct.unpack("<?", self._read_exact(1))[0]

        def read_object_header(self) -> int | None:
            header = self.read_uint8()
            if header == NULL_OBJECT_HEADER:
                return None
            return header

        def read_collection_header(self) -> int | None:
            length = self.read_int32()
            if length == NULL_COLLECTION_HEADER:
                return None
            return length

        def read_string(self) -> str | None:
            length = self.read_collection_header()
            if length is None:
                return None
            if length == 0:
                return ""
            if length > 0:
                return self._read_exact(length * 2).decode("utf-16-le")

            utf8_length = ~length
            self.read_int32()
            return self._read_exact(utf8_length).decode("utf-8")

        def read_array(
            self,
            item_reader: Callable[["JPCatalogDecoder.Reader"], Any],
        ) -> list[Any]:
            length = self.read_collection_header()
            if length is None:
                return []
            return [item_reader(self) for _ in range(length)]

        def read_string_map(
            self,
            value_reader: Callable[["JPCatalogDecoder.Reader"], dict[str, object]],
        ) -> dict[str, dict[str, object]]:
            length = self.read_collection_header()
            if length is None:
                return {}

            result: dict[str, dict[str, object]] = {}
            for _ in range(length):
                key = self.read_string()
                if key is None:
                    raise ValueError("Encountered null key in MemoryPack map.")
                result[key] = value_reader(self)
            return result

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
        if type == "media":
            return JPCatalogDecoder.__decode_media_catalog(data, container)
        return JPCatalogDecoder.__decode_table_catalog(data, container)

    @classmethod
    def __decode_media_catalog(
        cls,
        data: Reader,
        container: JPResource,
    ) -> dict[str, object]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 1:
            return {}

        manifest = data.read_string_map(cls.__decode_media_manifest)
        for key, obj in manifest.items():
            path = str(obj["path"]).replace("\\", "/")
            container.add_media_resource(
                key,
                path,
                str(obj["file_name"]),
                int(obj["type"]),
                int(obj["bytes"]),
                int(obj["crc"]),
                bool(obj["is_prologue"]),
                bool(obj["is_split_download"]),
            )
            obj["path"] = path
        return manifest

    @classmethod
    def __decode_table_catalog(
        cls,
        data: Reader,
        container: JPResource,
    ) -> dict[str, object]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 1:
            return {}

        manifest = data.read_string_map(cls.__decode_table_manifest)
        if member_count >= 2:
            for key, obj in data.read_string_map(cls.__decode_table_pack_manifest).items():
                manifest[key] = obj

        for key, obj in manifest.items():
            container.add_table_resource(
                key,
                str(obj["name"]),
                int(obj["size"]),
                int(obj["crc"]),
                bool(obj.get("is_in_build", False)),
                bool(obj.get("is_changed", False)),
                bool(obj.get("is_prologue", False)),
                bool(obj.get("is_split_download", False)),
                list(obj.get("includes", [])),
            )
        return manifest

    @classmethod
    def __decode_media_manifest(
        cls,
        data: Reader,
    ) -> dict[str, object]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 7:
            raise ValueError("Malformed JP media catalog entry.")

        path = data.read_string() or ""
        file_name = data.read_string() or ""
        size = data.read_int64()
        crc = data.read_int64()
        is_prologue = data.read_bool()
        is_split_download = data.read_bool()
        media_type = data.read_int32()

        return {
            "path": path,
            "file_name": file_name,
            "type": media_type,
            "bytes": size,
            "crc": crc,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
        }

    @classmethod
    def __decode_table_manifest(
        cls,
        data: Reader,
    ) -> dict[str, object]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 8:
            raise ValueError("Malformed JP table catalog entry.")

        name = data.read_string() or ""
        size = data.read_int64()
        crc = data.read_int64()
        is_in_build = data.read_bool()
        is_changed = data.read_bool()
        is_prologue = data.read_bool()
        is_split_download = data.read_bool()
        includes = [item for item in data.read_array(lambda reader: reader.read_string()) if item]

        return {
            "name": name,
            "size": size,
            "crc": crc,
            "is_in_build": is_in_build,
            "is_changed": is_changed,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
            "includes": includes,
        }

    @classmethod
    def __decode_table_pack_manifest(
        cls,
        data: Reader,
    ) -> dict[str, object]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 5:
            raise ValueError("Malformed JP table pack catalog entry.")

        name = data.read_string() or ""
        size = data.read_int64()
        crc = data.read_int64()
        is_prologue = data.read_bool()
        bundle_files = data.read_array(cls.__decode_table_manifest)

        return {
            "name": name,
            "size": size,
            "crc": crc,
            "is_in_build": False,
            "is_changed": False,
            "is_prologue": is_prologue,
            "is_split_download": False,
            "includes": [str(bundle["name"]) for bundle in bundle_files],
            "bundle_files": bundle_files,
        }
