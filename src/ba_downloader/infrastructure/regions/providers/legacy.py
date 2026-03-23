from __future__ import annotations

from collections.abc import Callable

from ba_downloader.domain.models.asset import AssetCollection, AssetType, RegionCapabilities
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.legacy.models.resource import Resource


def legacy_resource_to_assets(resource: Resource) -> AssetCollection:
    assets = AssetCollection()
    type_map = {
        "table": AssetType.table,
        "media": AssetType.media,
        "bundle": AssetType.bundle,
    }

    for item in resource:
        assets.add(
            item.url,
            item.path,
            item.size,
            str(item.checksum),
            item.check_type,
            type_map[item.resource_type.name],
            item.addition,
        )

    return assets


class LegacyRegionPipelineAdapter:
    def __init__(
        self,
        provider_factory: Callable[..., RegionProvider],
        *,
        capabilities: RegionCapabilities,
        http_client: object,
        logger: object,
    ) -> None:
        self._provider = provider_factory(http_client=http_client, logger=logger)
        self._capabilities = capabilities

    def get_capabilities(self) -> RegionCapabilities:
        return self._capabilities

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        result = self._provider.load_catalog(context)
        return RegionCatalogResult(
            resources=legacy_resource_to_assets(result.resources),
            context=result.context,
            capabilities=self._capabilities,
        )
