from collections.abc import Callable

from ba_downloader.application.contracts.commands import AssetOperationOptions
from ba_downloader.application.profiles import RegionProfile
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.asset_filter import (
    RESOURCE_FIELDS,
    AssetFilterService,
)
from ba_downloader.domain.services.resource_query import ResourceQueryService


class DownloadAssetsUseCase:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        *,
        workflow_profile: RegionProfile,
        cancellation: CancellationPort | None = None,
        character_index_builder_factory: Callable[
            [ExecutionContext], CharacterIndexBuilderPort
        ]
        | None = None,
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.workflow_profile = workflow_profile
        self.cancellation = cancellation or NeverCancelled()
        self.character_index_builder_factory = character_index_builder_factory

    def run(
        self, context: ExecutionContext, options: AssetOperationOptions
    ) -> ExecutionContext:
        self.cancellation.raise_if_cancelled()
        catalog = self.provider.load_catalog(context)
        self.cancellation.raise_if_cancelled()
        catalog_resources = catalog.resources
        resources = catalog_resources
        self.workflow_profile.catalog_metadata.on_catalog_loaded(
            catalog.context,
            resources,
        )
        if options.asset_filter.predicates:
            entries = None
            if any(
                predicate.field not in RESOURCE_FIELDS
                for predicate in options.asset_filter.predicates
            ):
                if self.character_index_builder_factory is None:
                    raise LookupError(
                        "Character filters require a configured character index."
                    )
                builder = self.character_index_builder_factory(catalog.context)
                if not builder.verify_index_file(catalog.context):
                    raise LookupError(
                        "Character index is missing or stale. Run "
                        f"`ba-downloader index build --region {catalog.context.region}` first."
                    )
                entries = builder.load(catalog.context).entries
            resources = AssetFilterService.apply(
                resources,
                options.asset_filter,
                character_entries=entries,
            )
        direct = ResourceQueryService.filter_type(resources, options.resources)
        self.downloader.verify_and_download(
            direct,
            catalog.context,
            concurrency=options.concurrency,
        )
        self.cancellation.raise_if_cancelled()
        return catalog.context
