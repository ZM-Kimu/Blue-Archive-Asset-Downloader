from collections.abc import Callable

from ba_downloader.application.profiles import (
    RegionProfile,
    SyncExtractionMode,
)
from ba_downloader.application.use_cases.asset_selection import AssetSelectionService
from ba_downloader.application.use_cases.character_index_search import (
    CharacterIndexSearchService,
)
from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.resource_query import ResourceQueryService


class SyncAssetsUseCase:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        extract_service: ExtractAssetsUseCase,
        schema_preparation: SchemaPreparationPort,
        character_index_builder_factory: Callable[
            [RuntimeContext], CharacterIndexBuilderPort
        ],
        logger: LoggerPort,
        *,
        workflow_profile: RegionProfile,
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.extract_service = extract_service
        self.schema_preparation = schema_preparation
        self.character_index_builder_factory = character_index_builder_factory
        self.logger = logger
        self.workflow_profile = workflow_profile
        self.asset_selector = AssetSelectionService(logger)
        self.character_index_search = CharacterIndexSearchService(
            character_index_builder_factory,
            logger,
            workflow_profile.settings_policy,
        )

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
            index_result = self.character_index_search.resolve_sync_keywords(
                resources,
                context,
                schema_preparation=self.schema_preparation,
                downloader=self.downloader,
                schema_prepared=schema_prepared,
            )
            advanced_keywords = index_result.keywords

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
        self.workflow_profile.catalog_metadata.on_catalog_loaded(
            active_context,
            resources,
        )

        if self.workflow_profile.prepares_schema_for_sync:
            self._prepare_schema(active_context)

        if active_context.search or active_context.advanced_search:
            resources = self._search_resource(
                resources,
                active_context,
                self.workflow_profile.prepares_schema_for_sync,
            )

        filtered = self._filter_and_download(resources, active_context)
        if self.workflow_profile.sync_extraction_mode is SyncExtractionMode.direct:
            self.extract_service.run(active_context, filtered)
        else:
            self.extract_service.run_post_download(active_context, filtered)
        return active_context
