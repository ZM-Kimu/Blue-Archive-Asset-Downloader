from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext


@dataclass(frozen=True, slots=True)
class RegionCatalogResult:
    resources: AssetCollection
    context: RuntimeContext

    @property
    def assets(self) -> AssetCollection:
        return self.resources


@dataclass(frozen=True, slots=True)
class DecodedJPCatalog:
    tables: list[dict[str, object]]
    media: list[dict[str, object]]
    bundles: list[dict[str, object]]
