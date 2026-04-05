from __future__ import annotations

import re
from os import path
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort
from ba_downloader.infrastructure.apk import download_package_file, extract_xapk_file
from ba_downloader.infrastructure.regions.providers.common import (
    build_region_catalog_result,
    warn_if_platform_ignored,
)


class GLServer:
    CAPABILITIES = RegionCapabilities(
        supports_sync=True,
        supports_advanced_search=True,
        supports_relation_build=True,
    )
    CATALOG_URL = "https://api-pub.nexon.com/patch/v1.1/version-check"
    UPTODOWN_URL = "https://blue-archive-global.en.uptodown.com/android"
    APKPURE_URL = "https://d.apkpure.com/b/XAPK/com.nexon.bluearchive"

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def get_capabilities(self) -> RegionCapabilities:
        return self.CAPABILITIES

    @staticmethod
    def apk_extract_folder(context: RuntimeContext) -> str:
        return path.join(context.temp_dir, "Data")

    @classmethod
    def build_apk_url(cls, version: str) -> str:
        if not version:
            return f"{cls.APKPURE_URL}?version=latest"
        return f"{cls.APKPURE_URL}?versionCode={version.split('.')[-1]}"

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        version = context.version
        resolved_context = context
        warn_if_platform_ignored(context, self.logger)

        if not version:
            self.logger.info("Version not specified. Automatically fetching latest...")
            version = self.get_latest_version()
            resolved_context = context.with_updates(version=version)

        self.logger.info(f"Current resource version: {version}")
        self.logger.info("Pulling catalog...")
        resources = self.get_resource_catalog(self.get_server_url(version))
        return self._build_catalog_result(resources, resolved_context)

    def _build_catalog_result(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> RegionCatalogResult:
        return build_region_catalog_result(
            self.logger,
            resources=resources,
            context=context,
            capabilities=self.get_capabilities(),
        )

    def get_apk_url(self, version: str) -> str:
        return self.build_apk_url(version)

    def get_latest_version(self) -> str:
        response = self.http_client.request("GET", self.UPTODOWN_URL)

        if version_match := re.search(r"(\d+\.\d+\.\d+)", response.text):
            return version_match.group(1)

        raise LookupError("Unable to retrieve the version.")

    def get_server_url(self, version: str) -> str:
        request_body = {
            "market_game_id": "com.nexon.bluearchive",
            "market_code": "playstore",
            "curr_build_version": version,
            "curr_build_number": version.split(".")[-1],
        }

        server_url = self.http_client.request(
            "POST",
            self.CATALOG_URL,
            json=request_body,
        ).json()
        return str(server_url.get("patch", {}).get("resource_path", ""))

    def get_resource_catalog(self, server_url: str) -> AssetCollection:
        assets = AssetCollection()
        found_types: set[AssetType] = set()
        try:
            base_url = server_url.rsplit("/", 1)[0].rstrip("/") + "/"
            resource_payload = self.http_client.request("GET", server_url).json()

            for item in resource_payload.get("resources", []):
                if isinstance(item, dict):
                    self._add_resource(assets, base_url, item, found_types)

            if found_types != {AssetType.table, AssetType.media, AssetType.bundle}:
                self.logger.warn(
                    "The catalog is incomplete, and some resource types may fail to be retrieved.",
                )
        except (LookupError, OSError, TypeError, ValueError) as exc:
            raise LookupError(
                f"Encountered the following error while attempting to fetch catalog: {exc}."
            ) from exc

        return assets

    @staticmethod
    def _add_resource(
        assets: AssetCollection,
        base_url: str,
        item: dict[str, Any],
        found_types: set[AssetType],
    ) -> None:
        resource_path = str(item.get("resource_path", ""))
        if not resource_path:
            return

        resource_url = urljoin(base_url, resource_path)
        resource_size = int(item.get("resource_size", 0) or 0)
        resource_hash = str(item.get("resource_hash", ""))

        if "TableBundles" in resource_path:
            found_types.add(AssetType.table)
            assets.add(
                resource_url,
                "Table" + resource_path.split("TableBundles", 1)[-1],
                resource_size,
                resource_hash,
                "md5",
                AssetType.table,
            )
            return

        if "MediaResources" in resource_path:
            found_types.add(AssetType.media)
            assets.add(
                resource_url,
                "Media" + resource_path.split("MediaResources", 1)[-1],
                resource_size,
                resource_hash,
                "md5",
                AssetType.media,
            )
            return

        if resource_path.endswith(".bundle"):
            found_types.add(AssetType.bundle)
            assets.add(
                resource_url,
                "Bundle/" + resource_path.rsplit("/", 1)[-1],
                resource_size,
                resource_hash,
                "md5",
                AssetType.bundle,
            )


class GLRuntimeAssetPreparer(RuntimeAssetPreparerPort):
    RUNTIME_FILES = ("libil2cpp.so", "global-metadata.dat")

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def prepare(self, context: RuntimeContext) -> None:
        if self._has_runtime_assets(context):
            return
        if not context.version:
            raise LookupError("GL runtime asset preparation requires a resolved version.")

        self.logger.info("Downloading APK to prepare runtime assets...")
        package_path = download_package_file(
            self.http_client,
            self.logger,
            GLServer.build_apk_url(context.version),
            context.temp_dir,
            transport="browser",
        )
        extract_xapk_file(
            package_path,
            GLServer.apk_extract_folder(context),
            context.temp_dir,
        )
        if not self._has_runtime_assets(context):
            raise FileNotFoundError("Unable to prepare GL runtime assets from the package.")

    def _has_runtime_assets(self, context: RuntimeContext) -> bool:
        temp_dir = Path(context.temp_dir)
        if not temp_dir.exists():
            return False
        return all(any(temp_dir.rglob(file_name)) for file_name in self.RUNTIME_FILES)


__all__ = ["GLServer"]
