from typing import Protocol

from ba_downloader.domain.models.asset import RegionCapabilities
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region_catalog import RegionCatalogResult


class RegionProvider(Protocol):
    def get_capabilities(self) -> RegionCapabilities: ...

    def load_catalog(self, context: ExecutionContext) -> RegionCatalogResult: ...
