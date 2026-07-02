from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from ba_downloader.application.use_cases.asset_selection import AssetSelectionService
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.catalog_metadata import TableMetadataManifestPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.resource_query import ResourceQueryService


class SyncExtractionMode(Enum):
    direct = "direct"
    post_download = "post_download"


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


class NoopCatalogMetadataPolicy:
    def on_catalog_loaded(
        self,
        context: RuntimeContext,
        resources: AssetCollection,
    ) -> None:
        _ = context
        _ = resources

    def resolve_existing_table_resources(
        self,
        context: RuntimeContext,
    ) -> tuple[RuntimeContext, AssetCollection | None]:
        return context, None


class JpTableCatalogMetadataPolicy:
    def __init__(
        self,
        provider: RegionProvider,
        logger: LoggerPort,
        store: TableMetadataManifestPort,
    ) -> None:
        self.provider = provider
        self.logger = logger
        self.store = store

    def on_catalog_loaded(
        self,
        context: RuntimeContext,
        resources: AssetCollection,
    ) -> None:
        self.store.write(context, resources)

    def resolve_existing_table_resources(
        self,
        context: RuntimeContext,
    ) -> tuple[RuntimeContext, AssetCollection | None]:
        stored_resources = self.store.load(context)
        if stored_resources is not None:
            return context, AssetSelectionService.filter_existing_resources(
                stored_resources,
                context,
            )

        try:
            catalog = self.provider.load_catalog(context)
        except Exception as exc:
            raise LookupError(
                "JP table metadata manifest is missing or stale and catalog "
                "refresh failed. JP table extraction requires catalog metadata "
                f"for encrypted nested table archives. Error: {exc}"
            ) from exc

        active_context = catalog.context
        self.store.write(active_context, catalog.resources)
        table_resources = ResourceQueryService.filter_type(
            catalog.resources,
            ("table",),
        )
        return active_context, AssetSelectionService.filter_existing_resources(
            table_resources,
            active_context,
        )


@dataclass(frozen=True, slots=True)
class RegionProfile:
    prepares_schema_for_sync: bool
    sync_extraction_mode: SyncExtractionMode
    catalog_metadata: CatalogMetadataPolicy
    requires_jp_table_prerequisite: bool = False


def build_region_profile(
    context: RuntimeContext,
    provider: RegionProvider,
    logger: LoggerPort,
    table_metadata_store: TableMetadataManifestPort,
) -> RegionProfile:
    catalog_metadata: CatalogMetadataPolicy = NoopCatalogMetadataPolicy()
    if context.region == "jp":
        catalog_metadata = JpTableCatalogMetadataPolicy(
            provider,
            logger,
            table_metadata_store,
        )

    extraction_mode = (
        SyncExtractionMode.direct
        if context.region == "gl"
        else SyncExtractionMode.post_download
    )
    return RegionProfile(
        prepares_schema_for_sync=context.region in {"cn", "gl", "jp"},
        sync_extraction_mode=extraction_mode,
        catalog_metadata=catalog_metadata,
        requires_jp_table_prerequisite=context.region == "jp",
    )
