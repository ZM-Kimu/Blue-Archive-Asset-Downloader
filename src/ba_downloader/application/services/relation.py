from collections.abc import Callable

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import FlatbufferWorkflowPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.relation import RelationBuilderPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort


class RelationService:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        flatbuffer_workflow: FlatbufferWorkflowPort,
        runtime_asset_preparer: RuntimeAssetPreparerPort,
        relation_builder_factory: Callable[[RuntimeContext], RelationBuilderPort],
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.flatbuffer_workflow = flatbuffer_workflow
        self.runtime_asset_preparer = runtime_asset_preparer
        self.relation_builder_factory = relation_builder_factory

    def build(self, context: RuntimeContext) -> RuntimeContext:
        if not self.provider.get_capabilities().supports_relation_build:
            raise LookupError(
                f"Relation build is temporarily unavailable for region '{context.region}'."
            )

        catalog = self.provider.load_catalog(context)
        active_context = catalog.context
        self.runtime_asset_preparer.prepare(active_context)
        self.flatbuffer_workflow.dump(active_context)
        self.flatbuffer_workflow.compile(active_context)

        relation_builder = self.relation_builder_factory(active_context)
        excel_resources = relation_builder.get_excel_resources(catalog.resources)
        self.downloader.verify_and_download(excel_resources, active_context)
        relation_builder.build(active_context)
        return active_context
