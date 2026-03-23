from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.asset import AssetCollection, RegionCapabilities
from ba_downloader.domain.models.runtime import RuntimeContext


@dataclass(frozen=True, slots=True)
class RegionCatalogResult:
    resources: AssetCollection
    context: RuntimeContext
    capabilities: RegionCapabilities

    @property
    def assets(self) -> AssetCollection:
        return self.resources
