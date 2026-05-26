from __future__ import annotations

from collections.abc import Callable

from ba_downloader.domain.models.region import Region
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort
from ba_downloader.infrastructure.regions.cn.provider import (
    CNRegionProvider,
    CNRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.regions.gl.provider import (
    GLRegionProvider,
    GLRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.regions.jp.provider import JPRegionProvider
from ba_downloader.infrastructure.schema.catalog import JPCatalogDecoder


class RegionRegistry:
    def __init__(self) -> None:
        self._providers: dict[Region, Callable[..., RegionProvider]] = {}

    def register(
        self,
        region: Region,
        provider_factory: Callable[..., RegionProvider],
    ) -> None:
        self._providers[region] = provider_factory

    def resolve(self, region: Region) -> Callable[..., RegionProvider]:
        if region not in self._providers:
            raise KeyError(f"Region '{region}' is not registered.")
        return self._providers[region]


class NoOpRuntimeAssetPreparer(RuntimeAssetPreparerPort):
    def prepare(self, context: RuntimeContext) -> None:
        _ = context


class RuntimeAssetPreparerRegistry:
    def __init__(self) -> None:
        self._preparers: dict[Region, Callable[..., RuntimeAssetPreparerPort]] = {}

    def register(
        self,
        region: Region,
        preparer_factory: Callable[..., RuntimeAssetPreparerPort],
    ) -> None:
        self._preparers[region] = preparer_factory

    def resolve(self, region: Region) -> Callable[..., RuntimeAssetPreparerPort]:
        if region not in self._preparers:
            raise KeyError(f"Region '{region}' is not registered.")
        return self._preparers[region]


def build_noop_runtime_preparer(**_: object) -> RuntimeAssetPreparerPort:
    return NoOpRuntimeAssetPreparer()


def build_jp_region_provider(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> RegionProvider:
    return JPRegionProvider(
        http_client,
        logger,
        catalog_decoder=JPCatalogDecoder(),
    )


DEFAULT_REGION_REGISTRY = RegionRegistry()
DEFAULT_REGION_REGISTRY.register("cn", CNRegionProvider)
DEFAULT_REGION_REGISTRY.register("gl", GLRegionProvider)
DEFAULT_REGION_REGISTRY.register("jp", build_jp_region_provider)

DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY = RuntimeAssetPreparerRegistry()
DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.register("cn", CNRuntimeAssetPreparer)
DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.register("gl", GLRuntimeAssetPreparer)
DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.register("jp", build_noop_runtime_preparer)
