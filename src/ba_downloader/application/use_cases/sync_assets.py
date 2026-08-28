from collections.abc import Callable
from dataclasses import dataclass

from ba_downloader.application.contracts.commands import AssetOperationOptions
from ba_downloader.application.profiles import (
    RegionProfile,
    SyncExtractionMode,
)
from ba_downloader.application.use_cases.character_index_search import (
    CharacterIndexSearchService,
)
from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.extraction import ExtractionReport
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.asset_filter import (
    RESOURCE_FIELDS,
    AssetFilterService,
)
from ba_downloader.domain.services.resource_query import ResourceQueryService


@dataclass(frozen=True, slots=True)
class SyncAssetsResult:
    context: ExecutionContext
    extraction: ExtractionReport


class SyncAssetsUseCase:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        extract_service: ExtractAssetsUseCase,
        schema_preparation: SchemaPreparationPort,
        character_index_builder_factory: Callable[
            [ExecutionContext], CharacterIndexBuilderPort
        ],
        logger: LoggerPort,
        *,
        workflow_profile: RegionProfile,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.extract_service = extract_service
        self.schema_preparation = schema_preparation
        self.character_index_builder_factory = character_index_builder_factory
        self.logger = logger
        self.workflow_profile = workflow_profile
        self.cancellation = cancellation or NeverCancelled()
        self.character_index_search = CharacterIndexSearchService(
            character_index_builder_factory,
            logger,
            workflow_profile.settings_policy,
        )

    def _prepare_schema(self, context: ExecutionContext) -> None:
        self.schema_preparation.prepare(context)

    def _search_resource(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        options: AssetOperationOptions,
        schema_prepared: bool,
    ) -> AssetCollection:
        if options.asset_filter.predicates:
            character_entries = None
            if any(
                predicate.field not in RESOURCE_FIELDS
                for predicate in options.asset_filter.predicates
            ):
                character_entries, _ = self.character_index_search.resolve_sync_entries(
                    resources,
                    context,
                    schema_preparation=self.schema_preparation,
                    downloader=self.downloader,
                    schema_prepared=schema_prepared,
                    concurrency=options.concurrency,
                )
            return AssetFilterService.apply(
                resources,
                options.asset_filter,
                character_entries=character_entries,
            )
        return resources

    def _filter_and_download(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        options: AssetOperationOptions,
    ) -> AssetCollection:
        direct = ResourceQueryService.filter_type(resources, options.resources)
        self.downloader.verify_and_download(
            direct, context, concurrency=options.concurrency
        )
        return direct

    def run(
        self, context: ExecutionContext, options: AssetOperationOptions
    ) -> SyncAssetsResult:
        self.cancellation.raise_if_cancelled()
        capabilities = self.provider.get_capabilities()
        if not capabilities.supports_sync:
            raise LookupError(
                f"Sync is temporarily unavailable for region '{context.region}'."
            )
        catalog = self.provider.load_catalog(context)
        self.cancellation.raise_if_cancelled()
        active_context = catalog.context
        catalog_resources = catalog.resources
        resources = catalog_resources
        self.workflow_profile.catalog_metadata.on_catalog_loaded(
            active_context,
            resources,
        )

        if self.workflow_profile.prepares_schema_for_sync:
            self._prepare_schema(active_context)
            self.cancellation.raise_if_cancelled()

        if options.asset_filter.predicates:
            resources = self._search_resource(
                resources,
                active_context,
                options,
                self.workflow_profile.prepares_schema_for_sync,
            )

        filtered = self._filter_and_download(
            resources,
            active_context,
            options,
        )
        self.cancellation.raise_if_cancelled()
        if self.workflow_profile.sync_extraction_mode is SyncExtractionMode.direct:
            extraction = self.extract_service.run(active_context, options, filtered)
        else:
            extraction = self.extract_service.run_post_download(
                active_context, options, filtered
            )
        self.cancellation.raise_if_cancelled()
        return SyncAssetsResult(active_context, extraction)
