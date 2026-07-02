from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pykakasi

from ba_downloader.domain.models.character import CharacterData
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.character.relation_sources import (
    CharacterRelationSources,
)
from ba_downloader.infrastructure.extraction.character.scenario_matching import (
    ScenarioMatchIndex,
)


class CharacterRelationEnricher(Protocol):
    def enrich(
        self,
        composer: CharacterRelationComposer,
        hash_map: dict[int, CharacterData],
        sources: CharacterRelationSources,
    ) -> None: ...


class CnLegacyRelationEnricher:
    def enrich(
        self,
        composer: CharacterRelationComposer,
        hash_map: dict[int, CharacterData],
        sources: CharacterRelationSources,
    ) -> None:
        composer.apply_costume_data(hash_map, sources.costume_excel)
        composer.apply_cn_recruit_data(
            hash_map,
            sources.shop_recruit,
            sources.localize_gacha,
        )


@dataclass(frozen=True, slots=True)
class CharacterRelationCompositionProfile:
    romanize_japanese_names: bool
    enrichers: tuple[CharacterRelationEnricher, ...] = ()


def build_character_relation_composition_profile(
    context: RuntimeContext,
) -> CharacterRelationCompositionProfile:
    if context.region == "jp":
        return CharacterRelationCompositionProfile(romanize_japanese_names=True)
    if context.region == "cn":
        return CharacterRelationCompositionProfile(
            romanize_japanese_names=False,
            enrichers=(CnLegacyRelationEnricher(),),
        )
    return CharacterRelationCompositionProfile(romanize_japanese_names=False)


class CharacterRelationComposer:
    def __init__(self) -> None:
        self._kana_converter = pykakasi.kakasi()

    def compose(
        self,
        sources: CharacterRelationSources,
        profile: CharacterRelationCompositionProfile,
    ) -> list[CharacterData]:
        hash_map: dict[int, CharacterData] = {}
        self.apply_profile_data(hash_map, sources.char_profile, profile)
        self.apply_excel_data(hash_map, sources.char_excel)
        for enricher in profile.enrichers:
            enricher.enrich(self, hash_map, sources)
        self.apply_scenario_data(hash_map, sources.scenario_db, profile)
        return list(hash_map.values())

    def convert_kana_to_hepburn(self, kana: str) -> str:
        return "".join(item["hepburn"] for item in self._kana_converter.convert(kana))

    @staticmethod
    def str_to_int(text: str, default: int = 0) -> int:
        return int(match.group()) if (match := re.search(r"\d+", text)) else default

    @staticmethod
    def split_path_to_name(file_path: str, max_split: int = 2) -> str:
        return Path(file_path).name.split("_", max_split)[-1]

    def apply_profile_data(
        self,
        hash_map: dict[int, CharacterData],
        char_profile: list[dict[str, Any]],
        profile: CharacterRelationCompositionProfile,
    ) -> None:
        for character_profile in char_profile:
            names = self.collect_profile_names(character_profile, profile)
            data = CharacterData(
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
        composition_profile: CharacterRelationCompositionProfile,
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
        hash_map: dict[int, CharacterData],
        char_excel: list[dict[str, Any]],
    ) -> None:
        for excel_entry in char_excel:
            data = hash_map.get(
                excel_entry.get("Id", -1),
                CharacterData(excel_entry.get("Id", 0)),
            )
            data.dev_name = excel_entry.get("DevName", "")
            data.school_en = excel_entry.get("School", "")
            data.club_en = excel_entry.get("Club", "")
            hash_map[data.character_id] = data

    def apply_costume_data(
        self,
        hash_map: dict[int, CharacterData],
        costume_excel: list[dict[str, Any]],
    ) -> None:
        for costume in costume_excel:
            char_id = int(costume.get("CostumeGroupId", 0) or 0)
            if char_id <= 0:
                continue

            data = hash_map.get(char_id, CharacterData(char_id))
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

    def apply_cn_recruit_data(
        self,
        hash_map: dict[int, CharacterData],
        shop_recruit: list[dict[str, Any]],
        localize_gacha: list[dict[str, Any]],
    ) -> None:
        subtitle_by_shop_id = {
            int(item.get("GachaShopId", 0) or 0): str(item.get("SubTitleKr", ""))
            for item in localize_gacha
            if item.get("SubTitleKr")
        }

        for recruit in shop_recruit:
            shop_id = int(recruit.get("Id", 0) or 0)
            subtitle = subtitle_by_shop_id.get(shop_id, "")
            if not subtitle:
                continue

            info_character_ids = [
                int(value)
                for value in recruit.get("InfoCharacterId", [])
                if int(value or 0) > 0
            ]
            if not info_character_ids:
                continue

            recruit_names = extract_recruit_names(subtitle)
            if not recruit_names:
                continue

            if len(info_character_ids) == 1:
                append_names(hash_map, info_character_ids[0], {recruit_names[0]})
                continue

            for char_id, recruit_name in zip(
                info_character_ids, recruit_names, strict=False
            ):
                append_names(hash_map, char_id, {recruit_name})

    def apply_scenario_data(
        self,
        hash_map: dict[int, CharacterData],
        scenario_db: list[dict[str, Any]],
        profile: CharacterRelationCompositionProfile,
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
            add_file_aliases(
                matched_char,
                {file_name, name_no_underline},
            )
            match_index.add_character(matched_char)
            return True

        return False

    def register_unmatched_scenario(
        self,
        hash_map: dict[int, CharacterData],
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
        char_data = CharacterData(
            normalized_id,
            dev_name=file_name,
            names=sorted(scenario_names),
            file_name={file_name, name_no_underline},
        )
        hash_map[normalized_id] = char_data
        match_index.add_character(char_data)

    def collect_scenario_names(
        self,
        scene_data: dict[str, Any],
        profile: CharacterRelationCompositionProfile,
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


def extract_recruit_names(subtitle: str) -> list[str]:
    names: list[str] = []
    for segment in re.split(r"[/\n]+", subtitle):
        normalized = segment.strip()
        if not normalized:
            continue

        normalized = normalized.replace("还可招募", "").strip()
        normalized = re.sub(r"^【[^】]+】", "", normalized).strip()
        normalized = re.sub(r"招募概率提升[\uFF01!]*$", "", normalized).strip()
        normalized = re.sub(r"^[123]★", "", normalized).strip()
        normalized = re.sub(r"\uFF08[123]★\uFF09$", "", normalized).strip()
        normalized = normalized.strip("\uff01! ")

        if normalized:
            names.append(normalized)
    return names


def append_names(
    hash_map: dict[int, CharacterData],
    char_id: int,
    names: set[str],
) -> None:
    data = hash_map.get(char_id, CharacterData(char_id))
    merged_names = set(data.names or [])
    merged_names.update(name for name in names if name)
    data.names = sorted(merged_names)
    hash_map[char_id] = data


def add_file_aliases(char_data: CharacterData, aliases: set[str]) -> None:
    valid_aliases = {alias for alias in aliases if alias and alias != "Null"}
    if not valid_aliases:
        return
    if char_data.file_name is None:
        char_data.file_name = set()
    char_data.file_name.update(valid_aliases)
