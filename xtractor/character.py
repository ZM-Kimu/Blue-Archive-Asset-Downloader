import json
import re
from dataclasses import asdict
from os import path
from typing import Any

import pykakasi

from lib.console import notice, print
from lib.encryption import zip_password
from lib.structure import CharacterData, CharacterRelation, Resource
from utils.config import Config
from utils.database import TableDatabase
from utils.util import FileUtils, ZipUtils
from xtractor.table import TableExtractor


class CharacterNameRelation(TableExtractor):
    EXCEL_NAME = "Excel.zip"
    DB_NAME = "ExcelDB.db"
    RELATION_NAME = "CharacterRelation.json"
    EXCEL_FOLDER = path.join(Config.raw_dir, "Table")
    EXCEL_EXTRACT_FOLDER = path.join(Config.temp_dir, "Table")

    def __init__(self) -> None:
        super().__init__(
            self.EXCEL_FOLDER,
            self.EXCEL_EXTRACT_FOLDER,
            f"{Config.extract_dir}.FlatData",
        )

        self.kana_converter = pykakasi.kakasi()

    def __convert_kana_to_hepburn(self, kana: str) -> str:
        return "".join([kana["hepburn"] for kana in self.kana_converter.convert(kana)])

    def __get_int_from_str(self, text: str, default: int = 0) -> int:
        return (
            int(re_digit.group()) if (re_digit := re.search(r"\d+", text)) else default
        )

    def __split_path_to_name(self, file_path: str, max_split=2):
        return path.basename(file_path).split("_", max_split)[-1]

    def main(self) -> None:
        """Character extract entry."""
        print("Extracting necessary data...")
        excel = self.__extract_excel()
        print("Relating character data...")
        relations = self.__create_relation_list(*excel)
        self.__create_relation_file(Config.version, Config.region, relations)

    def get_excel_res(self, resource: Resource) -> Resource:
        """Get excel file item from resources."""
        searched = resource.search_resource("path", self.EXCEL_NAME)
        if not (searched := resource.search_resource("path", "Excel")):
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

        ZipUtils.extract_zip(
            path.join(self.EXCEL_FOLDER, self.EXCEL_NAME),
            path.join(self.extract_folder, self.EXCEL_NAME.removesuffix(".zip")),
            keywords=bytes_files,
            password=zip_password(self.EXCEL_NAME),
        )

        if tables := self._process_db_file(
            path.join(self.EXCEL_FOLDER, self.DB_NAME), "ScenarioCharacterNameDBSchema"
        ):
            scenario_db = TableDatabase.convert_to_list_dict(tables[0])

        b_file_paths = FileUtils.find_files(
            self.EXCEL_EXTRACT_FOLDER, bytes_files, True
        )

        if len(bytes_files) == 2:
            for b_path, b_name in zip(b_file_paths, bytes_files):
                with open(b_path, "rb") as f:
                    excel_data, _, _ = self._process_zip_file(b_name, f.read(), True)
                    if b_name == "characterexceltable.bytes":
                        char_excel = json.loads(excel_data)
                    else:
                        char_profile = json.loads(excel_data)

        if not (scenario_db and char_excel and char_profile):
            notice("Some files wents wrong. Name relation might incomplete.")

        return scenario_db, char_profile, char_excel

    def __create_relation_list(
        self,
        scenario_db: list[dict[str, Any]],
        char_profile: list[dict[str, Any]],
        char_excel: list[dict],
    ) -> list[CharacterData]:
        hash_map: dict[int, CharacterData] = {}

        for char_p in char_profile:
            family_name_ruby_jp = char_p.get("FamilyNameRubyJp", "")
            personal_name_kana = char_p.get("PersonalNameRubyJp", "") or char_p.get(
                "PersonalNameJp", ""
            )

            family_name_en = self.__convert_kana_to_hepburn(family_name_ruby_jp)
            personal_name_en = self.__convert_kana_to_hepburn(personal_name_kana)

            age = self.__get_int_from_str(char_p.get("CharacterAgeJp", ""))
            height = self.__get_int_from_str(char_p.get("CharHeightJp", ""))

            data = CharacterData(
                char_p.get("CharacterId", 0),
                full_name_kr=char_p.get("FullNameKr", "").replace(" ", ""),
                full_name_jp=char_p.get("FullNameJp", ""),
                family_name_jp=char_p.get("FamilyNameJp", ""),
                family_name_kr=char_p.get("FamilyNameKr", ""),
                family_name_ruby_jp=family_name_ruby_jp,
                personal_name_jp=char_p.get("PersonalNameJp", ""),
                personal_name_kr=char_p.get("PersonalNameKr", ""),
                personal_name_ruby_jp=char_p.get("PersonalNameRubyJp", ""),
                family_name_en=family_name_en,
                personal_name_en=personal_name_en,
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
            scenario_data = scenario["Bytes"]
            file_name = self.__split_path_to_name(
                scenario_data.get("SmallPortrait", "")
            )
            name_no_underline = file_name.replace("_", "")
            jp_name = scenario_data.get("NameJP", "")

            for char_data in hash_map.values():
                if file_name and (jp_name == char_data.personal_name_jp):
                    if char_data.file_name:
                        char_data.file_name.add(file_name)
                        char_data.file_name.add(name_no_underline)
                    else:
                        char_data.file_name = {file_name, name_no_underline}
                    scenario_data_unrelated = False

            if (
                scenario_data_unrelated
                and file_name
                and file_name != "Null"  # Default portrait name.
                and (char_id := scenario_data.get("CharacterName", 0))
                and jp_name
            ):
                hash_map[char_id] = CharacterData(
                    char_id,
                    dev_name=file_name,
                    personal_name_jp=jp_name,
                    personal_name_kr=scenario_data.get("NameKR", ""),
                    family_name_en=self.__convert_kana_to_hepburn(jp_name),
                    file_name={file_name, name_no_underline},
                )

        return list(hash_map.values())

    def __create_relation_file(
        self, version: str, region: str, data: list[CharacterData]
    ) -> None:
        region = region.upper()
        with open(region + self.RELATION_NAME, "wt", encoding="utf8") as f:
            json.dump(
                asdict(CharacterRelation(region + version, data)),
                f,
                indent=4,
                ensure_ascii=False,
                default=CharacterData.serialize,
            )

    @staticmethod
    def verify_relation_file(version: str, region: str) -> bool:
        """Ensure the relation file exists in the directory."""
        try:
            with open(
                region + CharacterNameRelation.RELATION_NAME, "rt", encoding="utf8"
            ) as f:
                return json.load(f).get("version", "") == (region.upper() + version)
        except:
            return False

    @staticmethod
    def search(version: str, region: str, search: list[str]) -> list[str]:
        """Search relation from file."""
        try:
            relation_file = region.upper() + CharacterNameRelation.RELATION_NAME
            if not path.exists(relation_file):
                raise FileNotFoundError("Character relation file does not exist.")

            if not CharacterNameRelation.verify_relation_file(version, region):
                notice(
                    "The character relation version does not match the latest game version."
                )

            relation = CharacterRelation("", [])
            with open(relation_file, "rt", encoding="utf8") as f:
                relation_json = json.load(f)
                relation.version = relation_json.get("version", "")
                for rel in relation_json.get("relations", []):
                    relation.relations.append(CharacterData(**rel))

            search_keywords = []
            keywords = [s.lower() for s in search if "=" not in s]
            char_attr = {}
            for keyword in search:
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
                if any(
                    [
                        char.full_name_jp in keywords,
                        char.full_name_kr in keywords,
                        char.family_name_jp in keywords,
                        char.family_name_kr in keywords,
                        char.family_name_ruby_jp in keywords,
                        char.personal_name_jp in keywords,
                        char.personal_name_kr in keywords,
                        char.family_name_en in keywords,
                        char.personal_name_en in keywords,
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
