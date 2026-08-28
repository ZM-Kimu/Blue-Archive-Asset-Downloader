from __future__ import annotations

from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext


class CatalogMetadataPolicy(Protocol):
    def on_catalog_loaded(
        self,
        context: ExecutionContext,
        resources: AssetCollection,
    ) -> None: ...

    def resolve_existing_table_resources(
        self,
        context: ExecutionContext,
    ) -> tuple[ExecutionContext, AssetCollection | None]: ...


class TableMetadataManifestPort(Protocol):
    def load(self, context: ExecutionContext) -> AssetCollection | None: ...

    def write(self, context: ExecutionContext, resources: AssetCollection) -> None: ...
