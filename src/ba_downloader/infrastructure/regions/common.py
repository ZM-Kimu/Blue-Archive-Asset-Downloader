from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urljoin

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.ports.logging import LoggerPort


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


def build_region_catalog_result(
    logger: LoggerPort,
    *,
    resources: AssetCollection,
    context: ExecutionContext,
) -> RegionCatalogResult:
    logger.info(f"Catalog: {resources}.")
    return RegionCatalogResult(
        resources=resources,
        context=context,
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
