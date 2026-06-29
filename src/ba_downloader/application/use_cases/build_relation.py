from collections.abc import Callable

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.relation import RelationBuilderPort


class BuildRelationUseCase:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        schema_preparation: SchemaPreparationPort,
        relation_builder_factory: Callable[[RuntimeContext], RelationBuilderPort],
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.schema_preparation = schema_preparation
        self.relation_builder_factory = relation_builder_factory

    def build(self, context: RuntimeContext) -> RuntimeContext:
        if not self.provider.get_capabilities().supports_relation_build:
            raise LookupError(
                f"Relation build is temporarily unavailable for region '{context.region}'."
            )

        catalog = self.provider.load_catalog(context)
        active_context = catalog.context
        self.schema_preparation.prepare(active_context)

        relation_builder = self.relation_builder_factory(active_context)
        excel_resources = relation_builder.get_excel_resources(catalog.resources)
        self.downloader.verify_and_download(excel_resources, active_context)
        relation_builder.build(active_context)
        return active_context
