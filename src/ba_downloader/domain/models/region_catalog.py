from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext


@dataclass(frozen=True, slots=True)
class RegionCatalogResult:
    resources: AssetCollection
    context: ExecutionContext

    @property
    def assets(self) -> AssetCollection:
        return self.resources


@dataclass(frozen=True, slots=True)
class DecodedJPCatalog:
    tables: list[dict[str, object]]
    media: list[dict[str, object]]
    bundles: list[dict[str, object]]
