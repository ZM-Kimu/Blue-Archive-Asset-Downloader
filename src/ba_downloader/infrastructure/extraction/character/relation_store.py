from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ba_downloader.domain.models.character import CharacterData, CharacterRelation
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort

RELATION_NAME = "CharacterRelation.json"


class CharacterRelationFileStore:
    def __init__(
        self,
        logger: LoggerPort,
        relation_name: str = RELATION_NAME,
    ) -> None:
        self._logger = logger
        self._relation_name = relation_name

    def save(
        self,
        version: str,
        region: str,
        data: list[CharacterData],
    ) -> Path:
        normalized_region = region.upper()
        relation_path = Path(normalized_region + self._relation_name).resolve()
        with relation_path.open("w", encoding="utf8") as file_handle:
            json.dump(
                asdict(CharacterRelation(normalized_region + version, data)),
                file_handle,
                indent=4,
                ensure_ascii=False,
                default=CharacterData.serialize,
            )
        return relation_path

    def verify(self, context: RuntimeContext) -> bool:
        relation_path = self._relation_file_name(context)
        try:
            with Path(relation_path).open(encoding="utf8") as file_handle:
                payload = json.load(file_handle)
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
            return False
        return payload.get("version", "") == (context.region.upper() + context.version)

    def load(self, context: RuntimeContext) -> CharacterRelation:
        return self.load_path(self._relation_file_name(context), context)

    def load_path(
        self,
        relation_file: str | Path,
        context: RuntimeContext,
    ) -> CharacterRelation:
        relation_path = Path(relation_file)
        if not relation_path.exists():
            raise FileNotFoundError("Character relation file does not exist.")

        if not self.verify(context):
            self._logger.warn(
                "The character relation version does not match the latest game version."
            )

        relation = CharacterRelation("", [])
        with relation_path.open(encoding="utf8") as file_handle:
            relation_json = json.load(file_handle)
        relation.version = relation_json.get("version", "")
        for payload in relation_json.get("relations", []):
            relation.relations.append(CharacterData(**payload))
        return relation

    def _relation_file_name(self, context: RuntimeContext) -> str:
        return context.region.upper() + self._relation_name


class CharacterRelationSearchIndex:
    def search(
        self,
        relation: CharacterRelation,
        search_terms: list[str],
    ) -> list[str]:
        search_keywords: list[str] = []
        keywords = [term.lower() for term in search_terms if "=" not in term]
        char_attr = self._parse_attribute_terms(search_terms)

        for char in relation.relations:
            file_names = list(char.file_name or [])
            char_names = list(char.names or [])
            if self._match_character(
                char,
                char_names,
                file_names,
                keywords,
                char_attr,
            ):
                search_keywords.extend(file_names)
                if char.dev_name:
                    search_keywords.append(char.dev_name)

        return [keyword for keyword in search_keywords if keyword]

    @staticmethod
    def _parse_attribute_terms(search_terms: list[str]) -> dict[str, str]:
        char_attr = {}
        for keyword in search_terms:
            attr, _, value = keyword.lower().partition("=")
            if value and attr in {
                "cv",
                "age",
                "height",
                "birthday",
                "illustrator",
                "school",
                "club",
            }:
                char_attr[attr] = value
        return char_attr

    @staticmethod
    def _match_character(
        char: CharacterData,
        char_names: list[str],
        file_names: list[str],
        keywords: list[str],
        char_attr: dict[str, str],
    ) -> bool:
        lowered_names = [name.lower() for name in char_names]
        lowered_files = [file_name.lower() for file_name in file_names]
        lowered_dev_name = char.dev_name.lower()
        return any(
            [
                any(keyword in lowered_names for keyword in keywords),
                any(keyword in lowered_files for keyword in keywords),
                any(keyword in lowered_dev_name for keyword in keywords),
                (char.cv.lower() or "None") in char_attr.get("cv", "_"),
                str(char.age) == char_attr.get("age", -1),
                str(char.height) == char_attr.get("height", -1),
                (char.birthday.lower() or "None") in char_attr.get("birthday", "_"),
                (char.illustrator.lower() or "None")
                in char_attr.get("illustrator", "_"),
                (char.school_en.lower() or "None") in char_attr.get("school", "_"),
                (char.club_en.lower() or "None") in char_attr.get("club", "_"),
            ]
        )
