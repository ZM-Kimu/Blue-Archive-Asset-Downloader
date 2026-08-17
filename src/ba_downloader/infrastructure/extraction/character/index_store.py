from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ba_downloader.domain.models.character import CharacterIndex, CharacterIndexEntry
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort

INDEX_SCHEMA_VERSION = 1
INDEX_RELATIVE_PATH = Path("indexes", "characters.json")


class CharacterIndexFileStore:
    def __init__(self, logger: LoggerPort) -> None:
        self._logger = logger

    def save(
        self,
        context: ExecutionContext | RuntimeContext,
        data: list[CharacterIndexEntry],
        *,
        expected_character_ids: set[int] | None = None,
    ) -> Path:
        region, platform, version = self._metadata(context)
        if not version:
            raise ValueError("Character index requires a resolved resource version.")
        index_path = self._index_file_name(context)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, staging_name = tempfile.mkstemp(
            prefix=f".{index_path.name}.",
            suffix=".tmp",
            dir=index_path.parent,
        )
        staging_path = Path(staging_name)
        payload = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "metadata": {
                "region": region,
                "platform": platform,
                "resource_version": version,
            },
            "entries": [self._serialize_entry(entry) for entry in data],
        }
        try:
            with os.fdopen(descriptor, "w", encoding="utf8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            staged_index = self.load_path(staging_path, context)
            if expected_character_ids is not None:
                actual_ids = {entry.character_id for entry in staged_index.entries}
                missing_ids = expected_character_ids - actual_ids
                if missing_ids:
                    preview = ", ".join(str(item) for item in sorted(missing_ids)[:10])
                    raise ValueError(
                        "Character index is missing successfully decoded profile "
                        f"characters: {preview}."
                    )
            os.replace(staging_path, index_path)
        except BaseException:
            staging_path.unlink(missing_ok=True)
            raise
        return index_path.resolve()

    def verify(self, context: ExecutionContext | RuntimeContext) -> bool:
        try:
            self.load_path(self._index_file_name(context), context)
        except (
            FileNotFoundError,
            OSError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
        ):
            return False
        return True

    def load(self, context: ExecutionContext | RuntimeContext) -> CharacterIndex:
        return self.load_path(self._index_file_name(context), context)

    def load_path(
        self,
        index_file: str | Path,
        context: ExecutionContext | RuntimeContext,
    ) -> CharacterIndex:
        payload = self._read_payload(Path(index_file), context)
        metadata = payload["metadata"]
        entries = payload["entries"]
        assert isinstance(metadata, dict)
        assert isinstance(entries, list)
        parsed_entries = [self._parse_entry(entry) for entry in entries]
        self._validate_entries(parsed_entries)
        return CharacterIndex(
            str(metadata["resource_version"]),
            parsed_entries,
        )

    def _read_payload(
        self,
        index_path: Path,
        context: ExecutionContext | RuntimeContext,
    ) -> dict[str, Any]:
        if not index_path.is_file():
            raise FileNotFoundError("Character index file does not exist.")
        with index_path.open(encoding="utf8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Character index payload must be a JSON object.")
        if payload.get("schema_version") != INDEX_SCHEMA_VERSION:
            raise ValueError(
                f"Character index schema_version must be {INDEX_SCHEMA_VERSION}."
            )
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("Character index payload must contain metadata.")
        expected_region, expected_platform, expected_version = self._metadata(context)
        expected = {
            "region": expected_region,
            "platform": expected_platform,
            "resource_version": expected_version,
        }
        if metadata != expected:
            raise ValueError(
                "Character index metadata does not match execution context."
            )
        if not isinstance(payload.get("entries"), list):
            raise ValueError("Character index payload must contain an 'entries' list.")
        if set(payload) != {"schema_version", "metadata", "entries"}:
            raise ValueError("Character index payload contains unknown fields.")
        return payload

    @staticmethod
    def _serialize_entry(entry: CharacterIndexEntry) -> dict[str, object]:
        return {
            "character_id": entry.character_id,
            "dev_name": entry.dev_name,
            "names": sorted(entry.names or []),
            "file_aliases": sorted(entry.file_aliases or set()),
            "cv": entry.cv,
            "age": entry.age,
            "height": entry.height,
            "birthday": entry.birthday,
            "illustrator": entry.illustrator,
            "school_en": entry.school_en,
            "club_en": entry.club_en,
        }

    @staticmethod
    def _parse_entry(payload: object) -> CharacterIndexEntry:
        if not isinstance(payload, dict):
            raise ValueError("Character index entry must be a JSON object.")
        expected_fields = {
            "character_id",
            "dev_name",
            "names",
            "file_aliases",
            "cv",
            "age",
            "height",
            "birthday",
            "illustrator",
            "school_en",
            "club_en",
        }
        if set(payload) != expected_fields:
            raise ValueError("Character index entry fields are invalid.")
        names = payload["names"]
        aliases = payload["file_aliases"]
        if not isinstance(names, list) or not all(
            isinstance(item, str) for item in names
        ):
            raise ValueError("Character index entry names must be a string list.")
        if not isinstance(aliases, list) or not all(
            isinstance(item, str) for item in aliases
        ):
            raise ValueError(
                "Character index entry file_aliases must be a string list."
            )
        integer_fields = ("character_id", "age", "height")
        if any(
            not isinstance(payload[field], int) or isinstance(payload[field], bool)
            for field in integer_fields
        ):
            raise ValueError("Character index integer fields must contain integers.")
        string_fields = (
            "dev_name",
            "cv",
            "birthday",
            "illustrator",
            "school_en",
            "club_en",
        )
        if any(not isinstance(payload[field], str) for field in string_fields):
            raise ValueError("Character index string fields must contain strings.")
        return CharacterIndexEntry(
            character_id=payload["character_id"],
            dev_name=payload["dev_name"],
            names=list(names),
            file_aliases=set(aliases),
            cv=payload["cv"],
            age=payload["age"],
            height=payload["height"],
            birthday=payload["birthday"],
            illustrator=payload["illustrator"],
            school_en=payload["school_en"],
            club_en=payload["club_en"],
        )

    @staticmethod
    def _validate_entries(entries: list[CharacterIndexEntry]) -> None:
        if not entries:
            raise ValueError("Character index must contain at least one entry.")
        character_ids = [entry.character_id for entry in entries]
        if any(character_id == 0 for character_id in character_ids):
            raise ValueError("Character index character_id values must be non-zero.")
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("Character index character_id values must be unique.")

    @staticmethod
    def _metadata(
        context: ExecutionContext | RuntimeContext,
    ) -> tuple[str, str, str]:
        if isinstance(context, ExecutionContext):
            return (
                context.region,
                context.platform,
                context.resource_version or "",
            )
        return context.region, context.platform, context.version

    @staticmethod
    def _index_file_name(context: ExecutionContext | RuntimeContext) -> Path:
        if isinstance(context, ExecutionContext):
            return context.workspace.character_index
        return Path(context.work_dir) / INDEX_RELATIVE_PATH


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
