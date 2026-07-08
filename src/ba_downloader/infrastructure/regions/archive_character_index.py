from __future__ import annotations

from ba_downloader.infrastructure.extraction.character.index_sources import (
    CharacterIndexSourceLoader,
    CharacterIndexSources,
)


class ArchiveCharacterIndexSourceProfile:
    def load(
        self,
        loader: CharacterIndexSourceLoader,
    ) -> CharacterIndexSources:
        return loader.load_archive_index_sources()
