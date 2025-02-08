import importlib
import json
import os
from os import path
from types import ModuleType
from typing import Any
from zipfile import ZipFile

from lib.console import notice, print
from lib.encryption import xor_with_key, zip_password
from lib.structure import DBTable, SQLiteDataType
from utils.database import TableDatabase


class TableExtractor:
    def __init__(
        self, table_file_folder: str, extract_folder: str, flat_data_module_name: str
    ) -> None:
        """Extract files in table folder.

        Args:
            table_file_folder (str): Folder own table files.
            extract_folder (str): Folder to store the extracted data.
            flat_data_module_name (str): Name path to import flat data module. Most like "Extracted.FlatData".
        """
        self.table_file_folder = table_file_folder
        self.extract_folder = extract_folder
        self.flat_data_module_name = flat_data_module_name

        self.lower_fb_name_modules: dict[str, type] = {}
        self.dump_wrapper_lib: ModuleType

        self.__import_modules()

    def __import_modules(self):
        try:
            flat_data_lib = importlib.import_module(self.flat_data_module_name)
            self.dump_wrapper_lib = importlib.import_module(
                f"{self.flat_data_module_name}.dump_wrapper"
            )
        except Exception as e:
            notice(
                f"Cannot import FlatData module. Make sure FlatData is available in Extracted folder. {e}",
                "error",
            )
        self.lower_fb_name_modules = {
            t_name.lower(): t_class
            for t_name, t_class in flat_data_lib.__dict__.items()
        }

    def _process_bytes_file(
        self, file_name: str, data: bytes
    ) -> tuple[dict[str, Any], str]:
        """Extract flatbuffer bytes file to dict

        Args:
            file_name (str): Schema name of data.
            data (bytes): Flatbuffer data to extract.

        Returns:
            tuple[dict[str, Any], str]: Tuple with extracted dict and file name. Always have file name if success extract.
        """
        if not (
            flatbuffer_class := self.lower_fb_name_modules.get(
                file_name.removesuffix(".bytes").lower(), None
            )
        ):
            return {}, ""

        obj = None
        try:
            if flatbuffer_class.__name__.endswith("Table"):
                try:
                    data = xor_with_key(flatbuffer_class.__name__, data)
                    flat_buffer = getattr(flatbuffer_class, "GetRootAs")(data)
                    obj = getattr(self.dump_wrapper_lib, "dump_table")(flat_buffer)
                except:
                    pass

            if not obj:
                flat_buffer = getattr(flatbuffer_class, "GetRootAs")(data)
                obj = getattr(
                    self.dump_wrapper_lib, f"dump_{flatbuffer_class.__name__}"
                )(flat_buffer)
            return (obj, f"{flatbuffer_class.__name__}.json")
        except:
            # if json_data := self.__process_json_file(file_name, data):
            #     return json.loads(json_data), f"{file_name}.json"
            return {}, ""

    def _process_json_file(self, data: bytes) -> bytes:
        """Extract json file in zip.

        Args:
            file_name (str): File name.
            data (bytes): Data of file.

        Returns:
            bytes: Bytes of json data.
        """
        try:
            data.decode("utf8")
            return data
        except:
            return bytes()

    def _process_db_file(self, file_path: str, table_name: str = "") -> list[DBTable]:
        """Extract sqlite database file.

        Args:
            file_path (str): Database path.
            table_name (str): Specify table to extract.

        Returns:
            list[DBTable]: A list of DBTables.
        """
        with TableDatabase(file_path) as db:
            tables = []

            table_list = [table_name] if table_name else db.get_table_list()

            for table in table_list:
                columns = db.get_table_column_structure(table)
                rows: list[tuple] = db.get_table_data(table)[1]
                table_data = []
                for row in rows:
                    row_data: list[Any] = []
                    for col, value in zip(columns, row):
                        col_type = SQLiteDataType[col.data_type].value
                        if col_type == bytes:
                            data, _ = self._process_bytes_file(
                                table.replace("DBSchema", "Excel"), value
                            )
                            row_data.append(data)
                        elif col_type == bool:
                            row_data.append(bool(value))
                        else:
                            row_data.append(value)

                    table_data.append(row_data)
                tables.append(DBTable(table, columns, table_data))
            return tables

    def _process_zip_file(
        self,
        file_name: str,
        file_data: bytes,
        detect_type: bool = False,
    ) -> tuple[bytes, str, bool]:
        data = bytes()
        if (detect_type or file_name.endswith(".json")) and (
            data := self._process_json_file(file_data)
        ):
            return data, "", True

        if detect_type or file_name.endswith(".bytes"):
            b_data = self._process_bytes_file(file_name, file_data)
            file_dict, file_name = b_data
            if file_name:
                return (
                    json.dumps(file_dict, indent=4, ensure_ascii=False).encode("utf8"),
                    file_name,
                    True,
                )

        return data, "", False

    def extract_db_file(self, file_path: str) -> bool:
        """Extract db file."""
        try:
            if db_tables := self._process_db_file(
                path.join(self.table_file_folder, file_path)
            ):
                db_name = file_path.removesuffix(".db")
                for table in db_tables:
                    db_extract_folder = path.join(self.extract_folder, db_name)
                    os.makedirs(db_extract_folder, exist_ok=True)
                    with open(
                        path.join(db_extract_folder, f"{table.name}.json"),
                        "wt",
                        encoding="utf8",
                    ) as f:
                        json.dump(
                            TableDatabase.convert_to_list_dict(table),
                            f,
                            indent=4,
                            ensure_ascii=False,
                        )
                return True
            return False
        except Exception as e:
            print(f"Error when process {file_path}: {e}")
            return False

    def extract_zip_file(self, file_name: str) -> None:
        """Extract zip file."""
        try:
            zip_extract_folder = path.join(
                self.extract_folder, file_name.removesuffix(".zip")
            )
            os.makedirs(zip_extract_folder, exist_ok=True)

            password = zip_password(path.basename(file_name))
            with ZipFile(path.join(self.table_file_folder, file_name), "r") as zip:
                zip.setpassword(password)
                for item_name in zip.namelist():
                    item_data = zip.read(item_name)

                    data, name, success = bytes(), "", False
                    if item_name.endswith((".json", ".bytes")):
                        if "RootMotion" in file_name:
                            data, name, success = self._process_zip_file(
                                f"{file_name.removesuffix('.zip')}Flat", item_data, True
                            )
                            name = item_name
                        else:
                            data, name, success = self._process_zip_file(
                                item_name, item_data
                            )

                    if not success:
                        data, name, success = self._process_zip_file(
                            item_name, item_data, True
                        )
                    if success:
                        item_name = name if name else item_name
                        item_data = data
                    else:
                        notice(
                            f"The file {item_name} in {file_name} is not be implementate or cannot process."
                        )
                        continue

                    with open(path.join(zip_extract_folder, item_name), "wb") as f:
                        f.write(item_data)
        except Exception as e:
            print(f"Error when process {file_name}: {e}")

    def extract_table(self, file_path: str) -> None:
        """Extract a table by file path."""
        if not file_path.endswith((".zip", ".db")):
            notice(f"The file {file_path} is not supported in current implementation.")

        if file_path.endswith(".db"):
            self.extract_db_file(file_path)

        if file_path.endswith(".zip"):
            self.extract_zip_file(file_path)
