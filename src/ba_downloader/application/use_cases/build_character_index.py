from collections.abc import Callable

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.region import RegionProvider


class BuildCharacterIndexUseCase:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        schema_preparation: SchemaPreparationPort,
        character_index_builder_factory: Callable[
            [RuntimeContext], CharacterIndexBuilderPort
        ],
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.schema_preparation = schema_preparation
        self.character_index_builder_factory = character_index_builder_factory

    def build(self, context: RuntimeContext) -> RuntimeContext:
        if not self.provider.get_capabilities().supports_character_index_build:
            raise LookupError(
                f"Character index build is temporarily unavailable for region '{context.region}'."
            )

        catalog = self.provider.load_catalog(context)
        active_context = catalog.context
        self.schema_preparation.prepare(active_context)

        character_index_builder = self.character_index_builder_factory(active_context)
        excel_resources = character_index_builder.get_excel_resources(catalog.resources)
        self.downloader.verify_and_download(excel_resources, active_context)
        character_index_builder.build(active_context)
        return active_context
