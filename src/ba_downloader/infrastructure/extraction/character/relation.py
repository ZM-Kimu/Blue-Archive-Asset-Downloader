from __future__ import annotations

import json
from typing import cast

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.relation import RelationBuilderPort
from ba_downloader.infrastructure.extraction.character.relation_composer import (
    CharacterRelationComposer,
)
from ba_downloader.infrastructure.extraction.character.relation_sources import (
    CharacterRelationSourceLoader,
)
from ba_downloader.infrastructure.extraction.character.relation_store import (
    CharacterRelationFileStore,
    CharacterRelationSearchIndex,
)
from ba_downloader.infrastructure.extraction.character.table_source import (
    CharacterTableSource,
    TableExtractorCharacterTableSource,
)
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger


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
    ) -> None:
        self.context = context
        self.logger = logger or ConsoleLogger()
        self._table_source: CharacterTableSource = table_source or cast(
            CharacterTableSource,
            TableExtractorCharacterTableSource.from_context(
                context,
                self.logger,
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
        sources = self._source_loader.load(self.context)
        self.logger.info("Relating character data...")
        relations = self._composer.compose(sources, self.context.region)
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
