import importlib
import json
import os
from io import BytesIO
from os import path
from types import ModuleType
from typing import IO, Any, Literal
from zipfile import ZipFile, ZipInfo

from lib.console import ProgressBar, notice, print
from lib.encryption import aes_decrypt, table_zip_password, xor_with_key
from lib.structure import DBTable, SQLiteDataType
from utils.config import Config
from utils.database import TableDatabase
from utils.util import TaskManager


class TableZipFile(ZipFile):
    """Override ZipFile lib."""

    def __init__(self, file: str | BytesIO, file_name: str = "") -> None:
        super().__init__(file)
        file_name = file_name if not isinstance(file, str) else path.basename(file)
        self.password = table_zip_password(file_name)

    def open(
        self,
        name: str | ZipInfo,
        mode: Literal["r", "w"] = "r",
        pwd: bytes | None = None,
        *,
        force_zip64: bool = False,
    ) -> IO[bytes]:
        return super().open(name, mode, pwd=self.password, force_zip64=force_zip64)


class TableExtractor:
    def __init__(
        self, table_file_folder: str, extract_folder: str, flat_data_module_name: str
    ) -> None:
        """Extract files in table folder.

        Args:
            table_file_folder (str): Folder own table files.
            extract_folder (str): Folder to store the extracted data.
            flat_data_module_name (str): Name to import flat data module.
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

    def process_bytes_file(
        self, file_name: str, data: bytes
    ) -> tuple[dict[str, Any], str]:
        """Extract flatbuffer bytes file to dict

        Args:
            file_name (str): Schema name of data.
            data (bytes): Flatbuffer data to extract.

        Returns:
            tuple[dict[str, Any], str]: Tuple with extracted dict and file name.
        """
        if not (
            flatbuffer_class := self.lower_fb_name_modules.get(
                file_name.removesuffix(".bytes").removesuffix("").lower(), None
            )
        ):
            return {}, ""
        try:
            if flatbuffer_class.__name__.endswith("Table"):  # TODO: ??
                data = xor_with_key(flatbuffer_class.__name__, data)
                flat_buffer = getattr(flatbuffer_class, "GetRootAs")(data)
                excel = getattr(self.dump_wrapper_lib, "dump_table")(flat_buffer)
            else:
                flat_buffer = getattr(flatbuffer_class, "GetRootAs")(data)
                excel = getattr(
                    self.dump_wrapper_lib, f"dump_{flatbuffer_class.__name__}"
                )(flat_buffer)
            return (excel, f"{flatbuffer_class.__name__}.json")
        except:
            return {}, ""

    def process_json_file(self, file_name: str, data: bytes) -> bytes:
        """Extract json file in zip.

        Args:
            file_name (str): File name.
            data (bytes): Data of file.

        Returns:
            bytes: Bytes of json data.
        """
        if file_name == "logiceffectdata.json":
            return aes_decrypt(data, "LogicEffectData").encode("utf8")
        if file_name == "newskilldata.json":
            return aes_decrypt(data, "NewSkillData").encode("utf8")
        try:
            data.decode("utf8")
            return data
        except:
            pass
        return bytes()

    def process_db_file(self, file_path: str) -> list[DBTable]:
        """Extract sqlite database file.

        Args:
            file_path (str): Database path.

        Returns:
            list[DBTable]: A list of DBTables.
        """
        with TableDatabase(file_path) as db:
            tables = []

            for table in db.get_table_list():
                columns = db.get_table_column_structure(table)
                rows: list[tuple] = db.get_table_data(table)[1]
                table_data = []
                for row in rows:
                    row_data: list[Any] = []
                    for col, value in zip(columns, row):
                        col_type = SQLiteDataType[col.data_type].value
                        if col_type == bytes:
                            data, _ = self.process_bytes_file(
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

    def __extract_worker(self, task_manager: TaskManager) -> None:
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            table_file = task_manager.tasks.get()
            ProgressBar.item_text(table_file)
            try:
                if not table_file.endswith((".zip", ".db")):
                    notice(
                        f"The file {table_file} is not supported in current implementation."
                    )
                    return

                if table_file.endswith(".db") and (
                    db_tables := self.process_db_file(
                        path.join(self.table_file_folder, table_file)
                    )
                ):
                    db_name = table_file.removesuffix(".db")
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
                    return

                zip_extract_folder = path.join(
                    self.extract_folder, table_file.removesuffix(".zip")
                )
                os.makedirs(zip_extract_folder, exist_ok=True)

                with TableZipFile(
                    path.join(self.table_file_folder, table_file), "r"
                ) as zip_file:
                    for file_name in zip_file.namelist():
                        file_data = zip_file.read(file_name)

                        if file_name.endswith(".json") and not (
                            file_data := self.process_json_file(file_name, file_data)
                        ):
                            notice(
                                f"The json file: {file_name} in {table_file} is not implementate for process."
                            )

                        if file_name.endswith("bytes"):
                            file_dict, file_name = self.process_bytes_file(
                                file_name, file_data
                            )
                            if not file_data:
                                print(
                                    f"Cannot process file {file_name} in {table_file}."
                                )
                                continue

                            file_data = json.dumps(
                                file_dict, indent=4, ensure_ascii=False
                            ).encode("utf8")

                        if file_data:
                            with open(
                                path.join(zip_extract_folder, file_name), "wb"
                            ) as file:
                                file.write(file_data)
            except Exception as e:
                print(f"Error while extract table {table_file}: {e}")
            table_file = task_manager.tasks.task_done()
            ProgressBar.increase()

    def extract_tables(self) -> None:
        """Extract table with multi-thread"""
        os.makedirs(self.extract_folder, exist_ok=True)
        table_files = os.listdir(self.table_file_folder)
        with ProgressBar(len(table_files), "Extracting Table file...", "items"):
            with TaskManager(
                Config.threads, Config.max_threads, self.__extract_worker
            ) as manager:
                manager.import_tasks(table_files)
                manager.run(manager)
