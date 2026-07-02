from __future__ import annotations

from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext


class TableMetadataManifestPort(Protocol):
    def load(self, context: RuntimeContext) -> AssetCollection | None: ...

    def write(self, context: RuntimeContext, resources: AssetCollection) -> None: ...
