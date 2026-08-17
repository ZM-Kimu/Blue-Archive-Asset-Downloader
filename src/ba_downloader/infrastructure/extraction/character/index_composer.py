from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import pykakasi

from ba_downloader.domain.models.character import CharacterIndexEntry
from ba_downloader.infrastructure.extraction.character.index_sources import (
    CharacterIndexSources,
)
from ba_downloader.infrastructure.extraction.character.scenario_matching import (
    ScenarioMatchIndex,
)

_KANA_CONVERTER = pykakasi.kakasi()


@lru_cache(maxsize=4096)
def _convert_kana_to_hepburn(kana: str) -> str:
    return "".join(item["hepburn"] for item in _KANA_CONVERTER.convert(kana))


class CharacterIndexEnricher(Protocol):
    def enrich(
        self,
        composer: CharacterIndexComposer,
        hash_map: dict[int, CharacterIndexEntry],
        sources: CharacterIndexSources,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CharacterIndexCompositionProfile:
    romanize_japanese_names: bool
    enrichers: tuple[CharacterIndexEnricher, ...] = ()


def build_default_character_index_composition_profile() -> (
    CharacterIndexCompositionProfile
):
    return CharacterIndexCompositionProfile(romanize_japanese_names=False)


class CharacterIndexComposer:
    def compose(
        self,
        sources: CharacterIndexSources,
        profile: CharacterIndexCompositionProfile,
    ) -> list[CharacterIndexEntry]:
        hash_map: dict[int, CharacterIndexEntry] = {}
        self.apply_profile_data(hash_map, sources.char_profile, profile)
        self.apply_excel_data(hash_map, sources.char_excel)
        for enricher in profile.enrichers:
            enricher.enrich(self, hash_map, sources)
        self.apply_scenario_data(hash_map, sources.scenario_db, profile)
        searchable_entries: list[CharacterIndexEntry] = []
        remaining_entries: list[CharacterIndexEntry] = []
        for entry in hash_map.values():
            target = (
                searchable_entries
                if entry.names or entry.file_aliases
                else remaining_entries
            )
            target.append(entry)
        return searchable_entries + remaining_entries

    def convert_kana_to_hepburn(self, kana: str) -> str:
        return _convert_kana_to_hepburn(kana)

    @staticmethod
    def str_to_int(text: str, default: int = 0) -> int:
        return int(match.group()) if (match := re.search(r"\d+", text)) else default

    @staticmethod
    def split_path_to_name(file_path: str, max_split: int = 2) -> str:
        return Path(file_path).name.split("_", max_split)[-1]

    def apply_profile_data(
        self,
        hash_map: dict[int, CharacterIndexEntry],
        char_profile: list[dict[str, Any]],
        profile: CharacterIndexCompositionProfile,
    ) -> None:
        for character_profile in char_profile:
            names = self.collect_profile_names(character_profile, profile)
            data = CharacterIndexEntry(
                character_profile.get("CharacterId", 0),
                names=list(names),
                cv=first_non_empty(
                    character_profile,
                    "CharacterVoiceJp",
                    "CharacterVoiceKr",
                ),
                age=self.str_to_int(
                    first_non_empty(
                        character_profile,
                        "CharacterAgeJp",
                        "CharacterAgeKr",
                    )
                ),
                height=self.str_to_int(
                    first_non_empty(
                        character_profile,
                        "CharHeightJp",
                        "CharHeightKr",
                    )
                ),
                birthday=character_profile.get("BirthDay", ""),
                illustrator=first_non_empty(
                    character_profile,
                    "IllustratorNameJp",
                    "IllustratorNameKr",
                ),
            )
            hash_map[data.character_id] = data

    def collect_profile_names(
        self,
        profile: dict[str, Any],
        composition_profile: CharacterIndexCompositionProfile,
    ) -> set[str]:
        names: set[str] = set()
        for key in profile:
            lowered_key = key.lower()
            if not lowered_key.startswith(("fullname", "familyname", "personalname")):
                continue
            name = profile.get(key, "")
            if name:
                names.add(str(name))
            if (
                name
                and composition_profile.romanize_japanese_names
                and lowered_key.endswith("jp")
            ):
                romanized_name = self.convert_kana_to_hepburn(str(name))
                if romanized_name:
                    names.add(romanized_name)
        return names

    @staticmethod
    def apply_excel_data(
        hash_map: dict[int, CharacterIndexEntry],
        char_excel: list[dict[str, Any]],
    ) -> None:
        for excel_entry in char_excel:
            data = hash_map.get(
                excel_entry.get("Id", -1),
                CharacterIndexEntry(excel_entry.get("Id", 0)),
            )
            data.dev_name = excel_entry.get("DevName", "")
            data.school_en = excel_entry.get("School", "")
            data.club_en = excel_entry.get("Club", "")
            hash_map[data.character_id] = data

    def apply_costume_data(
        self,
        hash_map: dict[int, CharacterIndexEntry],
        costume_excel: list[dict[str, Any]],
    ) -> None:
        for costume in costume_excel:
            char_id = int(costume.get("CostumeGroupId", 0) or 0)
            if char_id <= 0:
                continue

            data = hash_map.get(char_id, CharacterIndexEntry(char_id))
            if not data.dev_name:
                data.dev_name = str(costume.get("DevName", ""))
            add_file_aliases(data, self.collect_costume_aliases(costume))
            hash_map[data.character_id] = data

    def collect_costume_aliases(self, costume: dict[str, Any]) -> set[str]:
        aliases: set[str] = set()

        texture_alias = self.split_path_to_name(str(costume.get("TextureDir", "")))
        if texture_alias and texture_alias != "Null":
            aliases.add(texture_alias)

        model_name = str(costume.get("ModelPrefabName", ""))
        if model_name and not model_name.endswith("_Original"):
            aliases.add(model_name)

        return aliases

    def apply_scenario_data(
        self,
        hash_map: dict[int, CharacterIndexEntry],
        scenario_db: list[dict[str, Any]],
        profile: CharacterIndexCompositionProfile,
    ) -> None:
        match_index = ScenarioMatchIndex(hash_map.values())
        for scenario in scenario_db:
            scene_data = scenario.get("Bytes", {})
            if not isinstance(scene_data, dict):
                continue

            file_name = self.split_path_to_name(
                str(scene_data.get("SmallPortrait", ""))
            )
            name_no_underline = file_name.replace("_", "")
            if not file_name:
                continue

            scenario_names = self.collect_scenario_names(scene_data, profile)
            if self.apply_existing_scenario_mapping(
                match_index,
                scenario_names,
                file_name,
                name_no_underline,
            ):
                continue

            self.register_unmatched_scenario(
                hash_map,
                match_index,
                scene_data,
                scenario_names,
                file_name,
                name_no_underline,
            )

    def apply_existing_scenario_mapping(
        self,
        match_index: ScenarioMatchIndex,
        scenario_names: set[str],
        file_name: str,
        name_no_underline: str,
    ) -> bool:
        file_candidates = {file_name, name_no_underline}
        if matched_char := match_index.match(scenario_names, file_candidates):
            add_names(matched_char, scenario_names)
            add_file_aliases(
                matched_char,
                {file_name, name_no_underline},
            )
            match_index.add_character(matched_char)
            return True

        return False

    def register_unmatched_scenario(
        self,
        hash_map: dict[int, CharacterIndexEntry],
        match_index: ScenarioMatchIndex,
        scene_data: dict[str, Any],
        scenario_names: set[str],
        file_name: str,
        name_no_underline: str,
    ) -> None:
        if file_name == "Null" or not scenario_names:
            return
        char_id = scene_data.get("CharacterName", 0)
        if not char_id:
            return

        normalized_id = -char_id if char_id in hash_map else char_id
        char_data = CharacterIndexEntry(
            normalized_id,
            dev_name=file_name,
            names=sorted(scenario_names),
            file_aliases={file_name, name_no_underline},
        )
        hash_map[normalized_id] = char_data
        match_index.add_character(char_data)

    def collect_scenario_names(
        self,
        scene_data: dict[str, Any],
        profile: CharacterIndexCompositionProfile,
    ) -> set[str]:
        names: set[str] = set()
        for key in scene_data:
            if not key.lower().startswith("name"):
                continue
            name = scene_data.get(key, "")
            if name:
                names.add(str(name))
            if name and profile.romanize_japanese_names and key.lower() == "namejp":
                names.add(self.convert_kana_to_hepburn(str(name)))
        return names


def first_non_empty(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key, "")
        if value:
            return str(value)
    return ""


def append_names(
    hash_map: dict[int, CharacterIndexEntry],
    char_id: int,
    names: set[str],
) -> None:
    data = hash_map.get(char_id, CharacterIndexEntry(char_id))
    add_names(data, names)
    hash_map[char_id] = data


def add_names(char_data: CharacterIndexEntry, names: set[str]) -> None:
    merged_names = set(char_data.names or [])
    merged_names.update(name for name in names if name)
    char_data.names = sorted(merged_names)


def add_file_aliases(char_data: CharacterIndexEntry, aliases: set[str]) -> None:
    valid_aliases = {alias for alias in aliases if alias and alias != "Null"}
    if not valid_aliases:
        return
    if char_data.file_aliases is None:
        char_data.file_aliases = set()
    char_data.file_aliases.update(valid_aliases)
