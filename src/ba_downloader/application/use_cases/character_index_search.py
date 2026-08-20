from __future__ import annotations

from collections.abc import Callable

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.character import CharacterIndexEntry
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region_profile import RegionSettingsPolicy
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.logging import LoggerPort

CharacterIndexBuilderFactory = Callable[[ExecutionContext], CharacterIndexBuilderPort]


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

    def resolve_sync_entries(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        *,
        schema_preparation: SchemaPreparationPort,
        downloader: ResourceDownloaderPort,
        schema_prepared: bool,
        concurrency: int,
    ) -> tuple[list[CharacterIndexEntry], bool]:
        builder, active_schema_prepared = self._prepare_sync_builder(
            resources,
            context,
            schema_preparation=schema_preparation,
            downloader=downloader,
            schema_prepared=schema_prepared,
            concurrency=concurrency,
        )
        return builder.load(context).entries, active_schema_prepared

    def resolve_existing_entries(
        self, context: ExecutionContext
    ) -> list[CharacterIndexEntry]:
        builder = self.character_index_builder_factory(context)
        self._require_current_index(builder, context)
        return builder.load(context).entries

    def _prepare_sync_builder(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        *,
        schema_preparation: SchemaPreparationPort,
        downloader: ResourceDownloaderPort,
        schema_prepared: bool,
        concurrency: int,
    ) -> tuple[CharacterIndexBuilderPort, bool]:
        builder = self.character_index_builder_factory(context)
        active_schema_prepared = schema_prepared
        if not builder.verify_index_file(context):
            schema_snapshot = None
            if not active_schema_prepared:
                schema_snapshot = schema_preparation.prepare(context)
                active_schema_prepared = True
            downloader.verify_and_download(
                builder.get_excel_resources(resources),
                context,
                concurrency=concurrency,
            )
            builder.build(context, schema_snapshot=schema_snapshot)
        return builder, active_schema_prepared

    def _require_current_index(
        self,
        character_index_builder: CharacterIndexBuilderPort,
        context: ExecutionContext,
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

    def _format_character_index_command_args(self, context: ExecutionContext) -> str:
        return f"--region {context.region}"
