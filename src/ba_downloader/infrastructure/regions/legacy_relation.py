from __future__ import annotations

from ba_downloader.infrastructure.extraction.character.relation_sources import (
    CharacterRelationSourceLoader,
    CharacterRelationSources,
)


class LegacyArchiveRelationSourceProfile:
    def load(
        self,
        loader: CharacterRelationSourceLoader,
    ) -> CharacterRelationSources:
        return loader.load_archive_relation_sources()
