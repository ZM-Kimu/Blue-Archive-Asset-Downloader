from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.resource import Resource
from ba_downloader.domain.models.runtime import RuntimeContext


@dataclass(frozen=True, slots=True)
class RegionCatalogResult:
    resources: Resource
    context: RuntimeContext
