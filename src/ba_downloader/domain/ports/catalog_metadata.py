from __future__ import annotations

from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext


class CatalogMetadataPolicy(Protocol):
    def on_catalog_loaded(
        self,
        context: RuntimeContext,
        resources: AssetCollection,
    ) -> None: ...

    def resolve_existing_table_resources(
        self,
        context: RuntimeContext,
    ) -> tuple[RuntimeContext, AssetCollection | None]: ...


class TableMetadataManifestPort(Protocol):
    def load(self, context: RuntimeContext) -> AssetCollection | None: ...

    def write(self, context: RuntimeContext, resources: AssetCollection) -> None: ...
