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
        return "".join([kana["hepburn"] for kana in self.kana_converter.convert(kana)])

    def __str_to_int(self, text: str, default: int = 0) -> int:
        return (
            int(re_digit.group()) if (re_digit := re.search(r"\d+", text)) else default
        )

    def __split_path_to_name(self, file_path: str, max_split=2):
        return Path(file_path).name.split("_", max_split)[-1]

    def build(self, context: RuntimeContext | None = None) -> None:
        """Character extract entry."""
        self.context = context or self.context
        self.logger.info("Extracting necessary data...")
        excel = self.__extract_excel()
        self.logger.info("Relating character data...")
        relations = self.__create_relation_list(*excel)
        self.__create_relation_file(self.context.version, self.context.region, relations)

    def get_excel_resources(self, resource: AssetCollection) -> AssetCollection:
        """Get excel file item from resources."""
        if not (searched := resource.search("path", "Excel")):
            raise LookupError("Excel not found, advanced search is unavailable now.")
        return searched

    def __extract_excel(self) -> tuple[list, list, list]:
        scenario_db: list[dict] = []
        char_excel: list[dict] = []
        char_profile: list[dict] = []

        bytes_files = [
            "characterexceltable.bytes",
            "localizecharprofileexceltable.bytes",
        ]
        excel_folder = Path(self.table_file_folder)

        extract_dir = Path(self.extract_folder) / self.EXCEL_NAME.removesuffix(".zip")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with ZipFile(excel_folder / self.EXCEL_NAME, "r") as excel_zip:
            excel_zip.setpassword(zip_password(self.EXCEL_NAME))
            for item_name in excel_zip.namelist():
                if item_name.lower() in bytes_files:
                    excel_zip.extract(item_name, extract_dir)

        if tables := self._process_db_file(
            str(excel_folder / self.DB_NAME), "ScenarioCharacterNameDBSchema"
        ):
            scenario_db = TableDatabase.convert_to_list_dict(tables[0])

        b_file_paths = []
        for file_name in bytes_files:
            matches = list(extract_dir.rglob(file_name))
            if matches:
                b_file_paths.append(str(matches[0]))

        if len(bytes_files) == 2:
            for b_path, b_name in zip(b_file_paths, bytes_files, strict=True):
                with open(b_path, "rb") as f:
                    excel_data, _, _ = self._process_zip_file(b_name, f.read(), True)
                    if b_name == "characterexceltable.bytes":
                        char_excel = json.loads(excel_data)
                    else:
                        char_profile = json.loads(excel_data)

        if not (scenario_db and char_excel and char_profile):
            self.logger.warn("Some files went wrong. Name relation might be incomplete.")

        return scenario_db, char_profile, char_excel

    def __create_relation_list(
        self,
        scenario_db: list[dict[str, Any]],
        char_profile: list[dict[str, Any]],
        char_excel: list[dict],
    ) -> list[CharacterData]:
        hash_map: dict[int, CharacterData] = {}

        for char_p in char_profile:
            names: set = set()
            for key in char_p.keys():
                if key.lower().startswith(("fullname", "familyname", "personalname")):
                    if name := char_p.get(key, ""):
                        names.add(name)
                    if name and key.lower() in ("familynamerubyjp", "personalnamejp"):
                        names.add(self.__convert_kana_to_hepburn(name))

            age = self.__str_to_int(char_p.get("CharacterAgeJp", ""))
            height = self.__str_to_int(char_p.get("CharHeightJp", ""))

            data = CharacterData(
                char_p.get("CharacterId", 0),
                names=list(names),
                cv=char_p.get("CharacterVoiceJp", ""),
                age=age,
                height=height,
                birthday=char_p.get("BirthDay", ""),
                illustrator=char_p.get("IllustratorNameJp", ""),
            )

            hash_map[data.character_id] = data

        for char_e in char_excel:
            data = hash_map.get(
                char_e.get("Id", -1), CharacterData(char_e.get("Id", 0))
            )
            data.dev_name = char_e.get("DevName", "")
            data.school_en = char_e.get("School", "")
            data.club_en = char_e.get("Club", "")

        for scenario in scenario_db:
            scenario_data_unrelated = True
            scene_data = scenario.get("Bytes", {})
            file_name = self.__split_path_to_name(scene_data.get("SmallPortrait", ""))
            name_no_underline = file_name.replace("_", "")
            jp_name = scene_data.get("NameJP", "")

            if not (file_name and jp_name):
                continue

            for char_data in hash_map.values():
                char_names = char_data.names if char_data.names else []
                if char_data.dev_name and (
                    any(jp_name in n.lower() for n in char_names)
                    or (char_data.dev_name in file_name)
                ):
                    if char_data.file_name:
                        char_data.file_name.update({file_name, name_no_underline})
                    else:
                        char_data.file_name = {file_name, name_no_underline}
                    scenario_data_unrelated = False

            if (
                scenario_data_unrelated
                and file_name != "Null"  # Default portrait name.
                and (char_id := scene_data.get("CharacterName", 0))
            ):
                names = set()
                for key in scene_data.keys():
                    if key.lower().startswith("name"):
                        if name := scene_data.get(key, ""):
                            names.add(name)
                        if jp_name:
                            names.add(self.__convert_kana_to_hepburn(jp_name))

                char_id = -char_id if char_id in hash_map else char_id
                hash_map[char_id] = CharacterData(
                    char_id,
                    dev_name=file_name,
                    names=list(names),
                    file_name={file_name, name_no_underline},
                )

        return list(hash_map.values())

    def __create_relation_file(
        self, version: str, region: str, data: list[CharacterData]
    ) -> None:
        region = region.upper()
        with open(region + self.RELATION_NAME, "w", encoding="utf8") as f:
            json.dump(
                asdict(CharacterRelation(region + version, data)),
                f,
                indent=4,
                ensure_ascii=False,
                default=CharacterData.serialize,
            )

    def verify_relation_file(self, context: RuntimeContext | None = None) -> bool:
        """Ensure the relation file exists in the directory."""
        active_context = context or self.context
        try:
            with open(
                active_context.region + CharacterNameRelation.RELATION_NAME,
                encoding="utf8",
            ) as f:
                return json.load(f).get("version", "") == (
                    active_context.region.upper() + active_context.version
                )
        except Exception:
            return False

    def search(
        self,
        context: RuntimeContext | None = None,
        search_terms: list[str] | None = None,
    ) -> list[str]:
        """Search relation from file."""
        active_context = context or self.context
        search_terms = search_terms or []
        try:
            relation_file = (
                active_context.region.upper() + CharacterNameRelation.RELATION_NAME
            )
            if not Path(relation_file).exists():
                raise FileNotFoundError("Character relation file does not exist.")

            if not self.verify_relation_file(active_context):
                self.logger.warn(
                    "The character relation version does not match the latest game version."
                )

            relation = CharacterRelation("", [])
            with open(relation_file, encoding="utf8") as f:
                relation_json = json.load(f)
                relation.version = relation_json.get("version", "")
                for rel in relation_json.get("relations", []):
                    relation.relations.append(CharacterData(**rel))

            search_keywords = []
            keywords = [s.lower() for s in search_terms if "=" not in s]
            char_attr = {}
            for keyword in search_terms:
                arg = keyword.lower().split("=")
                if "=" in keyword and arg[0] in [
                    "cv",
                    "age",
                    "height",
                    "birthday",
                    "illustrator",
                    "school",
                    "club",
                ]:
                    char_attr[arg[0]] = arg[1]

            for char in relation.relations:
                file_name = list(char.file_name) if char.file_name else []
                char_names = list(char.names) if char.names else []
                if any(
                    [
                        any(
                            keyword in [n.lower() for n in char_names]
                            for keyword in keywords
                        ),
                        any(
                            keyword in [f.lower() for f in file_name]
                            for keyword in keywords
                        ),
                        (char.cv.lower() or "None") in char_attr.get("cv", "_"),
                        str(char.age) == char_attr.get("age", -1),
                        str(char.height) == char_attr.get("height", -1),
                        (char.birthday.lower() or "None")
                        in char_attr.get("birthday", "_"),
                        (char.illustrator.lower() or "None")
                        in char_attr.get("illustrator", "_"),
                        (char.school_en.lower() or "None")
                        in char_attr.get("school", "_"),
                        (char.club_en.lower() or "None") in char_attr.get("club", "_"),
                    ]
                ):
                    search_keywords += file_name
                    search_keywords += [char.dev_name]

            search_keywords = [k for k in search_keywords if k]
            return search_keywords
        except Exception as e:
            raise LookupError(
                f"Search failed due to error {e}. Retrying may solve the issue."
            ) from e



