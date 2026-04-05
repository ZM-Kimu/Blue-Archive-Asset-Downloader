from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pykakasi

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.character import CharacterData, CharacterRelation
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.relation import RelationBuilderPort
from ba_downloader.infrastructure.extractors.table import TableExtractor
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
from ba_downloader.infrastructure.storage import TableDatabase
from ba_downloader.shared.crypto.encryption import zip_password


class CharacterNameRelation(TableExtractor, RelationBuilderPort):
    EXCEL_NAME = "Excel.zip"
    DB_NAME = "ExcelDB.db"
    RELATION_NAME = "CharacterRelation.json"
    REQUIRED_BYTES_FILES = (
        "characterexceltable.bytes",
        "localizecharprofileexceltable.bytes",
    )
    REQUIRED_RELATION_SOURCES = (
        "ScenarioCharacterNameDBSchema",
        "characterexceltable.bytes",
        "localizecharprofileexceltable.bytes",
    )

    def __init__(
        self,
        context: RuntimeContext,
        logger: LoggerPort | None = None,
    ) -> None:
        self.context = context
        self.logger = logger or ConsoleLogger()
        super().__init__(
            str(Path(context.raw_dir) / "Table"),
            str(Path(context.temp_dir) / "Table"),
            str(Path(context.extract_dir) / "FlatData"),
            logger=self.logger,
        )
        self.kana_converter = pykakasi.kakasi()

    def __convert_kana_to_hepburn(self, kana: str) -> str:
        return "".join(item["hepburn"] for item in self.kana_converter.convert(kana))

    @staticmethod
    def __str_to_int(text: str, default: int = 0) -> int:
        return int(match.group()) if (match := re.search(r"\d+", text)) else default

    @staticmethod
    def __split_path_to_name(file_path: str, max_split: int = 2) -> str:
        return Path(file_path).name.split("_", max_split)[-1]

    def build(self, context: RuntimeContext | None = None) -> None:
        self.context = context or self.context
        self.logger.info("Extracting necessary data...")
        excel = self.__extract_excel()
        self.logger.info("Relating character data...")
        relations = self.__create_relation_list(*excel)
        self.__create_relation_file(self.context.version, self.context.region, relations)

    def get_excel_resources(self, resource: AssetCollection) -> AssetCollection:
        if not (searched := resource.search("path", "Excel")):
            raise LookupError("Excel not found, advanced search is unavailable now.")
        return searched

    def __extract_excel(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        scenario_db = self.__extract_scenario_db()
        extracted_paths = self.__extract_excel_bytes_files()
        excel_payloads = self.__load_excel_payloads(extracted_paths)

        self.__validate_relation_sources(
            scenario_db=scenario_db,
            extracted_payloads=excel_payloads,
        )

        char_profile = excel_payloads.get("localizecharprofileexceltable.bytes", [])
        char_excel = excel_payloads.get("characterexceltable.bytes", [])
        return scenario_db, char_profile, char_excel

    def __extract_scenario_db(self) -> list[dict[str, Any]]:
        tables = self._process_db_file(
            str(Path(self.table_file_folder) / self.DB_NAME),
            "ScenarioCharacterNameDBSchema",
        )
        if not tables:
            return []
        return TableDatabase.convert_to_list_dict(tables[0])

    def __extract_excel_bytes_files(self) -> dict[str, Path]:
        excel_folder = Path(self.table_file_folder)
        extract_dir = Path(self.extract_folder) / self.EXCEL_NAME.removesuffix(".zip")
        extract_dir.mkdir(parents=True, exist_ok=True)

        with ZipFile(excel_folder / self.EXCEL_NAME, "r") as excel_zip:
            excel_zip.setpassword(zip_password(self.EXCEL_NAME))
            for item_name in excel_zip.namelist():
                lowered_name = item_name.lower()
                if lowered_name in self.REQUIRED_BYTES_FILES:
                    excel_zip.extract(item_name, extract_dir)

        extracted_paths: dict[str, Path] = {}
        for file_name in self.REQUIRED_BYTES_FILES:
            matches = list(extract_dir.rglob(file_name))
            if matches:
                extracted_paths[file_name] = matches[0]
        return extracted_paths

    def __load_excel_payloads(
        self,
        extracted_paths: dict[str, Path],
    ) -> dict[str, list[dict[str, Any]]]:
        payloads: dict[str, list[dict[str, Any]]] = {}
        for file_name, file_path in extracted_paths.items():
            try:
                with file_path.open("rb") as file_handle:
                    processed = self._process_zip_file(
                        self.EXCEL_NAME,
                        file_name,
                        file_handle.read(),
                        detect_type=True,
                    )
                payloads[file_name] = json.loads(processed.data)
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self.logger.warn(f"Failed to process {file_name}: {exc}")
        return payloads

    def __validate_relation_sources(
        self,
        *,
        scenario_db: list[dict[str, Any]],
        extracted_payloads: dict[str, list[dict[str, Any]]],
    ) -> None:
        missing_sources: list[str] = []
        if not scenario_db:
            missing_sources.append("ScenarioCharacterNameDBSchema")
        for file_name in self.REQUIRED_BYTES_FILES:
            if not extracted_payloads.get(file_name):
                missing_sources.append(file_name)

        if len(missing_sources) == len(self.REQUIRED_RELATION_SOURCES):
            raise LookupError(
                "Relation build failed because all core relation sources are missing."
            )

        if missing_sources:
            missing_text = ", ".join(missing_sources)
            self.logger.warn(
                f"Some relation sources are missing or invalid: {missing_text}. "
                "Name relation might be incomplete."
            )

    def __create_relation_list(
        self,
        scenario_db: list[dict[str, Any]],
        char_profile: list[dict[str, Any]],
        char_excel: list[dict[str, Any]],
    ) -> list[CharacterData]:
        hash_map: dict[int, CharacterData] = {}
        self.__apply_profile_data(hash_map, char_profile)
        self.__apply_excel_data(hash_map, char_excel)
        self.__apply_scenario_data(hash_map, scenario_db)
        return list(hash_map.values())

    def __apply_profile_data(
        self,
        hash_map: dict[int, CharacterData],
        char_profile: list[dict[str, Any]],
    ) -> None:
        for profile in char_profile:
            names = self.__collect_profile_names(profile)
            data = CharacterData(
                profile.get("CharacterId", 0),
                names=list(names),
                cv=profile.get("CharacterVoiceJp", ""),
                age=self.__str_to_int(profile.get("CharacterAgeJp", "")),
                height=self.__str_to_int(profile.get("CharHeightJp", "")),
                birthday=profile.get("BirthDay", ""),
                illustrator=profile.get("IllustratorNameJp", ""),
            )
            hash_map[data.character_id] = data

    def __collect_profile_names(self, profile: dict[str, Any]) -> set[str]:
        names: set[str] = set()
        for key in profile:
            if not key.lower().startswith(("fullname", "familyname", "personalname")):
                continue
            name = profile.get(key, "")
            if name:
                names.add(name)
            if name and key.lower() in ("familynamerubyjp", "personalnamejp"):
                names.add(self.__convert_kana_to_hepburn(str(name)))
        return names

    @staticmethod
    def __apply_excel_data(
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

    def __apply_scenario_data(
        self,
        hash_map: dict[int, CharacterData],
        scenario_db: list[dict[str, Any]],
    ) -> None:
        for scenario in scenario_db:
            scene_data = scenario.get("Bytes", {})
            if not isinstance(scene_data, dict):
                continue

            file_name = self.__split_path_to_name(str(scene_data.get("SmallPortrait", "")))
            name_no_underline = file_name.replace("_", "")
            jp_name = str(scene_data.get("NameJP", ""))
            if not (file_name and jp_name):
                continue

            if self.__apply_existing_scenario_mapping(
                hash_map,
                scene_data,
                file_name,
                name_no_underline,
                jp_name,
            ):
                continue

            self.__register_unmatched_scenario(
                hash_map,
                scene_data,
                file_name,
                name_no_underline,
                jp_name,
            )

    def __apply_existing_scenario_mapping(
        self,
        hash_map: dict[int, CharacterData],
        scene_data: dict[str, Any],
        file_name: str,
        name_no_underline: str,
        jp_name: str,
    ) -> bool:
        for char_data in hash_map.values():
            char_names = char_data.names or []
            if not char_data.dev_name:
                continue
            if any(jp_name in name.lower() for name in char_names) or char_data.dev_name in file_name:
                if char_data.file_name:
                    char_data.file_name.update({file_name, name_no_underline})
                else:
                    char_data.file_name = {file_name, name_no_underline}
                return True
        return False

    def __register_unmatched_scenario(
        self,
        hash_map: dict[int, CharacterData],
        scene_data: dict[str, Any],
        file_name: str,
        name_no_underline: str,
        jp_name: str,
    ) -> None:
        if file_name == "Null":
            return
        char_id = scene_data.get("CharacterName", 0)
        if not char_id:
            return

        names = self.__collect_scenario_names(scene_data, jp_name)
        normalized_id = -char_id if char_id in hash_map else char_id
        hash_map[normalized_id] = CharacterData(
            normalized_id,
            dev_name=file_name,
            names=list(names),
            file_name={file_name, name_no_underline},
        )

    def __collect_scenario_names(
        self,
        scene_data: dict[str, Any],
        jp_name: str,
    ) -> set[str]:
        names: set[str] = set()
        for key in scene_data:
            if not key.lower().startswith("name"):
                continue
            name = scene_data.get(key, "")
            if name:
                names.add(name)
        if jp_name:
            names.add(self.__convert_kana_to_hepburn(jp_name))
        return names

    def __create_relation_file(
        self,
        version: str,
        region: str,
        data: list[CharacterData],
    ) -> None:
        region = region.upper()
        with open(region + self.RELATION_NAME, "w", encoding="utf8") as file_handle:
            json.dump(
                asdict(CharacterRelation(region + version, data)),
                file_handle,
                indent=4,
                ensure_ascii=False,
                default=CharacterData.serialize,
            )

    def verify_relation_file(self, context: RuntimeContext | None = None) -> bool:
        active_context = context or self.context
        relation_path = active_context.region.upper() + CharacterNameRelation.RELATION_NAME
        try:
            with open(relation_path, encoding="utf8") as file_handle:
                payload = json.load(file_handle)
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
            return False
        return payload.get("version", "") == (
            active_context.region.upper() + active_context.version
        )

    def search(
        self,
        context: RuntimeContext | None = None,
        search_terms: list[str] | None = None,
    ) -> list[str]:
        active_context = context or self.context
        normalized_terms = search_terms or []
        relation_file = active_context.region.upper() + CharacterNameRelation.RELATION_NAME
        try:
            relation = self.__load_relation_file(relation_file, active_context)
            return self.__search_keywords(relation, normalized_terms)
        except (
            FileNotFoundError,
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise LookupError(
                f"Search failed due to error {exc}. Retrying may solve the issue."
            ) from exc

    def __load_relation_file(
        self,
        relation_file: str,
        context: RuntimeContext,
    ) -> CharacterRelation:
        if not Path(relation_file).exists():
            raise FileNotFoundError("Character relation file does not exist.")

        if not self.verify_relation_file(context):
            self.logger.warn(
                "The character relation version does not match the latest game version."
            )

        relation = CharacterRelation("", [])
        with open(relation_file, encoding="utf8") as file_handle:
            relation_json = json.load(file_handle)
        relation.version = relation_json.get("version", "")
        for payload in relation_json.get("relations", []):
            relation.relations.append(CharacterData(**payload))
        return relation

    def __search_keywords(
        self,
        relation: CharacterRelation,
        search_terms: list[str],
    ) -> list[str]:
        search_keywords: list[str] = []
        keywords = [term.lower() for term in search_terms if "=" not in term]
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

        for char in relation.relations:
            file_names = list(char.file_name or [])
            char_names = list(char.names or [])
            if self.__match_character(char, char_names, file_names, keywords, char_attr):
                search_keywords.extend(file_names)
                if char.dev_name:
                    search_keywords.append(char.dev_name)

        return [keyword for keyword in search_keywords if keyword]

    @staticmethod
    def __match_character(
        char: CharacterData,
        char_names: list[str],
        file_names: list[str],
        keywords: list[str],
        char_attr: dict[str, str],
    ) -> bool:
        lowered_names = [name.lower() for name in char_names]
        lowered_files = [file_name.lower() for file_name in file_names]
        return any(
            [
                any(keyword in lowered_names for keyword in keywords),
                any(keyword in lowered_files for keyword in keywords),
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
