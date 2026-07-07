from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
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
    CharacterIndexSearcher,
)
from ba_downloader.infrastructure.extraction.character.table_source import (
    CharacterTableSource,
    TableExtractorCharacterTableSource,
    TableProfileFactory,
)
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger

CharacterIndexSourceProfileFactory = Callable[
    [RuntimeContext],
    CharacterIndexSourceProfile,
]
CharacterIndexCompositionProfileFactory = Callable[
    [RuntimeContext],
    CharacterIndexCompositionProfile,
]


def build_default_character_index_source_profile(
    context: RuntimeContext,
) -> CharacterIndexSourceProfile:
    raise ValueError(
        f"No character index source profile was configured for region '{context.region}'."
    )


def build_default_character_index_composition_profile(
    context: RuntimeContext,
) -> CharacterIndexCompositionProfile:
    _ = context
    return build_default_composer_profile()


class CharacterIndexBuilder(CharacterIndexBuilderPort):
    def __init__(
        self,
        context: RuntimeContext,
        logger: LoggerPort | None = None,
        table_source: CharacterTableSource | None = None,
        source_loader: CharacterIndexSourceLoader | None = None,
        composer: CharacterIndexComposer | None = None,
        index_store: CharacterIndexFileStore | None = None,
        search_index: CharacterIndexSearcher | None = None,
        table_profile_factory: TableProfileFactory | None = None,
        character_index_source_profile_factory: CharacterIndexSourceProfileFactory = (
            build_default_character_index_source_profile
        ),
        character_index_composition_profile_factory: CharacterIndexCompositionProfileFactory = (
            build_default_character_index_composition_profile
        ),
    ) -> None:
        self.context = context
        self.logger = logger or ConsoleLogger()
        self._character_index_source_profile_factory = (
            character_index_source_profile_factory
        )
        self._character_index_composition_profile_factory = (
            character_index_composition_profile_factory
        )
        self._table_source: CharacterTableSource = table_source or cast(
            CharacterTableSource,
            TableExtractorCharacterTableSource.from_context(
                context,
                self.logger,
                table_profile_factory=table_profile_factory,
            ),
        )
        self._source_loader = source_loader or CharacterIndexSourceLoader(
            self._table_source,
            self.logger,
        )
        self._composer = composer or CharacterIndexComposer()
        self._index_store = index_store or CharacterIndexFileStore(self.logger)
        self._search_index = search_index or CharacterIndexSearcher()

    def build(self, context: RuntimeContext | None = None) -> None:
        self.context = context or self.context
        self.logger.info("Extracting necessary data...")
        sources = self._source_loader.load(
            self._character_index_source_profile_factory(self.context)
        )
        self.logger.info("Building character index entries...")
        entries = self._composer.compose(
            sources,
            self._character_index_composition_profile_factory(self.context),
        )
        index_path = self._index_store.save(
            self.context.version,
            self.context.region,
            entries,
        )
        self.logger.info(f"Character index file saved to {index_path}.")

    def get_excel_resources(self, resource: AssetCollection) -> AssetCollection:
        if not (searched := resource.search("path", "Excel")):
            raise LookupError("Excel not found, advanced search is unavailable now.")
        return searched

    def verify_index_file(self, context: RuntimeContext | None = None) -> bool:
        return self._index_store.verify(context or self.context)

    def search(
        self,
        context: RuntimeContext | None = None,
        search_terms: list[str] | None = None,
    ) -> list[str]:
        active_context = context or self.context
        normalized_terms = search_terms or []
        try:
            index = self._index_store.load(active_context)
            return self._search_index.search(index, normalized_terms)
        except (
            FileNotFoundError,
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise LookupError(
                f"Search failed due to error {exc}. Retrying may solve the issue."
            ) from exc
