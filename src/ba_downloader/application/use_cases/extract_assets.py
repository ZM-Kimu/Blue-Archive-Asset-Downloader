from ba_downloader.application.contracts.commands import AssetOperationOptions
from ba_downloader.application.profiles import RegionProfile
from ba_downloader.application.use_cases.character_index_search import (
    CharacterIndexBuilderFactory,
    CharacterIndexSearchService,
)
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.extraction import ExtractionReport
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.extract import (
    AssetExtractionPort,
    ExtractionPrerequisitePort,
)
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.asset_filter import (
    RESOURCE_FIELDS,
    AssetFilterService,
)
from ba_downloader.domain.services.resource_query import ResourceQueryService


class ExtractAssetsUseCase:
    def __init__(
        self,
        extraction_workflow: AssetExtractionPort,
        logger: LoggerPort | None = None,
        *,
        provider: RegionProvider | None = None,
        character_index_builder_factory: CharacterIndexBuilderFactory | None = None,
        prerequisite_service: ExtractionPrerequisitePort | None = None,
        workflow_profile: RegionProfile,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.extraction_workflow = extraction_workflow
        self.logger = logger
        self.provider = provider
        self.prerequisite_service = prerequisite_service
        self.workflow_profile = workflow_profile
        self.cancellation = cancellation or NeverCancelled()
        self.character_index_search = (
            CharacterIndexSearchService(
                character_index_builder_factory,
                logger,
                workflow_profile.settings_policy,
            )
            if character_index_builder_factory is not None and logger is not None
            else None
        )

    def _resolve_search_resources(
        self,
        context: ExecutionContext,
        options: AssetOperationOptions,
    ) -> tuple[ExecutionContext, AssetCollection]:
        if self.provider is None:
            raise LookupError("Extract search requires a configured region provider.")

        capabilities = self.provider.get_capabilities()
        has_character_filters = any(
            predicate.field not in RESOURCE_FIELDS
            for predicate in options.asset_filter.predicates
        )
        if has_character_filters and not capabilities.supports_advanced_search:
            raise LookupError(
                f"Advanced search is not supported for region '{context.region}'."
            )

        catalog = self.provider.load_catalog(context)
        active_context = catalog.context
        self.workflow_profile.catalog_metadata.on_catalog_loaded(
            active_context,
            catalog.resources,
        )
        resources = self._filter_search_resources(
            catalog.resources, active_context, options
        )
        resources = ResourceQueryService.filter_type(
            resources,
            options.resources,
        )
        return active_context, ResourceQueryService.filter_existing(
            resources, active_context
        )

    def _filter_search_resources(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        options: AssetOperationOptions,
    ) -> AssetCollection:
        if options.asset_filter.predicates:
            entries = None
            if any(
                predicate.field not in RESOURCE_FIELDS
                for predicate in options.asset_filter.predicates
            ):
                if self.character_index_search is None:
                    raise LookupError(
                        "Character filters require a configured character index."
                    )
                entries = self.character_index_search.resolve_existing_entries(context)
            return AssetFilterService.apply(
                resources,
                options.asset_filter,
                character_entries=entries,
            )
        return resources

    def _resolve_table_metadata_resources(
        self,
        context: ExecutionContext,
    ) -> tuple[ExecutionContext, AssetCollection | None]:
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
        context: ExecutionContext,
        options: AssetOperationOptions,
        resources: AssetCollection | None = None,
    ) -> ExtractionReport:
        self.cancellation.raise_if_cancelled()
        active_context = context
        active_resources = resources
        if active_resources is None and options.asset_filter.predicates:
            active_context, active_resources = self._resolve_search_resources(
                active_context, options
            )

        if active_resources is not None and not active_resources:
            return ExtractionReport()

        reports: list[ExtractionReport] = []

        if options.resources.contains("table"):
            table_resources = self._filter_resources_for_type(
                active_resources,
                "table",
            )
            if table_resources is None:
                active_context, table_resources = (
                    self._resolve_table_metadata_resources(active_context)
                )
            if self._should_extract_type(table_resources):
                self.cancellation.raise_if_cancelled()
                if self.prerequisite_service is not None:
                    self.prerequisite_service.ensure(
                        active_context,
                        table_resources,
                    )
                reports.append(
                    self.extraction_workflow.extract_tables(
                        active_context,
                        table_resources,
                        concurrency=options.concurrency,
                    )
                )
                self.cancellation.raise_if_cancelled()
        if options.resources.contains("bundle"):
            bundle_resources = self._filter_resources_for_type(
                active_resources,
                "bundle",
            )
            if self._should_extract_type(bundle_resources):
                self.cancellation.raise_if_cancelled()
                reports.append(
                    self.extraction_workflow.extract_bundles(
                        active_context,
                        bundle_resources,
                        concurrency=options.concurrency,
                    )
                )
                self.cancellation.raise_if_cancelled()
        if options.resources.contains("media"):
            media_resources = self._filter_resources_for_type(
                active_resources,
                "media",
            )
            if self._should_extract_type(media_resources):
                self.cancellation.raise_if_cancelled()
                reports.append(
                    self.extraction_workflow.extract_media(
                        active_context,
                        media_resources,
                        concurrency=options.concurrency,
                    )
                )
                self.cancellation.raise_if_cancelled()
        return ExtractionReport.combine(*reports)

    def run_post_download(
        self,
        context: ExecutionContext,
        options: AssetOperationOptions,
        resources: AssetCollection | None = None,
    ) -> ExtractionReport:
        return self.run(context, options, resources)
