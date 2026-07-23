from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.character.table_source import (
    CharacterTableSource,
)
from ba_downloader.infrastructure.storage import TableDatabase

DB_NAME = "ExcelDB.db"


@dataclass(frozen=True)
class CharacterIndexSources:
    scenario_db: list[dict[str, Any]]
    char_profile: list[dict[str, Any]]
    char_excel: list[dict[str, Any]]
    costume_excel: list[dict[str, Any]]
    shop_recruit: list[dict[str, Any]]
    localize_gacha: list[dict[str, Any]]

    def as_tuple(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        return (
            self.scenario_db,
            self.char_profile,
            self.char_excel,
            self.costume_excel,
            self.shop_recruit,
            self.localize_gacha,
        )


@dataclass(frozen=True, slots=True)
class DatabaseIndexSourceSpec:
    scenario_table: str
    character_table: str
    profile_table: str
    costume_table: str | None = None
    shop_recruit_table: str | None = None
    localize_gacha_table: str | None = None

    @property
    def required_sources(self) -> tuple[str, str, str]:
        return (self.scenario_table, self.character_table, self.profile_table)


class CharacterIndexSourceProfile(Protocol):
    def load(
        self,
        loader: CharacterIndexSourceLoader,
    ) -> CharacterIndexSources: ...


class CharacterIndexSourceLoader:
    def __init__(
        self,
        table_source: CharacterTableSource,
        logger: LoggerPort,
    ) -> None:
        self._table_source = table_source
        self._logger = logger

    def load(
        self,
        source_profile: CharacterIndexSourceProfile,
    ) -> CharacterIndexSources:
        return source_profile.load(self)

    def load_database_index_sources(
        self,
        spec: DatabaseIndexSourceSpec,
    ) -> CharacterIndexSources:
        scenario_db = self.extract_db_table(spec.scenario_table)
        char_excel = self.extract_db_bytes_payloads(spec.character_table)
        char_profile = self.extract_db_bytes_payloads(spec.profile_table)
        costume_excel = self.extract_optional_db_bytes_payloads(spec.costume_table)
        shop_recruit = self.extract_optional_db_bytes_payloads(spec.shop_recruit_table)
        localize_gacha = self.extract_optional_db_bytes_payloads(
            spec.localize_gacha_table
        )

        self.validate_index_sources(
            source_payloads={
                spec.scenario_table: scenario_db,
                spec.character_table: char_excel,
                spec.profile_table: char_profile,
            },
            required_sources=spec.required_sources,
        )

        return CharacterIndexSources(
            scenario_db=scenario_db,
            char_profile=char_profile,
            char_excel=char_excel,
            costume_excel=costume_excel,
            shop_recruit=shop_recruit,
            localize_gacha=localize_gacha,
        )

    def extract_db_table(self, table_name: str) -> list[dict[str, Any]]:
        tables = self._table_source.process_db_file(
            str(Path(self._table_source.table_file_folder) / DB_NAME),
            table_name,
        )
        if not tables:
            return []
        return TableDatabase.convert_to_list_dict(tables[0])

    def extract_db_bytes_payloads(self, table_name: str) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for row in self.extract_db_table(table_name):
            payload = row.get("Bytes", {})
            if isinstance(payload, dict) and payload:
                payloads.append(payload)
        return payloads

    def extract_optional_db_bytes_payloads(
        self,
        table_name: str | None,
    ) -> list[dict[str, Any]]:
        if not table_name:
            return []
        try:
            return self.extract_db_bytes_payloads(table_name)
        except LookupError:
            return []

    def validate_index_sources(
        self,
        *,
        source_payloads: dict[str, list[dict[str, Any]]],
        required_sources: tuple[str, ...],
    ) -> None:
        missing_sources: list[str] = []
        for source_name in required_sources:
            if not source_payloads.get(source_name):
                missing_sources.append(source_name)

        if len(missing_sources) == len(required_sources):
            raise LookupError(
                "Character index build failed because all core index sources are missing."
            )

        if missing_sources:
            missing_text = ", ".join(missing_sources)
            self._logger.warn(
                f"Some character index sources are missing or invalid: {missing_text}. "
                "Character index might be incomplete."
            )
