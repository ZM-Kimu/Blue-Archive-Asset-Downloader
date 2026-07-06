from __future__ import annotations

from ba_downloader.infrastructure.extraction.character.relation_sources import (
    CharacterRelationSourceLoader,
    CharacterRelationSources,
    DatabaseRelationSourceSpec,
)

JP_DATABASE_RELATION_SOURCE_SPEC = DatabaseRelationSourceSpec(
    scenario_table="ScenarioCharacterNameDBSchema",
    character_table="CharacterDBSchema",
    profile_table="LocalizeCharProfileDBSchema",
)


class JpDbRelationSourceProfile:
    def load(
        self,
        loader: CharacterRelationSourceLoader,
    ) -> CharacterRelationSources:
        return loader.load_database_relation_sources(JP_DATABASE_RELATION_SOURCE_SPEC)
