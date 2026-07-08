from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ba_downloader.domain.models.character import CharacterIndex, CharacterIndexEntry
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort

INDEX_NAME = "CharacterIndex.json"


class CharacterIndexFileStore:
    def __init__(
        self,
        logger: LoggerPort,
        index_name: str = INDEX_NAME,
    ) -> None:
        self._logger = logger
        self._index_name = index_name

    def save(
        self,
        version: str,
        region: str,
        data: list[CharacterIndexEntry],
    ) -> Path:
        normalized_region = region.upper()
        index_path = Path(normalized_region + self._index_name).resolve()
        with index_path.open("w", encoding="utf8") as file_handle:
            json.dump(
                asdict(CharacterIndex(normalized_region + version, data)),
                file_handle,
                indent=4,
                ensure_ascii=False,
                default=CharacterIndexEntry.serialize,
            )
        return index_path

    def verify(self, context: RuntimeContext) -> bool:
        index_path = self._index_file_name(context)
        try:
            with Path(index_path).open(encoding="utf8") as file_handle:
                payload = json.load(file_handle)
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
            return False
        return payload.get("version", "") == (context.region.upper() + context.version)

    def load(self, context: RuntimeContext) -> CharacterIndex:
        return self.load_path(self._index_file_name(context), context)

    def load_path(
        self,
        index_file: str | Path,
        context: RuntimeContext,
    ) -> CharacterIndex:
        index_path = Path(index_file)
        if not index_path.exists():
            raise FileNotFoundError("Character index file does not exist.")

        if not self.verify(context):
            self._logger.warn(
                "The character index version does not match the latest game version."
            )

        index = CharacterIndex("", [])
        with index_path.open(encoding="utf8") as file_handle:
            index_json = json.load(file_handle)
        entries = index_json.get("entries")
        if not isinstance(entries, list):
            raise ValueError("Character index payload must contain an 'entries' list.")
        index.version = index_json.get("version", "")
        for payload in entries:
            index.entries.append(CharacterIndexEntry(**payload))
        return index

    def _index_file_name(self, context: RuntimeContext) -> str:
        return context.region.upper() + self._index_name


class CharacterIndexSearcher:
    def search(
        self,
        index: CharacterIndex,
        search_terms: list[str],
    ) -> list[str]:
        search_keywords: list[str] = []
        keywords = [term.lower() for term in search_terms if "=" not in term]
        char_attr = self._parse_attribute_terms(search_terms)

        for char in index.entries:
            file_aliases = list(char.file_aliases or [])
            char_names = list(char.names or [])
            if self._match_character(
                char,
                char_names,
                file_aliases,
                keywords,
                char_attr,
            ):
                search_keywords.extend(file_aliases)
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
        char: CharacterIndexEntry,
        char_names: list[str],
        file_aliases: list[str],
        keywords: list[str],
        char_attr: dict[str, str],
    ) -> bool:
        lowered_names = [name.lower() for name in char_names]
        lowered_files = [file_alias.lower() for file_alias in file_aliases]
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
