from collections.abc import Callable

from ba_downloader.application.use_cases.asset_selection import AssetSelectionService
from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.application.use_cases.relation_search import RelationSearchService
from ba_downloader.application.use_cases.sync_policy import (
    SyncExtractionMode,
    resolve_sync_workflow_policy,
)
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.relation import RelationBuilderPort
from ba_downloader.domain.services.resource_query import ResourceQueryService


class SyncAssetsUseCase:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        extract_service: ExtractAssetsUseCase,
        schema_preparation: SchemaPreparationPort,
        relation_builder_factory: Callable[[RuntimeContext], RelationBuilderPort],
        logger: LoggerPort,
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.extract_service = extract_service
        self.schema_preparation = schema_preparation
        self.relation_builder_factory = relation_builder_factory
        self.logger = logger
        self.asset_selector = AssetSelectionService(logger)
        self.relation_search = RelationSearchService(relation_builder_factory, logger)

    def _prepare_schema(self, context: RuntimeContext) -> None:
        self.schema_preparation.prepare(context)

    def _search_resource(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
        schema_prepared: bool,
    ) -> AssetCollection:
        advanced_keywords: list[str] | None = None
        if context.advanced_search:
            relation_result = self.relation_search.resolve_sync_keywords(
                resources,
                context,
                schema_preparation=self.schema_preparation,
                downloader=self.downloader,
                schema_prepared=schema_prepared,
            )
            advanced_keywords = relation_result.keywords

        return self.asset_selector.filter_search_resources(
            resources,
            context,
            advanced_keywords=advanced_keywords,
        )

    def _filter_and_download(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> AssetCollection:
        filtered = ResourceQueryService.filter_type(resources, context.resource_type)
        self.downloader.verify_and_download(filtered, context)
        return filtered

    def run(self, context: RuntimeContext) -> RuntimeContext:
        capabilities = self.provider.get_capabilities()
        if not capabilities.supports_sync:
            raise LookupError(
                f"Sync is temporarily unavailable for region '{context.region}'."
            )
        if context.advanced_search and not capabilities.supports_advanced_search:
            raise LookupError(
                f"Advanced search is not supported for region '{context.region}'."
            )

        catalog = self.provider.load_catalog(context)
        active_context = catalog.context
        resources = catalog.resources
        policy = resolve_sync_workflow_policy(active_context)

        if policy.prepares_schema:
            self._prepare_schema(active_context)

        if active_context.search or active_context.advanced_search:
            resources = self._search_resource(
                resources,
                active_context,
                policy.prepares_schema,
            )

        filtered = self._filter_and_download(resources, active_context)
        extract_resources = (
            filtered
            if active_context.search or active_context.advanced_search
            else None
        )
        if policy.extraction_mode is SyncExtractionMode.direct:
            self.extract_service.run(active_context, extract_resources)
        else:
            self.extract_service.run_post_download(active_context, extract_resources)
        return active_context
