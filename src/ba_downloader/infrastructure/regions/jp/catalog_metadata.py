from __future__ import annotations

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.catalog_metadata import TableMetadataManifestPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.resource_query import ResourceQueryService


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
            return context, ResourceQueryService.filter_existing(
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
        return active_context, ResourceQueryService.filter_existing(
            table_resources,
            active_context,
        )
