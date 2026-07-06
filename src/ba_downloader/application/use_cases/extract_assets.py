from ba_downloader.application.profiles import RegionProfile
from ba_downloader.application.use_cases.asset_selection import AssetSelectionService
from ba_downloader.application.use_cases.relation_search import (
    RelationBuilderFactory,
    RelationSearchService,
)
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import (
    AssetExtractionPort,
    ExtractionPrerequisitePort,
)
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.resource_query import ResourceQueryService


class ExtractAssetsUseCase:
    def __init__(
        self,
        extraction_workflow: AssetExtractionPort,
        logger: LoggerPort | None = None,
        *,
        provider: RegionProvider | None = None,
        relation_builder_factory: RelationBuilderFactory | None = None,
        prerequisite_service: ExtractionPrerequisitePort | None = None,
        workflow_profile: RegionProfile,
    ) -> None:
        self.extraction_workflow = extraction_workflow
        self.logger = logger
        self.provider = provider
        self.prerequisite_service = prerequisite_service
        self.workflow_profile = workflow_profile
        self.asset_selector = (
            AssetSelectionService(logger) if logger is not None else None
        )
        self.relation_search = (
            RelationSearchService(
                relation_builder_factory,
                logger,
                workflow_profile.settings_policy,
            )
            if relation_builder_factory is not None and logger is not None
            else None
        )

    def _resolve_search_resources(
        self,
        context: RuntimeContext,
    ) -> tuple[RuntimeContext, AssetCollection]:
        if self.provider is None:
            raise LookupError("Extract search requires a configured region provider.")

        capabilities = self.provider.get_capabilities()
        if context.advanced_search and not capabilities.supports_advanced_search:
            raise LookupError(
                f"Advanced search is not supported for region '{context.region}'."
            )

        catalog = self.provider.load_catalog(context)
        active_context = catalog.context
        self.workflow_profile.catalog_metadata.on_catalog_loaded(
            active_context,
            catalog.resources,
        )
        resources = self._filter_search_resources(catalog.resources, active_context)
        resources = ResourceQueryService.filter_type(
            resources,
            active_context.resource_type,
        )
        return active_context, AssetSelectionService.filter_existing_resources(
            resources,
            active_context,
        )

    def _filter_search_resources(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> AssetCollection:
        if self.asset_selector is not None:
            advanced_keywords = None
            if context.advanced_search:
                if self.relation_search is None:
                    raise LookupError(
                        "Extract advanced search requires a configured relation builder."
                    )
                advanced_keywords = self.relation_search.resolve_existing_keywords(
                    context
                )
            return self.asset_selector.filter_search_resources(
                resources,
                context,
                advanced_keywords=advanced_keywords,
            )

        if context.advanced_search:
            raise LookupError(
                "Extract advanced search requires a configured relation builder."
            )
        if context.search:
            return ResourceQueryService.search_name(resources, context.search)
        return resources

    def _resolve_table_metadata_resources(
        self,
        context: RuntimeContext,
    ) -> tuple[RuntimeContext, AssetCollection | None]:
        return self.workflow_profile.catalog_metadata.resolve_existing_table_resources(
            context
        )

    @staticmethod
    def _filter_resources_for_type(
        resources: AssetCollection | None,
        resource_type: str,
    ) -> AssetCollection | None:
        if resources is None:
            return None
        return ResourceQueryService.filter_type(resources, (resource_type,))

    @staticmethod
    def _should_extract_type(resources: AssetCollection | None) -> bool:
        return resources is None or bool(resources)

    def run(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        active_context = context
        active_resources = resources
        if active_resources is None and (
            active_context.search or active_context.advanced_search
        ):
            active_context, active_resources = self._resolve_search_resources(
                active_context
            )

        if active_resources is not None and not active_resources:
            return

        if "table" in active_context.resource_type:
            table_resources = self._filter_resources_for_type(
                active_resources,
                "table",
            )
            if table_resources is None:
                active_context, table_resources = (
                    self._resolve_table_metadata_resources(active_context)
                )
            if self._should_extract_type(table_resources):
                if self.prerequisite_service is not None:
                    self.prerequisite_service.ensure(
                        active_context,
                        table_resources,
                    )
                self.extraction_workflow.extract_tables(
                    active_context,
                    table_resources,
                )
        if "bundle" in active_context.resource_type:
            bundle_resources = self._filter_resources_for_type(
                active_resources,
                "bundle",
            )
            if self._should_extract_type(bundle_resources):
                self.extraction_workflow.extract_bundles(
                    active_context,
                    bundle_resources,
                )
        if "media" in active_context.resource_type:
            media_resources = self._filter_resources_for_type(
                active_resources,
                "media",
            )
            if self._should_extract_type(media_resources):
                self.extraction_workflow.extract_media(active_context, media_resources)

    def run_post_download(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        if context.extract_while_download:
            return
        self.run(context, resources)
