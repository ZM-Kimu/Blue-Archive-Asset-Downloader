from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.relation import RelationBuilderPort
from ba_downloader.infrastructure.extraction.character.relation_composer import (
    CharacterRelationComposer,
    CharacterRelationCompositionProfile,
    build_default_character_relation_composition_profile,
)
from ba_downloader.infrastructure.extraction.character.relation_sources import (
    CharacterRelationSourceLoader,
    CharacterRelationSourceProfile,
)
from ba_downloader.infrastructure.extraction.character.relation_store import (
    CharacterRelationFileStore,
    CharacterRelationSearchIndex,
)
from ba_downloader.infrastructure.extraction.character.table_source import (
    CharacterTableSource,
    TableExtractorCharacterTableSource,
    TableProfileFactory,
)
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger

RelationSourceProfileFactory = Callable[
    [RuntimeContext],
    CharacterRelationSourceProfile,
]
RelationCompositionProfileFactory = Callable[
    [RuntimeContext],
    CharacterRelationCompositionProfile,
]


def build_default_relation_source_profile(
    context: RuntimeContext,
) -> CharacterRelationSourceProfile:
    raise ValueError(
        f"No character relation source profile was configured for region '{context.region}'."
    )


def build_default_relation_composition_profile(
    context: RuntimeContext,
) -> CharacterRelationCompositionProfile:
    _ = context
    return build_default_character_relation_composition_profile()


class CharacterNameRelation(RelationBuilderPort):
    def __init__(
        self,
        context: RuntimeContext,
        logger: LoggerPort | None = None,
        table_source: CharacterTableSource | None = None,
        source_loader: CharacterRelationSourceLoader | None = None,
        composer: CharacterRelationComposer | None = None,
        relation_store: CharacterRelationFileStore | None = None,
        search_index: CharacterRelationSearchIndex | None = None,
        table_profile_factory: TableProfileFactory | None = None,
        relation_source_profile_factory: RelationSourceProfileFactory = (
            build_default_relation_source_profile
        ),
        relation_composition_profile_factory: RelationCompositionProfileFactory = (
            build_default_relation_composition_profile
        ),
    ) -> None:
        self.context = context
        self.logger = logger or ConsoleLogger()
        self._relation_source_profile_factory = relation_source_profile_factory
        self._relation_composition_profile_factory = (
            relation_composition_profile_factory
        )
        self._table_source: CharacterTableSource = table_source or cast(
            CharacterTableSource,
            TableExtractorCharacterTableSource.from_context(
                context,
                self.logger,
                table_profile_factory=table_profile_factory,
            ),
        )
        self._source_loader = source_loader or CharacterRelationSourceLoader(
            self._table_source,
            self.logger,
        )
        self._composer = composer or CharacterRelationComposer()
        self._relation_store = relation_store or CharacterRelationFileStore(self.logger)
        self._search_index = search_index or CharacterRelationSearchIndex()

    def build(self, context: RuntimeContext | None = None) -> None:
        self.context = context or self.context
        self.logger.info("Extracting necessary data...")
        sources = self._source_loader.load(
            self._relation_source_profile_factory(self.context)
        )
        self.logger.info("Relating character data...")
        relations = self._composer.compose(
            sources,
            self._relation_composition_profile_factory(self.context),
        )
        relation_path = self._relation_store.save(
            self.context.version,
            self.context.region,
            relations,
        )
        self.logger.info(f"Character relation file saved to {relation_path}.")

    def get_excel_resources(self, resource: AssetCollection) -> AssetCollection:
        if not (searched := resource.search("path", "Excel")):
            raise LookupError("Excel not found, advanced search is unavailable now.")
        return searched

    def verify_relation_file(self, context: RuntimeContext | None = None) -> bool:
        return self._relation_store.verify(context or self.context)

    def search(
        self,
        context: RuntimeContext | None = None,
        search_terms: list[str] | None = None,
    ) -> list[str]:
        active_context = context or self.context
        normalized_terms = search_terms or []
        try:
            relation = self._relation_store.load(active_context)
            return self._search_index.search(relation, normalized_terms)
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
