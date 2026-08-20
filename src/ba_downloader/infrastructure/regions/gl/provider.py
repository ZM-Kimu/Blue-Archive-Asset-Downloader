from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.regions.common import (
    build_region_catalog_result,
)
from ba_downloader.infrastructure.regions.gl.release_resolver import GLReleaseResolver


class GLRegionProvider:
    CAPABILITIES = RegionCapabilities(
        supports_sync=True,
        supports_advanced_search=True,
        supports_character_index_build=True,
    )
    CATALOG_URL = "https://api-patch.nexon.com/patch/v1.1/version-check"

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger
        self.release_resolver = GLReleaseResolver(http_client)

    def get_capabilities(self) -> RegionCapabilities:
        return self.CAPABILITIES

    def load_catalog(self, context: ExecutionContext) -> RegionCatalogResult:
        self.logger.info("Automatically fetching latest package info...")
        release = self.release_resolver.resolve_latest(context)
        resolved_context = context.resolve_resource_version(release.version)

        self.logger.info(f"Current resource version: {release.version}")
        self.logger.info("Pulling catalog...")
        resources = self.get_resource_catalog(self.get_server_url(release.version))
        return self._build_catalog_result(resources, resolved_context)

    def _build_catalog_result(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
    ) -> RegionCatalogResult:
        return build_region_catalog_result(
            self.logger,
            resources=resources,
            context=context,
        )

    def get_latest_version(self) -> str:
        return self.release_resolver.get_latest_release().version

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


__all__ = ["GLRegionProvider"]
