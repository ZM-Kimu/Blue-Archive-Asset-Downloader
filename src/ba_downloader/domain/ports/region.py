from typing import Literal, Protocol

from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext

Region = Literal["cn", "gl", "jp"]


class RegionProvider(Protocol):
    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        ...
