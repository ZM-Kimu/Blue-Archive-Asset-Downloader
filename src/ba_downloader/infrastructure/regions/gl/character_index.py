from __future__ import annotations

from ba_downloader.infrastructure.extraction.character.index_sources import (
    CharacterIndexSourceLoader,
    CharacterIndexSources,
    DatabaseIndexSourceSpec,
)

GL_DATABASE_INDEX_SOURCE_SPEC = DatabaseIndexSourceSpec(
    scenario_table="ScenarioCharacterNameDBSchema",
    character_table="CharacterDBSchema",
    profile_table="LocalizeCharProfileDBSchema",
)


class GlDbCharacterIndexSourceProfile:
    def load(
        self,
        loader: CharacterIndexSourceLoader,
    ) -> CharacterIndexSources:
        return loader.load_database_index_sources(GL_DATABASE_INDEX_SOURCE_SPEC)
