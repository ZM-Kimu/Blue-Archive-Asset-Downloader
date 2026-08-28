from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.character import CharacterIndex
from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.schema import PreparedSchemaSnapshot
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.character.index_composer import (
    CharacterIndexComposer,
    CharacterIndexCompositionProfile,
)
from ba_downloader.infrastructure.extraction.character.index_composer import (
    build_default_character_index_composition_profile as build_default_composer_profile,
)
from ba_downloader.infrastructure.extraction.character.index_sources import (
    CharacterIndexSourceLoader,
    CharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.extraction.character.index_store import (
    CharacterIndexFileStore,
)
from ba_downloader.infrastructure.extraction.character.table_source import (
    CharacterTableSource,
    TableExtractorCharacterTableSource,
    TableProfileFactory,
)
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger

CharacterIndexSourceProfileFactory = Callable[
    [ExecutionContext],
    CharacterIndexSourceProfile,
]
CharacterIndexCompositionProfileFactory = Callable[
    [ExecutionContext],
    CharacterIndexCompositionProfile,
]


def build_default_character_index_source_profile(
    context: ExecutionContext,
) -> CharacterIndexSourceProfile:
    raise ValueError(
        f"No character index source profile was configured for region '{context.region}'."
    )


def build_default_character_index_composition_profile(
    context: ExecutionContext,
) -> CharacterIndexCompositionProfile:
    _ = context
    return build_default_composer_profile()


class CharacterIndexBuilder(CharacterIndexBuilderPort):
    def __init__(
        self,
        logger: LoggerPort | None = None,
        table_source: CharacterTableSource | None = None,
        source_loader: CharacterIndexSourceLoader | None = None,
        composer: CharacterIndexComposer | None = None,
        index_store: CharacterIndexFileStore | None = None,
        table_profile_factory: TableProfileFactory | None = None,
        character_index_source_profile_factory: CharacterIndexSourceProfileFactory = (
            build_default_character_index_source_profile
        ),
        character_index_composition_profile_factory: CharacterIndexCompositionProfileFactory = (
            build_default_character_index_composition_profile
        ),
    ) -> None:
        self.logger = logger or ConsoleLogger()
        self._character_index_source_profile_factory = (
            character_index_source_profile_factory
        )
        self._character_index_composition_profile_factory = (
            character_index_composition_profile_factory
        )
        self._table_source = table_source
        self._table_profile_factory = table_profile_factory
        self._source_loader = source_loader
        self._composer = composer or CharacterIndexComposer()
        self._index_store = index_store or CharacterIndexFileStore(self.logger)

    def build(
        self,
        context: ExecutionContext,
        *,
        schema_snapshot: PreparedSchemaSnapshot | None = None,
        database_source_identity: DatabaseSourceIdentity | None = None,
    ) -> None:
        table_source = self._table_source or cast(
            CharacterTableSource,
            TableExtractorCharacterTableSource.from_context(
                context,
                self.logger,
                table_profile_factory=self._table_profile_factory,
                schema_snapshot=schema_snapshot,
                database_source_identity=database_source_identity,
            ),
        )
        source_loader = self._source_loader or CharacterIndexSourceLoader(
            table_source, self.logger
        )
        self.logger.info("Extracting necessary data...")
        sources = source_loader.load(
            self._character_index_source_profile_factory(context)
        )
        self.logger.info("Building character index entries...")
        entries = self._composer.compose(
            sources,
            self._character_index_composition_profile_factory(context),
        )
        expected_character_ids = {
            character_id
            for payload in sources.char_profile
            if isinstance(character_id := payload.get("CharacterId"), int)
            and not isinstance(character_id, bool)
            and character_id != 0
        }
        index_path = self._index_store.save(
            context,
            entries,
            expected_character_ids=expected_character_ids,
        )
        self.logger.info(f"Character index file saved to {index_path}.")

    def get_excel_resources(self, resource: AssetCollection) -> AssetCollection:
        searched = AssetCollection(
            item
            for item in resource
            if "exceldb" in item.path.casefold()
            or any(
                "exceldb" in include.casefold()
                for include in item.metadata.get("includes", [])
                if isinstance(include, str)
            )
        )
        if not searched:
            searched = resource.search("path", "Excel")
        if not searched:
            raise LookupError("Excel not found, advanced search is unavailable now.")
        return searched

    def verify_index_file(self, context: ExecutionContext) -> bool:
        return self._index_store.verify(context)

    def load(self, context: ExecutionContext) -> CharacterIndex:
        return self._index_store.load(context)
