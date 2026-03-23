from collections.abc import Callable

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import FlatbufferWorkflowPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.relation import RelationBuilderPort


class RelationService:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        flatbuffer_workflow: FlatbufferWorkflowPort,
        relation_builder_factory: Callable[[RuntimeContext], RelationBuilderPort],
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.flatbuffer_workflow = flatbuffer_workflow
        self.relation_builder_factory = relation_builder_factory

    def build(self, context: RuntimeContext) -> RuntimeContext:
        self.flatbuffer_workflow.dump(context)
        self.flatbuffer_workflow.compile(context)

        catalog = self.provider.load_catalog(context)
        relation_builder = self.relation_builder_factory(catalog.context)
        excel_resources = relation_builder.get_excel_resources(catalog.resources)
        self.downloader.verify_and_download(excel_resources, catalog.context)
        relation_builder.build(catalog.context)
        return catalog.context
