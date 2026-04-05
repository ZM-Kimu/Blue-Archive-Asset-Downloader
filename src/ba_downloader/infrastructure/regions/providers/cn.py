from __future__ import annotations

import json
import re
from io import BytesIO
from typing import ClassVar, Literal
from urllib.parse import urljoin

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort, get_header
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.regions.providers.common import (
    build_region_catalog_result,
    coerce_int,
    join_catalog_url,
    warn_if_platform_ignored,
)


class CNServer:
    CAPABILITIES = RegionCapabilities(
        supports_sync=True,
        supports_advanced_search=False,
        supports_relation_build=False,
    )

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger
        self.urls = {
            "home": "https://bluearchive-cn.com/",
            "version": "https://bluearchive-cn.com/api/meta/setup",
            "info": "https://gs-api.bluearchive-cn.com/api/state",
            "bili": "https://line1-h5-pc-api.biligame.com/game/detail/gameinfo?game_base_id=109864",
        }

    def get_capabilities(self) -> RegionCapabilities:
        return self.CAPABILITIES

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        if context.version:
            self.logger.warn("Specifying a version is not allowed with CNServer.")
        warn_if_platform_ignored(context, self.logger)

        self.logger.info("Automatically fetching latest version...")
        version = self.get_latest_version()
        resolved_context = context.with_updates(version=version)
        self.logger.info(f"Current resource version: {version}")

        self.logger.info("Pulling catalog...")
        resources = self.get_resource_manifest(self.get_server_info(resolved_context))
        return build_region_catalog_result(
            self.logger,
            resources=resources,
            context=resolved_context,
            capabilities=self.get_capabilities(),
        )

    def get_apk_url(self, server: Literal["official", "bili"] = "official") -> str:
        try:
            if server == "bili":
                bili_link = self.http_client.request("GET", self.urls["bili"])
                return str(bili_link.json()["data"]["android_download_link"])

            response = self.http_client.request("GET", self.urls["home"])

            if not (
                js_match := re.search(
                    r'<script[^>]+type="module"[^>]+crossorigin[^>]+src="([^"]+)"[^>]*>',
                    response.text,
                )
            ):
                raise LookupError

            js_response = self.http_client.request("GET", js_match.group(1))
            if apk_match := re.search(r'http[s]?://[^\s"<>]+?\.apk', js_response.text):
                return apk_match.group()

            raise LookupError("Could not find the latest CN APK URL.")
        except (LookupError, OSError, ValueError, TypeError) as exc:
            if server == "bili":
                raise LookupError(
                    "Could not find the latest version. Retrying may resolve the issue."
                ) from exc
            return self.get_apk_url("bili")

    def get_latest_version(self) -> str:
        response = self.http_client.request("GET", self.urls["version"])
        if version_match := re.search(r"(\d+\.\d+\.\d+)", response.text):
            return version_match.group(1)
        raise LookupError(
            "Unable to retrieve the version. Retry might solve this issue."
        )

    def get_resource_manifest(self, server_info: dict[str, object]) -> AssetCollection:
        try:
            base_url = self._resolve_catalog_root(server_info)
            assets = AssetCollection()
            loaded_sections = self._load_cn_catalog_sections(server_info, base_url, assets)
            if loaded_sections != {"table", "media", "bundle"}:
                raise FileNotFoundError("Cannot pull the manifest.")
            return assets
        except (FileNotFoundError, KeyError, LookupError, TypeError, ValueError) as exc:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {exc}."
            ) from exc

    @staticmethod
    def _resolve_catalog_root(server_info: dict[str, object]) -> str:
        roots = server_info.get("AddressablesCatalogUrlRoots", [])
        if not isinstance(roots, list) or not roots:
            raise LookupError("AddressablesCatalogUrlRoots was not found.")
        return str(roots[0]).rstrip("/") + "/"

    def _load_cn_catalog_sections(
        self,
        server_info: dict[str, object],
        base_url: str,
        assets: AssetCollection,
    ) -> set[str]:
        loaded_sections: set[str] = set()
        sections: tuple[
            tuple[Literal["table", "media", "bundle"], str, str, bool],
            ...,
        ] = (
            (
                "table",
                f"Manifest/TableBundles/{server_info['TableVersion']}/TableManifest",
                urljoin(base_url, "pool/TableBundles/"),
                False,
            ),
            (
                "media",
                f"Manifest/MediaResources/{server_info['MediaVersion']}/MediaManifest",
                urljoin(base_url, "pool/MediaResources/"),
                False,
            ),
            (
                "bundle",
                (
                    "AssetBundles/Catalog/"
                    f"{server_info['ResourceVersion']}/Android/bundleDownloadInfo.json"
                ),
                urljoin(base_url, "AssetBundles/Android/"),
                True,
            ),
        )
        for section_name, relative_url, root_url, require_json in sections:
            if self._load_cn_catalog_section(
                section_name,
                join_catalog_url(base_url, relative_url),
                root_url,
                assets,
                require_json=require_json,
            ):
                loaded_sections.add(section_name)
        return loaded_sections

    def _load_cn_catalog_section(
        self,
        section_name: Literal["table", "media", "bundle"],
        section_url: str,
        root_url: str,
        assets: AssetCollection,
        *,
        require_json: bool,
    ) -> bool:
        section_data = self.http_client.request("GET", section_url)
        content_type = get_header(section_data.headers, "Content-Type").lower()
        if not section_data.content:
            self.logger.error(
                f"Failed to fetch {section_name} catalog. Retry may solve the issue."
            )
            return False
        if require_json and "application/json" not in content_type:
            self.logger.error(
                f"Failed to fetch {section_name} catalog. Retry may solve the issue."
            )
            return False

        CNCatalogDecoder.decode_to_assets(
            section_data.content,
            assets,
            section_name,
            root_url,
        )
        return True

    def get_server_info(self, context: RuntimeContext) -> dict[str, object]:
        response = self.http_client.request(
            "GET",
            self.urls["info"],
            headers={
                "APP-VER": context.version,
                "PLATFORM-ID": "1",
                "CHANNEL-ID": "2",
            },
        )
        return response.json()


class CNCatalogDecoder:
    MEDIA_TYPES: ClassVar[dict[int, str]] = {
        1: "ogg",
        2: "mp4",
        3: "jpg",
        4: "png",
        5: "acb",
        6: "awb",
    }

    @staticmethod
    def decode_to_assets(
        raw_data: bytes,
        assets: AssetCollection,
        manifest_type: Literal["bundle", "table", "media"],
        base_url: str,
    ) -> None:
        if manifest_type == "bundle":
            bundle_data = json.loads(raw_data)
            for item in bundle_data.get("BundleFiles", []):
                if isinstance(item, dict):
                    CNCatalogDecoder._decode_bundle_manifest(item, assets, base_url)
            return

        if manifest_type == "media":
            data = BytesIO(raw_data)
            while item := data.readline():
                if item.strip():
                    CNCatalogDecoder._decode_media_manifest(item, assets, base_url)
            return

        table_data = json.loads(raw_data).get("Table", {})
        if not isinstance(table_data, dict):
            return
        for item in table_data.values():
            if isinstance(item, dict):
                CNCatalogDecoder._decode_table_manifest(item, assets, base_url)

    @staticmethod
    def _decode_bundle_manifest(
        data: dict[str, object],
        assets: AssetCollection,
        base_url: str,
    ) -> None:
        name = str(data.get("Name", "")).strip()
        if not name:
            return

        assets.add(
            urljoin(base_url, name),
            urljoin("Bundle/", name),
            coerce_int(data.get("Size", 0)),
            str(data.get("Crc", "")),
            # The CN endpoint exposes this hash in a field named "Crc",
            # but the observed value is still used as the legacy MD5-style asset key.
            "md5",
            AssetType.bundle,
        )

    @classmethod
    def _decode_media_manifest(
        cls,
        data: bytes,
        assets: AssetCollection,
        base_url: str,
    ) -> None:
        parts = data.decode("utf-8").strip().split(",")
        if len(parts) < 5:
            raise ValueError("Malformed CN media manifest entry.")

        file_path, md5, media_type_str, size_str, _ = parts[:5]
        media_type = int(media_type_str)
        media_extension = cls.MEDIA_TYPES.get(media_type)
        normalized_path = file_path + (f".{media_extension}" if media_extension else "")
        file_url_path = md5[:2] + "/" + md5

        assets.add(
            urljoin(base_url, file_url_path),
            urljoin("Media/", normalized_path),
            int(size_str),
            md5,
            "md5",
            AssetType.media,
            {"media_type": media_extension or str(media_type)},
        )

    @staticmethod
    def _decode_table_manifest(
        data: dict[str, object],
        assets: AssetCollection,
        base_url: str,
    ) -> None:
        name = str(data.get("Name", "")).strip()
        md5 = str(data.get("Crc", ""))
        if not name or not md5:
            return

        includes = data.get("Includes", [])
        assets.add(
            urljoin(base_url, md5[:2] + "/" + md5),
            urljoin("Table/", name),
            coerce_int(data.get("Size", 0)),
            md5,
            # The CN endpoint exposes this hash in a field named "Crc",
            # but the observed value is still used as the legacy MD5-style asset key.
            "md5",
            AssetType.table,
            {"includes": list(includes) if isinstance(includes, list) else []},
        )


__all__ = ["CNServer"]
