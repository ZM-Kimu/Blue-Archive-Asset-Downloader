from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.character import CharacterIndexEntry
from ba_downloader.domain.models.region_profile import RegionSettingsPolicy
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.logging import LoggerPort

CharacterIndexBuilderFactory = Callable[[RuntimeContext], CharacterIndexBuilderPort]


@dataclass(frozen=True, slots=True)
class CharacterIndexSearchResult:
    keywords: list[str]
    schema_prepared: bool


class CharacterIndexSearchService:
    def __init__(
        self,
        character_index_builder_factory: CharacterIndexBuilderFactory,
        logger: LoggerPort,
        settings_policy: RegionSettingsPolicy,
    ) -> None:
        self.character_index_builder_factory = character_index_builder_factory
        self.logger = logger
        self.settings_policy = settings_policy

    def resolve_sync_keywords(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
        *,
        schema_preparation: SchemaPreparationPort,
        downloader: ResourceDownloaderPort,
        schema_prepared: bool,
    ) -> CharacterIndexSearchResult:
        if not context.advanced_search:
            return CharacterIndexSearchResult([], schema_prepared)

        self.logger.info("Preparing for advanced search...")
        character_index_builder = self.character_index_builder_factory(context)
        active_schema_prepared = schema_prepared
        if not character_index_builder.verify_index_file(context):
            if not active_schema_prepared:
                schema_preparation.prepare(context)
                active_schema_prepared = True
            excel_resource = character_index_builder.get_excel_resources(resources)
            downloader.verify_and_download(excel_resource, context)
            character_index_builder.build(context)

        return CharacterIndexSearchResult(
            character_index_builder.search(context, list(context.advanced_search)),
            active_schema_prepared,
        )

    def resolve_existing_keywords(self, context: RuntimeContext) -> list[str]:
        if not context.advanced_search:
            return []

        character_index_builder = self.character_index_builder_factory(context)
        self._require_current_index(character_index_builder, context)
        return character_index_builder.search(context, list(context.advanced_search))

    def resolve_sync_entries(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
        *,
        schema_preparation: SchemaPreparationPort,
        downloader: ResourceDownloaderPort,
        schema_prepared: bool,
    ) -> tuple[list[CharacterIndexEntry], bool]:
        builder, active_schema_prepared = self._prepare_sync_builder(
            resources,
            context,
            schema_preparation=schema_preparation,
            downloader=downloader,
            schema_prepared=schema_prepared,
        )
        return builder.load(context).entries, active_schema_prepared

    def resolve_existing_entries(
        self, context: RuntimeContext
    ) -> list[CharacterIndexEntry]:
        builder = self.character_index_builder_factory(context)
        self._require_current_index(builder, context)
        return builder.load(context).entries

    def _prepare_sync_builder(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
        *,
        schema_preparation: SchemaPreparationPort,
        downloader: ResourceDownloaderPort,
        schema_prepared: bool,
    ) -> tuple[CharacterIndexBuilderPort, bool]:
        builder = self.character_index_builder_factory(context)
        active_schema_prepared = schema_prepared
        if not builder.verify_index_file(context):
            if not active_schema_prepared:
                schema_preparation.prepare(context)
                active_schema_prepared = True
            downloader.verify_and_download(
                builder.get_excel_resources(resources), context
            )
            builder.build(context)
        return builder, active_schema_prepared

    def _require_current_index(
        self,
        character_index_builder: CharacterIndexBuilderPort,
        context: RuntimeContext,
    ) -> None:
        if character_index_builder.verify_index_file(context):
            return

        command_args = self._format_character_index_command_args(context)
        raise LookupError(
            "Character index file is missing or does not match the current "
            "resource version. Run "
            f"`ba-downloader index build {command_args}` "
            "or "
            f"`ba-downloader assets sync {command_args} --filter name~<keyword>` "
            "before filtering extracted assets by character fields."
        )

    def _format_character_index_command_args(self, context: RuntimeContext) -> str:
        return f"--region {context.region}"
