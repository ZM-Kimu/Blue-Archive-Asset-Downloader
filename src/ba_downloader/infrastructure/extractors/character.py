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
        self.__create_relation_file(
            self.context.version, self.context.region, relations
        )

    def get_excel_resources(self, resource: AssetCollection) -> AssetCollection:
        if not (searched := resource.search("path", "Excel")):
            raise LookupError("Excel not found, advanced search is unavailable now.")
        return searched

    def __extract_excel(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        scenario_db = self.__extract_scenario_db()
        extracted_paths = self.__extract_excel_bytes_files()
        excel_payloads = self.__load_excel_payloads(extracted_paths)

        self.__validate_relation_sources(
            scenario_db=scenario_db,
            extracted_payloads=excel_payloads,
        )

        char_profile = excel_payloads.get("localizecharprofileexceltable.bytes", [])
        char_excel = excel_payloads.get("characterexceltable.bytes", [])
        costume_excel = excel_payloads.get("costumeexceltable.bytes", [])
        shop_recruit = excel_payloads.get("shoprecruitexceltable.bytes", [])
        localize_gacha = excel_payloads.get("localizegachashopexceltable.bytes", [])
        return (
            scenario_db,
            char_profile,
            char_excel,
            costume_excel,
            shop_recruit,
            localize_gacha,
        )

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
                if (
                    lowered_name
                    in self.REQUIRED_BYTES_FILES + self.OPTIONAL_BYTES_FILES
                ):
                    excel_zip.extract(item_name, extract_dir)

        extracted_paths: dict[str, Path] = {}
        for file_name in self.REQUIRED_BYTES_FILES + self.OPTIONAL_BYTES_FILES:
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
                payloads[file_name] = self.__normalize_excel_payload(
                    file_name,
                    json.loads(processed.data),
                )
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self.logger.warn(f"Failed to process {file_name}: {exc}")
        return payloads

    @staticmethod
    def __normalize_excel_payload(
        file_name: str,
        payload: Any,
    ) -> list[dict[str, Any]]:
        if isinstance(payload, list) and all(
            isinstance(item, dict) for item in payload
        ):
            return payload

        if isinstance(payload, dict):
            data_list = payload.get("DataList")
            if isinstance(data_list, list) and all(
                isinstance(item, dict) for item in data_list
            ):
                return data_list

        raise TypeError(
            f"Unexpected payload shape for {file_name}: expected list[dict] or {{'DataList': list[dict]}}."
        )

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
        costume_excel: list[dict[str, Any]],
        shop_recruit: list[dict[str, Any]],
        localize_gacha: list[dict[str, Any]],
    ) -> list[CharacterData]:
        hash_map: dict[int, CharacterData] = {}
        self.__apply_profile_data(hash_map, char_profile)
        self.__apply_excel_data(hash_map, char_excel)
        if self.context.region == "cn":
            self.__apply_costume_data(hash_map, costume_excel)
            self.__apply_cn_recruit_data(hash_map, shop_recruit, localize_gacha)
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
                cv=self.__first_non_empty(
                    profile,
                    "CharacterVoiceJp",
                    "CharacterVoiceKr",
                ),
                age=self.__str_to_int(
                    self.__first_non_empty(
                        profile,
                        "CharacterAgeJp",
                        "CharacterAgeKr",
                    )
                ),
                height=self.__str_to_int(
                    self.__first_non_empty(
                        profile,
                        "CharHeightJp",
                        "CharHeightKr",
                    )
                ),
                birthday=profile.get("BirthDay", ""),
                illustrator=self.__first_non_empty(
                    profile,
                    "IllustratorNameJp",
                    "IllustratorNameKr",
                ),
            )
            hash_map[data.character_id] = data

    @staticmethod
    def __first_non_empty(payload: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = payload.get(key, "")
            if value:
                return str(value)
        return ""

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

    def __apply_costume_data(
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
            self.__add_file_aliases(data, self.__collect_costume_aliases(costume))
            hash_map[data.character_id] = data

    def __collect_costume_aliases(self, costume: dict[str, Any]) -> set[str]:
        aliases: set[str] = set()

        texture_alias = self.__split_path_to_name(str(costume.get("TextureDir", "")))
        if texture_alias and texture_alias != "Null":
            aliases.add(texture_alias)

        model_name = str(costume.get("ModelPrefabName", ""))
        if model_name and not model_name.endswith("_Original"):
            aliases.add(model_name)

        return aliases

    def __apply_cn_recruit_data(
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

            recruit_names = self.__extract_recruit_names(subtitle)
            if not recruit_names:
                continue

            if len(info_character_ids) == 1:
                self.__append_names(hash_map, info_character_ids[0], {recruit_names[0]})
                continue

            for char_id, recruit_name in zip(
                info_character_ids, recruit_names, strict=False
            ):
                self.__append_names(hash_map, char_id, {recruit_name})

    def __extract_recruit_names(self, subtitle: str) -> list[str]:
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

    def __append_names(
        self,
        hash_map: dict[int, CharacterData],
        char_id: int,
        names: set[str],
    ) -> None:
        data = hash_map.get(char_id, CharacterData(char_id))
        merged_names = set(data.names or [])
        merged_names.update(name for name in names if name)
        data.names = sorted(merged_names)
        hash_map[char_id] = data

    @staticmethod
    def __normalize_lookup_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def __add_file_aliases(self, char_data: CharacterData, aliases: set[str]) -> None:
        valid_aliases = {alias for alias in aliases if alias and alias != "Null"}
        if not valid_aliases:
            return
        if char_data.file_name is None:
            char_data.file_name = set()
        char_data.file_name.update(valid_aliases)

    def __apply_scenario_data(
        self,
        hash_map: dict[int, CharacterData],
        scenario_db: list[dict[str, Any]],
    ) -> None:
        for scenario in scenario_db:
            scene_data = scenario.get("Bytes", {})
            if not isinstance(scene_data, dict):
                continue

            file_name = self.__split_path_to_name(
                str(scene_data.get("SmallPortrait", ""))
            )
            name_no_underline = file_name.replace("_", "")
            if not file_name:
                continue

            scenario_names = self.__collect_scenario_names(scene_data)
            if self.__apply_existing_scenario_mapping(
                hash_map,
                scenario_names,
                file_name,
                name_no_underline,
            ):
                continue

            self.__register_unmatched_scenario(
                hash_map,
                scene_data,
                scenario_names,
                file_name,
                name_no_underline,
            )

    def __apply_existing_scenario_mapping(
        self,
        hash_map: dict[int, CharacterData],
        scenario_names: set[str],
        file_name: str,
        name_no_underline: str,
    ) -> bool:
        normalized_scenario_names = {
            self.__normalize_lookup_token(name) for name in scenario_names if name
        }
        normalized_file_name = self.__normalize_lookup_token(file_name)
        normalized_file_name_no_underline = self.__normalize_lookup_token(
            name_no_underline
        )
        prefix_candidates: list[CharacterData] = []

        for char_data in hash_map.values():
            normalized_names = {
                self.__normalize_lookup_token(name)
                for name in (char_data.names or [])
                if name
            }
            if normalized_scenario_names and normalized_names.intersection(
                normalized_scenario_names
            ):
                self.__add_file_aliases(char_data, {file_name, name_no_underline})
                return True

            normalized_aliases = {
                self.__normalize_lookup_token(alias)
                for alias in (char_data.file_name or set())
                if alias
            }
            if any(
                normalized_alias
                and (
                    normalized_file_name.startswith(normalized_alias)
                    or normalized_alias.startswith(normalized_file_name)
                    or normalized_file_name_no_underline.startswith(normalized_alias)
                    or normalized_alias.startswith(normalized_file_name_no_underline)
                )
                for normalized_alias in normalized_aliases
            ):
                self.__add_file_aliases(char_data, {file_name, name_no_underline})
                return True

            dev_prefix = self.__normalize_lookup_token(
                char_data.dev_name.split("_", 1)[0]
            )
            if dev_prefix and (
                normalized_file_name.startswith(dev_prefix)
                or normalized_file_name_no_underline.startswith(dev_prefix)
            ):
                prefix_candidates.append(char_data)

        if len(prefix_candidates) == 1:
            self.__add_file_aliases(
                prefix_candidates[0], {file_name, name_no_underline}
            )
            return True

        return False

    def __register_unmatched_scenario(
        self,
        hash_map: dict[int, CharacterData],
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
        hash_map[normalized_id] = CharacterData(
            normalized_id,
            dev_name=file_name,
            names=sorted(scenario_names),
            file_name={file_name, name_no_underline},
        )

    def __collect_scenario_names(
        self,
        scene_data: dict[str, Any],
    ) -> set[str]:
        names: set[str] = set()
        for key in scene_data:
            if not key.lower().startswith("name"):
                continue
            name = scene_data.get(key, "")
            if name:
                names.add(name)
            if name and key.lower() == "namejp":
                names.add(self.__convert_kana_to_hepburn(str(name)))
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
        relation_path = (
            active_context.region.upper() + CharacterNameRelation.RELATION_NAME
        )
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
        relation_file = (
            active_context.region.upper() + CharacterNameRelation.RELATION_NAME
        )
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
            if self.__match_character(
                char, char_names, file_names, keywords, char_attr
            ):
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
