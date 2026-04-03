import hashlib
from importlib import import_module, invalidate_caches, util
import json
import os
from os import path
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, cast
from zipfile import ZipFile

from ba_downloader.domain.models.database import DBTable, SQLiteDataType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
from ba_downloader.infrastructure.storage import TableDatabase
from ba_downloader.shared.crypto.encryption import xor_with_key, zip_password


class TableExtractor:
    def __init__(
        self,
        table_file_folder: str,
        extract_folder: str,
        flat_data_dir: str,
        logger: LoggerPort | None = None,
    ) -> None:
        """Extract files in table folder.

        Args:
            table_file_folder (str): Folder own table files.
            extract_folder (str): Folder to store the extracted data.
            flat_data_dir (str): Folder path containing generated FlatData Python modules.
        """
        self.table_file_folder = table_file_folder
        self.extract_folder = extract_folder
        self.flat_data_dir = flat_data_dir
        self.logger = logger or ConsoleLogger()

        self.lower_fb_name_modules: dict[str, type] = {}
        self.dump_wrapper_lib: ModuleType

        self._load_modules()

    @classmethod
    def from_context(
        cls,
        context: RuntimeContext,
        logger: LoggerPort | None = None,
    ) -> "TableExtractor":
        return cls(
            str(Path(context.raw_dir) / "Table"),
            str(Path(context.extract_dir) / "Table"),
            str(Path(context.extract_dir) / "FlatData"),
            logger=logger,
        )

    def _load_modules(self) -> None:
        flat_data_lib = self._load_flat_data_package()
        self.lower_fb_name_modules = {
            t_name.lower(): t_class
            for t_name, t_class in flat_data_lib.__dict__.items()
        }

    def _load_flat_data_package(self) -> ModuleType:
        flat_data_dir = Path(self.flat_data_dir)
        init_file = flat_data_dir / "__init__.py"
        dump_wrapper_file = flat_data_dir / "dump_wrapper.py"
        if not flat_data_dir.is_dir():
            raise FileNotFoundError(
                f"FlatData directory does not exist: {flat_data_dir}."
            )
        if not init_file.is_file():
            raise FileNotFoundError(
                f"FlatData package initializer is missing: {init_file}."
            )
        if not dump_wrapper_file.is_file():
            raise FileNotFoundError(
                f"FlatData dump wrapper is missing: {dump_wrapper_file}."
            )

        invalidate_caches()
        path_digest = hashlib.sha1(str(flat_data_dir.resolve()).encode("utf-8")).hexdigest()
        package_name = (
            "ba_downloader_generated_flatdata_"
            f"{path_digest}"
        )
        spec = util.spec_from_file_location(
            package_name,
            init_file,
            submodule_search_locations=[str(flat_data_dir)],
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to create FlatData import spec for {flat_data_dir}.")

        module = sys.modules.get(package_name)
        if module is None:
            module = util.module_from_spec(spec)
            sys.modules[package_name] = module
            spec.loader.exec_module(module)

        self.dump_wrapper_lib = import_module(f"{package_name}.dump_wrapper")
        return module

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
        raw_flatbuffer_class = self.lower_fb_name_modules.get(
            file_name.removesuffix(".bytes").lower(), None
        )
        if raw_flatbuffer_class is None:
            return {}, ""
        flatbuffer_class = cast(Any, raw_flatbuffer_class)

        obj = None
        try:
            if flatbuffer_class.__name__.endswith("Table"):
                try:
                    data = xor_with_key(flatbuffer_class.__name__, data)
                    flat_buffer = flatbuffer_class.GetRootAs(data)
                    obj = self.dump_wrapper_lib.dump_table(flat_buffer)
                except Exception:
                    pass

            if not obj:
                flat_buffer = flatbuffer_class.GetRootAs(data)
                obj = getattr(
                    self.dump_wrapper_lib, f"dump_{flatbuffer_class.__name__}"
                )(flat_buffer)
            return (obj, f"{flatbuffer_class.__name__}.json")
        except Exception:
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
        except Exception:
            return b""

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
                    for col, value in zip(columns, row, strict=True):
                        col_type = SQLiteDataType[col.data_type].value
                        if col_type is bytes:
                            data, _ = self._process_bytes_file(
                                table.replace("DBSchema", "Excel"), value
                            )
                            row_data.append(data)
                        elif col_type is bool:
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
        data = b""
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
                        "w",
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
            self.logger.error(f"Error when process {file_path}: {e}")
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

                    data, name, success = b"", "", False
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
                        self.logger.warn(
                            f"The file {item_name} in {file_name} is not be implementate or cannot process."
                        )
                        continue

                    with open(path.join(zip_extract_folder, item_name), "wb") as f:
                        f.write(item_data)
        except Exception as e:
            self.logger.error(f"Error when process {file_name}: {e}")

    def extract_table(self, file_path: str) -> None:
        """Extract a table by file path."""
        if not file_path.endswith((".zip", ".db")):
            self.logger.warn(f"The file {file_path} is not supported in current implementation.")

        if file_path.endswith(".db"):
            self.extract_db_file(file_path)

        if file_path.endswith(".zip"):
            self.extract_zip_file(file_path)



