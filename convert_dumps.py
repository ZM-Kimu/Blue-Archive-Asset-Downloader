import importlib
import json
import os
import sqlite3
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from os import path
from types import ModuleType
from typing import IO, Any, Literal
from zipfile import ZipFile, ZipInfo

from lib.compiler import DumpToPython, ParseFromCS
from lib.console import ProgressBar, notice, print
from lib.dumper import FlatBufferDumper
from lib.encryption import aes_decrypt, create_key, table_zip_password, xor_with_key
from utils.config import Config


class SQLDataType(Enum):
    INTEGER = int
    REAL = float
    NUMERIC = int | float
    TEXT = str
    BLOB = bytes
    BOOLEAN = bool
    NULL = None


@dataclass
class Column:
    name: str
    data_type: str


@dataclass
class Table:
    name: str
    columns: list[Column]
    data: list[list]


class DBTable:
    def __init__(self, database: str) -> None:
        self.database = database
        self.connection = sqlite3.connect(self.database)

    def __enter__(self) -> "DBTable":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.connection.close()

    def get_table_list(self) -> list[str]:
        """Get all table name in database as list.

        Returns:
            list[tuple]: Tables
        """
        cursor = self.connection.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

        return [table[0] for table in cursor.fetchall() if table]

    def get_table_column_structure(self, table: str) -> list[Column]:
        """Get data structure of table.

        Args:
            table (str): table_name

        Returns:
            list[Column]: A list store all columns structure.
        """
        cursor = self.connection.cursor()

        cursor.execute(f"PRAGMA table_info({table});")

        return [Column(name=col[1], data_type=col[2]) for col in cursor.fetchall()]

    def get_table_data(self, table: str) -> tuple[list, list]:
        """Get all rows and table structure in table.

        Args:
            table (str): table_name

        Returns:
            tuple[list, list]: First list store the column_names. Second list store the rows.
        """
        cursor = self.connection.cursor()

        cursor.execute(f"SELECT * FROM {table};")

        column_names = [description[0] for description in cursor.description]
        rows = cursor.fetchall()

        return column_names, rows

    @staticmethod
    def convert_to_list_dict(table: Table) -> list[dict]:
        table_rows = []
        for row in table.data:
            row_data = {}
            for col, value in zip(table.columns, row):
                row_data[col.name] = value
            if row_data:
                table_rows.append(row_data)

        return table_rows


class TableZipFile(ZipFile):
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


class Dumper:
    FB_DATA_DIR = path.join(Config.extract_dir, "FlatData")
    DUMP_CS_FILE_PATH = path.join(Config.extract_dir, "Dumps", "dump.cs")

    def __init__(self):
        self.enums = []
        self.structs = []

    def dump(self):
        """Parse dump.cs and dump to python."""
        print("Process dump.cs...")
        parser = ParseFromCS(self.DUMP_CS_FILE_PATH)
        self.enums = parser.extract_enum_from_dump()
        self.structs = parser.extract_struct_from_dump()

        print("Generate flatbuffer python dump files...")
        compiler = DumpToPython(self.enums, self.structs, self.FB_DATA_DIR)
        compiler.convert_enum()
        compiler.convert_struct()
        compiler.create_module_file()
        compiler.create_dump_dict_file()


class ExtractTable:
    table_folder = path.join(Config.raw_dir, "Table")
    table_extract_folder = path.join(Config.extract_dir, "Table")

    def __init__(self) -> None:
        self.lower_fb_name_modules: dict[str, type] = {}
        self.dump_wrapper_lib: ModuleType
        self.__import_modules()

    def __import_modules(self):
        try:
            flat_data_lib = importlib.import_module(f"{Config.extract_dir}.FlatData")
            self.dump_wrapper_lib = importlib.import_module(
                f"{Config.extract_dir}.FlatData.dump_wrapper"
            )
        except:
            notice(
                "Cannot import FlatData module. Make sure FlatData is available in Extracted folder.",
                "error",
            )
        self.lower_fb_name_modules = {
            t_name.lower(): t_class
            for t_name, t_class in flat_data_lib.__dict__.items()
        }

    def __process_db_file(self, file_path: str) -> list[Table]:
        with DBTable(file_path) as db:
            tables = []

            for table in db.get_table_list():
                columns = db.get_table_column_structure(table)
                rows: list[tuple] = db.get_table_data(table)[1]
                table_data = []
                for row in rows:
                    row_data: list[Any] = []
                    for col, value in zip(columns, row):
                        col_type = SQLDataType[col.data_type].value
                        if col_type == bytes:
                            data, _ = self.__process_bytes_file(
                                table.replace("DBSchema", "Excel"),
                                value,
                                return_dict=True,
                            )
                            row_data.append(data)
                        elif col_type == bool:
                            row_data.append(bool(value))
                        else:
                            row_data.append(value)

                    table_data.append(row_data)
                tables.append(Table(table, columns, table_data))
            return tables

    def __process_json_file(self, file_name: str, data: bytes) -> bytes:
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

    def __process_bytes_file(
        self, file_name: str, data: bytes, return_dict: bool = False
    ) -> tuple[bytes | dict, str]:
        if not (
            flatbuffer_class := self.lower_fb_name_modules.get(
                file_name.removesuffix(".bytes").removesuffix("").lower(), None
            )
        ):
            return ({} if return_dict else bytes()), ""
        if flatbuffer_class.__name__.endswith("Table"):  # TODO: ??
            data = xor_with_key(flatbuffer_class.__name__, data)
            flat_buffer = getattr(flatbuffer_class, "GetRootAs")(data)
            excel = getattr(self.dump_wrapper_lib, "dump_table")(flat_buffer)
        else:
            flat_buffer = getattr(flatbuffer_class, "GetRootAs")(data)
            excel = getattr(self.dump_wrapper_lib, f"dump_{flatbuffer_class.__name__}")(
                flat_buffer
            )
        return (
            (
                excel
                if return_dict
                else json.dumps(excel, indent=4, ensure_ascii=False).encode("utf8")
            ),
            f"{flatbuffer_class.__name__}.json",
        )

    def extract_tables(self) -> None:
        os.makedirs(self.table_extract_folder, exist_ok=True)
        table_files = os.listdir(self.table_folder)
        with ProgressBar(len(table_files), "Extracting Table file...", "items") as bar:
            for table_file in table_files:
                bar.item_text(table_file)

                if table_file.endswith(".db"):
                    if tables := self.__process_db_file(
                        path.join(self.table_folder, table_file)
                    ):
                        table_name = table_file.removesuffix(".db")
                        for table in tables:
                            os.makedirs(
                                path.join(self.table_extract_folder, table_name),
                                exist_ok=True,
                            )
                            with open(
                                path.join(
                                    self.table_extract_folder,
                                    table_name,
                                    f"{table.name}.json",
                                ),
                                "wb",
                            ) as f:
                                f.write(
                                    json.dumps(
                                        DBTable.convert_to_list_dict(table),
                                        indent=4,
                                        ensure_ascii=False,
                                    ).encode("utf8")
                                )
                    continue
                if not table_file.endswith(".zip"):
                    notice(
                        f"The file {table_file} is not supported in current implementation."
                    )
                    continue

                extract_folder = path.join(
                    self.table_extract_folder, table_file.removesuffix(".zip")
                )
                os.makedirs(extract_folder, exist_ok=True)

                with TableZipFile(
                    path.join(self.table_folder, table_file), "r"
                ) as zip_file:
                    for file in zip_file.namelist():
                        data = zip_file.read(file)
                        file_name = file

                        # Battle.zip
                        # process encryption of those two files
                        if file.endswith(".json"):
                            if not (data := self.__process_json_file(file_name, data)):
                                notice(
                                    f"The json file: {file} in {table_file} is not implementate for process."
                                )
                                continue

                        if file.endswith("bytes"):
                            try:
                                data, file_name = self.__process_bytes_file(
                                    file_name, data
                                )
                                if not data:
                                    print(
                                        f"Cannot process file {file} in {table_file}."
                                    )
                                    continue

                            except Exception as e:
                                notice(
                                    f"Error encountered while processing file {file_name} in {table_file}: {e}.",
                                    "error",
                                )
                                continue

                        with open(path.join(extract_folder, file_name), "wb") as f:
                            f.write(data)
                bar.increase()
