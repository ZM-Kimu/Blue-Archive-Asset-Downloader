from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from zipfile import ZipFile

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.character.table_source import (
    CharacterTableSource,
)
from ba_downloader.infrastructure.schema.crypto import zip_password
from ba_downloader.infrastructure.storage import TableDatabase

EXCEL_NAME = "Excel.zip"
DB_NAME = "ExcelDB.db"
REQUIRED_BYTES_FILES = (
    "characterexceltable.bytes",
    "localizecharprofileexceltable.bytes",
)
OPTIONAL_BYTES_FILES = (
    "costumeexceltable.bytes",
    "shoprecruitexceltable.bytes",
    "localizegachashopexceltable.bytes",
)
REQUIRED_RELATION_SOURCES = (
    "ScenarioCharacterNameDBSchema",
    "characterexceltable.bytes",
    "localizecharprofileexceltable.bytes",
)


@dataclass(frozen=True)
class CharacterRelationSources:
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
class DatabaseRelationSourceSpec:
    scenario_table: str
    character_table: str
    profile_table: str

    @property
    def required_sources(self) -> tuple[str, str, str]:
        return (self.scenario_table, self.character_table, self.profile_table)


class CharacterRelationSourceProfile(Protocol):
    def load(
        self,
        loader: CharacterRelationSourceLoader,
    ) -> CharacterRelationSources: ...


class CharacterRelationSourceLoader:
    def __init__(
        self,
        table_source: CharacterTableSource,
        logger: LoggerPort,
    ) -> None:
        self._table_source = table_source
        self._logger = logger

    def load(
        self,
        source_profile: CharacterRelationSourceProfile,
    ) -> CharacterRelationSources:
        return source_profile.load(self)

    def load_archive_relation_sources(self) -> CharacterRelationSources:
        scenario_db = self.extract_scenario_db()
        extracted_paths = self.extract_excel_bytes_files()
        excel_payloads = self.load_excel_payloads(extracted_paths)

        self.validate_relation_sources(
            source_payloads={
                "ScenarioCharacterNameDBSchema": scenario_db,
                **excel_payloads,
            },
            required_sources=REQUIRED_RELATION_SOURCES,
        )

        return CharacterRelationSources(
            scenario_db=scenario_db,
            char_profile=excel_payloads.get("localizecharprofileexceltable.bytes", []),
            char_excel=excel_payloads.get("characterexceltable.bytes", []),
            costume_excel=excel_payloads.get("costumeexceltable.bytes", []),
            shop_recruit=excel_payloads.get("shoprecruitexceltable.bytes", []),
            localize_gacha=excel_payloads.get("localizegachashopexceltable.bytes", []),
        )

    def load_database_relation_sources(
        self,
        spec: DatabaseRelationSourceSpec,
    ) -> CharacterRelationSources:
        scenario_db = self.extract_db_table(spec.scenario_table)
        char_excel = self.extract_db_bytes_payloads(spec.character_table)
        char_profile = self.extract_db_bytes_payloads(spec.profile_table)

        self.validate_relation_sources(
            source_payloads={
                spec.scenario_table: scenario_db,
                spec.character_table: char_excel,
                spec.profile_table: char_profile,
            },
            required_sources=spec.required_sources,
        )

        return CharacterRelationSources(
            scenario_db=scenario_db,
            char_profile=char_profile,
            char_excel=char_excel,
            costume_excel=[],
            shop_recruit=[],
            localize_gacha=[],
        )

    def extract_scenario_db(self) -> list[dict[str, Any]]:
        return self.extract_db_table("ScenarioCharacterNameDBSchema")

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

    def extract_excel_bytes_files(self) -> dict[str, Path]:
        excel_folder = Path(self._table_source.table_file_folder)
        extract_dir = Path(self._table_source.extract_folder) / EXCEL_NAME.removesuffix(
            ".zip"
        )
        extract_dir.mkdir(parents=True, exist_ok=True)

        with ZipFile(excel_folder / EXCEL_NAME, "r") as excel_zip:
            excel_zip.setpassword(zip_password(EXCEL_NAME))
            for item_name in excel_zip.namelist():
                lowered_name = item_name.lower()
                if lowered_name in REQUIRED_BYTES_FILES + OPTIONAL_BYTES_FILES:
                    excel_zip.extract(item_name, extract_dir)

        extracted_paths: dict[str, Path] = {}
        for file_name in REQUIRED_BYTES_FILES + OPTIONAL_BYTES_FILES:
            matches = list(extract_dir.rglob(file_name))
            if matches:
                extracted_paths[file_name] = matches[0]
        return extracted_paths

    def load_excel_payloads(
        self,
        extracted_paths: dict[str, Path],
    ) -> dict[str, list[dict[str, Any]]]:
        payloads: dict[str, list[dict[str, Any]]] = {}
        for file_name, file_path in extracted_paths.items():
            try:
                with file_path.open("rb") as file_handle:
                    processed = self._table_source.process_zip_file(
                        EXCEL_NAME,
                        file_name,
                        file_handle.read(),
                        detect_type=True,
                    )
                payloads[file_name] = normalize_excel_payload(
                    file_name,
                    json.loads(processed.data),
                )
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._logger.warn(f"Failed to process {file_name}: {exc}")
        return payloads

    def validate_relation_sources(
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
                "Relation build failed because all core relation sources are missing."
            )

        if missing_sources:
            missing_text = ", ".join(missing_sources)
            self._logger.warn(
                f"Some relation sources are missing or invalid: {missing_text}. "
                "Name relation might be incomplete."
            )


def normalize_excel_payload(
    file_name: str,
    payload: Any,
) -> list[dict[str, Any]]:
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload

    if isinstance(payload, dict):
        data_list = payload.get("DataList")
        if isinstance(data_list, list) and all(
            isinstance(item, dict) for item in data_list
        ):
            return data_list

    raise TypeError(
        f"Unexpected payload shape for {file_name}: "
        "expected list[dict] or {'DataList': list[dict]}."
    )
