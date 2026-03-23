from collections.abc import Callable

from ba_downloader.application.services.extract import ExtractService
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import FlatbufferWorkflowPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.relation import RelationBuilderPort
from ba_downloader.domain.services.resource_query import ResourceQueryService


class SyncService:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        extract_service: ExtractService,
        flatbuffer_workflow: FlatbufferWorkflowPort,
        relation_builder_factory: Callable[[RuntimeContext], RelationBuilderPort],
        logger: LoggerPort,
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.extract_service = extract_service
        self.flatbuffer_workflow = flatbuffer_workflow
        self.relation_builder_factory = relation_builder_factory
        self.logger = logger

    def _dump_and_compile(self, context: RuntimeContext) -> None:
        self.flatbuffer_workflow.dump(context)
        self.flatbuffer_workflow.compile(context)

    def _search_resource(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
        dumped: bool,
    ) -> AssetCollection:
        keywords: list[str] = []
        relation_builder = self.relation_builder_factory(context)
        if context.advanced_search:
            self.logger.warn("Preparing for advanced search...")
            if not relation_builder.verify_relation_file(context):
                if not dumped:
                    self._dump_and_compile(context)
                    dumped = True
                excel_resource = relation_builder.get_excel_resources(resources)
                self.downloader.verify_and_download(excel_resource, context)
                relation_builder.build(context)

            keywords = relation_builder.search(
                context,
                list(context.advanced_search),
            )

        if context.search:
            keywords = list(context.search)

        if keywords:
            resources = ResourceQueryService.search_name(resources, keywords)

        return resources

    def _filter_and_download(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> None:
        filtered = ResourceQueryService.filter_type(resources, context.resource_type)
        self.downloader.verify_and_download(filtered, context)

    def run(self, context: RuntimeContext) -> RuntimeContext:
        capabilities = self.provider.get_capabilities()
        if not capabilities.supports_sync:
            raise LookupError(
                "Sync is temporarily unavailable for JP while the new download pipeline is being rebuilt."
            )
        if context.advanced_search and not capabilities.supports_advanced_search:
            raise LookupError(
                f"Advanced search is not supported for region '{context.region}'."
            )

        catalog = self.provider.load_catalog(context)
        active_context = catalog.context
        resources = catalog.resources

        if active_context.region == "gl":
            self._dump_and_compile(active_context)
            if active_context.search or active_context.advanced_search:
                resources = self._search_resource(resources, active_context, True)
            self._filter_and_download(resources, active_context)
            self.extract_service.run(active_context)
            return active_context

        if active_context.search or active_context.advanced_search:
            resources = self._search_resource(resources, active_context, False)

        self._filter_and_download(resources, active_context)
        self.extract_service.run_post_download(active_context)
        return active_context
