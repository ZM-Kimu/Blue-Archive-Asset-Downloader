import base64
import json
import os
import re
import struct
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from io import BytesIO
from os import path
from typing import Any
from urllib.parse import urljoin

from ba_downloader.application.catalog_pipeline import CatalogPipeline
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    BootstrapSession,
    CatalogSource,
    RegionCapabilities,
    ResolvedRelease,
)
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.settings import Platform
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.apk import download_package_file, extract_xapk_file
from ba_downloader.infrastructure.unity import UnityAssetReader
from ba_downloader.shared.crypto.encryption import convert_string, create_key


@dataclass(frozen=True)
class APKPackageInfo:
    version: str
    download_url: str


@dataclass(frozen=True, slots=True)
class DecodedJPCatalog:
    tables: list[dict[str, object]]
    media: list[dict[str, object]]
    bundles: list[dict[str, object]]


JP_PLATFORM_PATCH_SEGMENTS: dict[Platform, str] = {
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
}


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _resolve_jp_patch_pack_dir(platform: Platform) -> str:
    segment = JP_PLATFORM_PATCH_SEGMENTS[platform]
    return f"{segment}_PatchPack"


class JPReleaseResolver:
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

    def __init__(self, http_client: HttpClientPort) -> None:
        self.http_client = http_client

    @classmethod
    def parse_package_info(cls, payload: bytes) -> APKPackageInfo:
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
        payload = self.http_client.request(
            "GET",
            self.PUREAPK_VERSION_URL,
            headers=self.PUREAPK_HEADERS,
        ).content
        return self.parse_package_info(payload)

    def resolve(self, context: RuntimeContext) -> ResolvedRelease:
        package_info = self.get_latest_package_info()
        return ResolvedRelease(
            region=context.region,
            version=package_info.version,
            package_url=package_info.download_url,
        )


class JPBootstrapper:
    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def apk_extract_folder(self, context: RuntimeContext) -> str:
        return path.join(context.temp_dir, "Data")

    def bootstrap(
        self,
        release: ResolvedRelease,
        context: RuntimeContext,
    ) -> BootstrapSession:
        if not release.package_url:
            raise LookupError("JP release does not contain a package URL.")

        self.logger.info("Downloading APK to retrieve server URL...")
        apk_path = download_package_file(
            self.http_client,
            self.logger,
            release.package_url,
            context.temp_dir,
        )
        extract_xapk_file(
            apk_path,
            self.apk_extract_folder(context),
            context.temp_dir,
        )
        server_url = self.get_server_url(context)
        catalog_root = self._resolve_catalog_root(
            self.http_client.request("GET", server_url).json()
        )
        return BootstrapSession(
            release=release,
            server_url=server_url,
            catalog_root=catalog_root,
            metadata={
                "apk_path": apk_path,
                "bundle_patch_dir": _resolve_jp_patch_pack_dir(context.platform),
            },
        )

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

    def __decode_server_url(self, data: bytes) -> str:
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
        self.logger.info("Retrieving game info...")
        url = version = ""
        for dir, _, files in os.walk(
            path.join(self.apk_extract_folder(context), "assets", "bin", "Data")
        ):
            for file in files:
                if url_obj := UnityAssetReader.search_objects(
                    path.join(dir, file), ["TextAsset"], ["GameMainConfig"], True
                ):
                    url = self.__decode_server_url(
                        url_obj[0].read().m_Script.encode(
                            "utf-8",
                            "surrogateescape",
                        )
                    )
                    self.logger.info(f"Resolved server URL: {url}")
                if version_obj := UnityAssetReader.search_objects(
                    path.join(dir, file), ["PlayerSettings"]
                ):
                    try:
                        version = version_obj[0].read().bundleVersion
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


class JPCatalogSourceProvider:
    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def fetch(
        self,
        session: BootstrapSession,
        context: RuntimeContext,
    ) -> list[CatalogSource]:
        _ = context
        base_url = session.catalog_root.rstrip("/") + "/"
        sources: list[CatalogSource] = []
        bundle_patch_dir = _resolve_jp_patch_pack_dir(context.platform)

        targets = (
            ("table", urljoin(base_url, "TableBundles/TableCatalog.bytes")),
            ("media", urljoin(base_url, "MediaResources/Catalog/MediaCatalog.bytes")),
            ("bundle", urljoin(base_url, f"{bundle_patch_dir}/BundlePackingInfo.json")),
        )

        for name, url in targets:
            response = self.http_client.request("GET", url)
            if not response.content:
                self.logger.error(f"Failed to fetch JP {name} catalog from {url}.")
                continue
            sources.append(
                CatalogSource(
                    name=name,
                    url=url,
                    content=response.content,
                    content_type=str(response.headers.get("content-type", "")),
                )
            )

        if len(sources) < 3:
            raise FileNotFoundError("Cannot pull the JP manifest.")
        return sources


class JPAssetNormalizer:
    @staticmethod
    def normalize(payload: DecodedJPCatalog, session: BootstrapSession) -> AssetCollection:
        assets = AssetCollection()
        base_url = session.catalog_root.rstrip("/") + "/"
        bundle_patch_dir = str(session.metadata.get("bundle_patch_dir", "Android_PatchPack"))

        for table in payload.tables:
            includes = _coerce_string_list(table.get("includes", []))
            assets.add(
                urljoin(base_url, f"TableBundles/{table['name']}"),
                urljoin("Table/", str(table["name"])),
                _coerce_int(table.get("size")),
                str(table["crc"]),
                "crc",
                AssetType.table,
                {"includes": includes},
            )

        for media in payload.media:
            assets.add(
                urljoin(base_url, f"MediaResources/{media['path']}"),
                urljoin("Media/", str(media["path"])),
                _coerce_int(media.get("bytes")),
                str(media["crc"]),
                "crc",
                AssetType.media,
                {"media_type": media["type"]},
            )

        for bundle in payload.bundles:
            bundle_files = _coerce_string_list(bundle.get("bundle_files", []))
            assets.add(
                urljoin(base_url, f"{bundle_patch_dir}/{bundle['name']}"),
                urljoin("Bundle/", str(bundle["name"])),
                _coerce_int(bundle.get("size")),
                str(bundle["crc"]),
                "crc",
                AssetType.bundle,
                {"bundle_files": bundle_files},
            )

        return assets


class JPServer:
    CAPABILITIES = RegionCapabilities(
        supports_sync=True,
        supports_advanced_search=False,
        supports_relation_build=True,
    )

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger
        self.release_resolver = JPReleaseResolver(http_client)
        self.bootstrapper = JPBootstrapper(http_client, logger)
        self.catalog_source_provider = JPCatalogSourceProvider(http_client, logger)
        self.asset_normalizer = JPAssetNormalizer()
        self.pipeline = CatalogPipeline(
            self.release_resolver,
            self.bootstrapper,
            self.catalog_source_provider,
            JPCatalogDecoder(),
            self.asset_normalizer,
        )

    def get_capabilities(self) -> RegionCapabilities:
        return self.CAPABILITIES

    def apk_extract_folder(self, context: RuntimeContext) -> str:
        return self.bootstrapper.apk_extract_folder(context)

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        if context.version:
            self.logger.warn("Specifying a version is not allowed with JPServer.")

        self.logger.info("Automatically fetching latest package info...")
        assets, resolved_context = self.pipeline.load(context)
        self.logger.info(f"Current resource version: {resolved_context.version}")
        self.logger.info(f"Catalog: {assets}.")
        return RegionCatalogResult(
            resources=assets,
            context=resolved_context,
            capabilities=self.get_capabilities(),
        )

    def download_apk_file(self, apk_url: str, context: RuntimeContext) -> str:
        self.logger.info("Downloading APK to retrieve server URL...")
        return download_package_file(
            self.http_client,
            self.logger,
            apk_url,
            context.temp_dir,
        )

    def extract_apk_file(self, apk_path: str, context: RuntimeContext) -> None:
        extract_xapk_file(
            apk_path,
            self.apk_extract_folder(context),
            context.temp_dir,
        )

    @classmethod
    def parse_package_info(cls, payload: bytes) -> APKPackageInfo:
        return JPReleaseResolver.parse_package_info(payload)

    def get_latest_package_info(self) -> APKPackageInfo:
        return self.release_resolver.get_latest_package_info()

    def get_latest_version(self) -> str:
        return self.get_latest_package_info().version

    def get_resource_manifest(self, server_url: str) -> AssetCollection:
        session = BootstrapSession(
            release=ResolvedRelease(region="jp", version=""),
            server_url=server_url,
            catalog_root=self.bootstrapper._resolve_catalog_root(
                self.http_client.request("GET", server_url).json()
            ),
        )
        return self._load_asset_collection(
            session,
            RuntimeContext(
                region="jp",
                threads=1,
                version="",
                raw_dir="",
                extract_dir="",
                temp_dir="",
                extract_while_download=False,
                resource_type=("table", "media", "bundle"),
                proxy_url="",
                max_retries=0,
                search=(),
                advanced_search=(),
                work_dir="",
            ),
        )

    def get_server_url(self, context: RuntimeContext) -> str:
        return self.bootstrapper.get_server_url(context)

    def _load_asset_collection(
        self,
        session: BootstrapSession,
        context: RuntimeContext,
    ) -> AssetCollection:
        try:
            sources = self.catalog_source_provider.fetch(session, context)
            decoded = JPCatalogDecoder.decode(session, sources, context)
            assets = self.asset_normalizer.normalize(decoded, session)
            if not assets:
                raise FileNotFoundError("Cannot pull the JP manifest.")
            return assets
        except Exception as exc:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {exc}."
            ) from exc


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

    @classmethod
    def decode(
        cls,
        session: BootstrapSession,
        sources: list[CatalogSource],
        context: RuntimeContext,
    ) -> DecodedJPCatalog:
        _ = (session, context)
        payload = DecodedJPCatalog(tables=[], media=[], bundles=[])

        for source in sources:
            if source.name == "table":
                payload.tables.extend(cls.__decode_table_catalog(cls.Reader(source.content)))
            elif source.name == "media":
                payload.media.extend(cls.__decode_media_catalog(cls.Reader(source.content)))
            elif source.name == "bundle":
                payload.bundles.extend(cls.__decode_bundle_catalog(source.content))

        return payload

    @classmethod
    def __decode_media_catalog(
        cls,
        data: Reader,
    ) -> list[dict[str, object]]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 1:
            return []

        manifest = data.read_string_map(cls.__decode_media_manifest)
        assets: list[dict[str, object]] = []
        for key, obj in manifest.items():
            path = str(obj["path"]).replace("\\", "/")
            obj["key"] = key
            obj["path"] = path
            assets.append(obj)
        return assets

    @classmethod
    def __decode_table_catalog(
        cls,
        data: Reader,
    ) -> list[dict[str, object]]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 1:
            return []

        manifest = data.read_string_map(cls.__decode_table_manifest)
        if member_count >= 2:
            for key, obj in data.read_string_map(cls.__decode_table_pack_manifest).items():
                manifest[key] = obj

        assets: list[dict[str, object]] = []
        for key, obj in manifest.items():
            obj["key"] = key
            assets.append(obj)
        return assets

    @staticmethod
    def __decode_bundle_catalog(raw_data: bytes) -> list[dict[str, object]]:
        payload = json.loads(raw_data)
        assets: list[dict[str, object]] = []
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
                assets.append(
                    {
                        "name": pack_name,
                        "size": int(pack.get("PackSize", 0) or 0),
                        "crc": int(pack.get("Crc", 0) or 0),
                        "bundle_files": [
                            str(bundle.get("Name", "")).strip()
                            for bundle in pack.get("BundleFiles", [])
                            if isinstance(bundle, Mapping) and bundle.get("Name")
                        ],
                        "is_prologue": bool(pack.get("IsPrologue", False)),
                        "is_split_download": bool(pack.get("IsSplitDownload", False)),
                    }
                )
        return assets

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
