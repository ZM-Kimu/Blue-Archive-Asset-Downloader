from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urljoin

from ba_downloader.domain.models.asset import AssetCollection, RegionCapabilities
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort

SYNC_AND_RELATION_CAPABILITIES = RegionCapabilities(
    supports_sync=True,
    supports_advanced_search=False,
    supports_relation_build=True,
)


def coerce_int(value: object) -> int:
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


def coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def warn_if_platform_ignored(context: RuntimeContext, logger: LoggerPort) -> None:
    if context.platform_explicit:
        logger.warn("The --platform option only applies to JP and was ignored.")


def build_region_catalog_result(
    logger: LoggerPort,
    *,
    resources: AssetCollection,
    context: RuntimeContext,
    capabilities: RegionCapabilities,
) -> RegionCatalogResult:
    logger.info(f"Catalog: {resources}.")
    return RegionCatalogResult(
        resources=resources,
        context=context,
        capabilities=capabilities,
    )


def join_catalog_url(
    base_url: str, relative_url_factory: Callable[[], str] | str
) -> str:
    relative_url = (
        relative_url_factory()
        if callable(relative_url_factory)
        else relative_url_factory
    )
    return urljoin(base_url, relative_url)
