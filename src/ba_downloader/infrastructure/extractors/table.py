from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import struct
import sys
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from importlib import import_module, invalidate_caches, util
from os import path
from pathlib import Path
from types import ModuleType
from typing import Any
from zipfile import BadZipFile, ZipFile

from ba_downloader.domain.models.database import DBTable, SQLiteDataType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
from ba_downloader.infrastructure.storage import TableDatabase
from ba_downloader.shared.crypto.encryption import xor_with_key, zip_password


class TableProcessingError(RuntimeError):
    """Raised when a table payload cannot be processed."""


class UnsupportedSchemaError(TableProcessingError):
    """Raised when no generated FlatData class matches a payload."""


class GeneratedDumpWrapperError(TableProcessingError):
    """Raised when generated dump wrapper functions are missing or invalid."""


class TableDecryptError(TableProcessingError):
    """Raised when xor-protected table payloads cannot be decoded."""


class MalformedTablePayloadError(TableProcessingError):
    """Raised when bytes or JSON payload content is malformed."""


@dataclass(frozen=True, slots=True)
class ProcessedTableArtifact:
    data: bytes
    file_name: str


class TableExtractor:
    GROUND_GRID_SCHEMA_NAME = "GroundGridFlat.bytes"
    RHYTHM_BEATMAP_ARCHIVE_NAME = "RhythmBeatmapData.zip"

    def __init__(
        self,
        table_file_folder: str,
        extract_folder: str,
        flat_data_dir: str,
        logger: LoggerPort | None = None,
    ) -> None:
        self.table_file_folder = table_file_folder
        self.extract_folder = extract_folder
        self.flat_data_dir = flat_data_dir
        self.logger = logger or ConsoleLogger()
        self.lower_fb_name_modules: dict[str, Any] = {}
        self.dump_wrapper_lib: ModuleType
        self._load_modules()

    @classmethod
    def from_context(
        cls,
        context: RuntimeContext,
        logger: LoggerPort | None = None,
    ) -> TableExtractor:
        return cls(
            str(Path(context.raw_dir) / "Table"),
            str(Path(context.extract_dir) / "Table"),
            str(Path(context.extract_dir) / "FlatData"),
            logger=logger,
        )

    def _load_modules(self) -> None:
        flat_data_lib = self._load_flat_data_package()
        self.lower_fb_name_modules = {
            name.lower(): value for name, value in flat_data_lib.__dict__.items()
        }

    @staticmethod
    def _ensure_not_cancelled(should_stop: Callable[[], bool] | None) -> None:
        if should_stop is not None and should_stop():
            raise RuntimeError("Extraction cancelled by user.")

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
        path_digest = hashlib.sha1(
            str(flat_data_dir.resolve()).encode("utf-8")
        ).hexdigest()
        package_name = f"ba_downloader_generated_flatdata_{path_digest}"
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

    def _process_bytes_file(self, file_name: str, data: bytes) -> tuple[dict[str, Any], str]:
        flatbuffer_class = self._resolve_flatbuffer_class(file_name)
        normalized_name = flatbuffer_class.__name__

        if normalized_name.endswith("Table"):
            encrypted_error: TableProcessingError | None = None
            try:
                return self._dump_encrypted_table(flatbuffer_class, data)
            except TableProcessingError as exc:
                encrypted_error = exc

            try:
                return self._dump_flatbuffer_payload(flatbuffer_class, data)
            except TableProcessingError as exc:
                raise MalformedTablePayloadError(
                    f"Malformed flatbuffer payload for {file_name}: "
                    f"encrypted decode failed ({encrypted_error}); raw decode failed ({exc})."
                ) from exc

        return self._dump_flatbuffer_payload(flatbuffer_class, data)

    def _resolve_flatbuffer_class(self, file_name: str) -> Any:
        flatbuffer_class = self.lower_fb_name_modules.get(
            file_name.removesuffix(".bytes").lower()
        )
        if flatbuffer_class is None:
            raise UnsupportedSchemaError(
                f"Unsupported schema for {file_name}: generated FlatData class is missing."
            )
        return flatbuffer_class

    def _dump_encrypted_table(self, flatbuffer_class: Any, data: bytes) -> tuple[dict[str, Any], str]:
        try:
            decrypted_data = xor_with_key(flatbuffer_class.__name__, data)
        except (TypeError, ValueError) as exc:
            raise TableDecryptError(
                f"xor/decrypt failed for {flatbuffer_class.__name__}: {exc}"
            ) from exc

        try:
            flat_buffer = flatbuffer_class.GetRootAs(decrypted_data)
            return self.dump_wrapper_lib.dump_table(flat_buffer), f"{flatbuffer_class.__name__}.json"
        except AttributeError as exc:
            raise GeneratedDumpWrapperError(
                f"Generated dump wrapper is missing dump_table for {flatbuffer_class.__name__}: {exc}"
            ) from exc
        except StopIteration as exc:
            raise GeneratedDumpWrapperError(
                f"Generated dump wrapper could not resolve a table dump for {flatbuffer_class.__name__}."
            ) from exc
        except (
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            RuntimeError,
            struct.error,
        ) as exc:
            raise TableDecryptError(
                f"xor/decrypt failed for {flatbuffer_class.__name__}: {exc}"
            ) from exc

    def _dump_flatbuffer_payload(
        self,
        flatbuffer_class: Any,
        data: bytes,
    ) -> tuple[dict[str, Any], str]:
        dump_function_name = f"dump_{flatbuffer_class.__name__}"
        try:
            dump_function = getattr(self.dump_wrapper_lib, dump_function_name)
        except AttributeError as exc:
            raise GeneratedDumpWrapperError(
                f"Generated dump wrapper is missing {dump_function_name}."
            ) from exc

        try:
            flat_buffer = flatbuffer_class.GetRootAs(data)
            return dump_function(flat_buffer), f"{flatbuffer_class.__name__}.json"
        except StopIteration as exc:
            raise GeneratedDumpWrapperError(
                f"Generated dump wrapper could not resolve a table dump for {flatbuffer_class.__name__}."
            ) from exc
        except (
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            RuntimeError,
            struct.error,
        ) as exc:
            raise MalformedTablePayloadError(
                f"Malformed flatbuffer payload for {flatbuffer_class.__name__}: {exc}"
            ) from exc

    @staticmethod
    def _process_json_file(data: bytes) -> bytes:
        try:
            data.decode("utf8")
        except UnicodeDecodeError:
            return b""
        return data

    def _process_db_file(
        self,
        file_path: str,
        table_name: str = "",
        *,
        should_stop: Callable[[], bool] | None = None,
    ) -> list[DBTable]:
        with TableDatabase(file_path) as db:
            tables: list[DBTable] = []
            table_list = [table_name] if table_name else db.get_table_list()

            for table in table_list:
                self._ensure_not_cancelled(should_stop)
                tables.append(self._read_database_table(db, table, should_stop=should_stop))
            return tables

    def _read_database_table(
        self,
        db: TableDatabase,
        table_name: str,
        *,
        should_stop: Callable[[], bool] | None = None,
    ) -> DBTable:
        columns = db.get_table_column_structure(table_name)
        rows: list[tuple] = db.get_table_data(table_name)[1]
        table_data: list[list[Any]] = []
        schema_name = table_name.replace("DBSchema", "Excel")

        for row in rows:
            self._ensure_not_cancelled(should_stop)
            row_data = []
            for column, value in zip(columns, row, strict=True):
                row_data.append(self._convert_database_value(schema_name, table_name, column, value))
            table_data.append(row_data)

        return DBTable(table_name, columns, table_data)

    def _convert_database_value(
        self,
        schema_name: str,
        table_name: str,
        column: Any,
        value: Any,
    ) -> Any:
        column_type = SQLiteDataType[column.data_type].value
        if column_type is bytes:
            try:
                processed, _ = self._process_bytes_file(schema_name, value)
                return processed
            except TableProcessingError as exc:
                self.logger.warn(
                    f"Skipping bytes field {column.name} in {table_name}: {exc}"
                )
                return {}
        if column_type is bool:
            return bool(value)
        return value

    def _process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact:
        if (detect_type or file_name.endswith(".json")) and (
            json_bytes := self._process_json_file(file_data)
        ):
            return ProcessedTableArtifact(json_bytes, file_name)

        if detect_type or file_name.endswith(".bytes"):
            file_dict, normalized_name = self._process_bytes_file(file_name, file_data)
            return ProcessedTableArtifact(
                json.dumps(file_dict, indent=4, ensure_ascii=False).encode("utf8"),
                normalized_name,
            )

        raise UnsupportedSchemaError(
            f"Unsupported entry {file_name} in {archive_name}: no matching table processor."
        )

    @staticmethod
    def _is_ground_grid_patch_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name)
        return archive_name.startswith("TablePatchPack_") and "GroundGrid" in archive_name

    @staticmethod
    def _is_ground_stage_patch_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name)
        return archive_name.startswith("TablePatchPack_") and "GroundStage" in archive_name

    @classmethod
    def _is_rhythm_beatmap_archive(cls, file_name: str) -> bool:
        return path.basename(file_name) == cls.RHYTHM_BEATMAP_ARCHIVE_NAME

    @staticmethod
    def _write_processed_file(
        extract_folder: Path,
        processed_file: ProcessedTableArtifact,
    ) -> None:
        output_path = extract_folder / processed_file.file_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(processed_file.data)

    def _warn_skipped_entry(
        self,
        archive_name: str,
        entry_name: str,
        warnings: list[str],
        error: str,
    ) -> None:
        warning = f"Skipping {entry_name} in {archive_name}: {error}"
        self.logger.warn(warning)
        warnings.append(warning)

    def extract_db_file(
        self,
        file_path: str,
        *,
        should_stop: Callable[[], bool] | None = None,
    ) -> bool:
        source_path = path.join(self.table_file_folder, file_path)
        try:
            db_tables = self._process_db_file(source_path, should_stop=should_stop)
        except RuntimeError as exc:
            if str(exc) == "Extraction cancelled by user.":
                raise
            self.logger.error(f"Failed to process {file_path}: {exc}")
            return False
        except (FileNotFoundError, OSError, ValueError, sqlite3.Error) as exc:
            self.logger.error(f"Failed to process {file_path}: {exc}")
            return False

        if not db_tables:
            self.logger.warn(f"No readable tables were found in {file_path}.")
            return False

        db_name = file_path.removesuffix(".db")
        db_extract_folder = path.join(self.extract_folder, db_name)
        os.makedirs(db_extract_folder, exist_ok=True)
        for table in db_tables:
            output_path = path.join(db_extract_folder, f"{table.name}.json")
            with open(output_path, "w", encoding="utf8") as file_handle:
                json.dump(
                    TableDatabase.convert_to_list_dict(table),
                    file_handle,
                    indent=4,
                    ensure_ascii=False,
                )
        return True

    def extract_zip_file(
        self,
        file_name: str,
        *,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        warnings: list[str] = []

        if self._is_rhythm_beatmap_archive(archive_name):
            self.logger.warn(
                f"Skipping {archive_name}: beatmap semantic parser is not implemented yet."
            )
            return

        try:
            if self._is_ground_grid_patch_archive(archive_name):
                self._extract_ground_grid_patch_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                )
            elif self._is_ground_stage_patch_archive(archive_name):
                self._extract_ground_stage_patch_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                )
            else:
                self._extract_standard_zip_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                )
        except RuntimeError as exc:
            if str(exc) == "Extraction cancelled by user.":
                raise
            self.logger.error(f"Failed to process {archive_name}: {exc}")
            return
        except (BadZipFile, FileNotFoundError, OSError, ValueError) as exc:
            self.logger.error(f"Failed to process {archive_name}: {exc}")
            return

        if warnings:
            self.logger.warn(
                f"Skipped {len(warnings)} entries while extracting {archive_name}."
            )

    def _extract_standard_zip_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        extract_folder = Path(self.extract_folder) / archive_name.removesuffix(".zip")
        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            for item_name in archive.namelist():
                self._ensure_not_cancelled(should_stop)
                self._extract_zip_entry(
                    archive_name=archive_name,
                    item_name=item_name,
                    archive=archive,
                    extract_folder=extract_folder,
                    warnings=warnings,
                    should_stop=should_stop,
                )

    def _extract_ground_grid_patch_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        outer_extract_folder = Path(self.extract_folder) / archive_name.removesuffix(".zip")

        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            for item_name in archive.namelist():
                self._ensure_not_cancelled(should_stop)
                item_data = archive.read(item_name)
                try:
                    self._extract_ground_grid_inner_archive(
                        archive_name=archive_name,
                        item_name=item_name,
                        item_data=item_data,
                        extract_folder=outer_extract_folder,
                        warnings=warnings,
                        should_stop=should_stop,
                    )
                except BadZipFile as exc:
                    self._warn_skipped_entry(
                        archive_name,
                        item_name,
                        warnings,
                        str(exc),
                    )

    def _extract_ground_grid_inner_archive(
        self,
        *,
        archive_name: str,
        item_name: str,
        item_data: bytes,
        extract_folder: Path,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        with ZipFile(BytesIO(item_data), "r") as inner_archive:
            inner_archive.setpassword(zip_password(path.basename(item_name)))
            for inner_item_name in inner_archive.namelist():
                self._ensure_not_cancelled(should_stop)
                try:
                    inner_item_data = inner_archive.read(inner_item_name)
                except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                    self._warn_skipped_entry(
                        archive_name,
                        f"{item_name}/{inner_item_name}",
                        warnings,
                        str(exc),
                    )
                    continue
                try:
                    processed_file = self._process_zip_file(
                        archive_name,
                        self.GROUND_GRID_SCHEMA_NAME,
                        inner_item_data,
                        detect_type=True,
                    )
                except TableProcessingError as exc:
                    self._warn_skipped_entry(
                        archive_name,
                        f"{item_name}/{inner_item_name}",
                        warnings,
                        str(exc),
                    )
                    continue

                self._ensure_not_cancelled(should_stop)
                self._write_processed_file(
                    extract_folder / Path(item_name).stem,
                    processed_file,
                )

    def _extract_ground_stage_patch_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        outer_extract_folder = Path(self.extract_folder) / archive_name.removesuffix(".zip")

        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            for item_name in archive.namelist():
                self._ensure_not_cancelled(should_stop)
                item_data = archive.read(item_name)
                try:
                    self._extract_ground_stage_inner_archive(
                        archive_name=archive_name,
                        item_name=item_name,
                        item_data=item_data,
                        extract_folder=outer_extract_folder,
                        warnings=warnings,
                        should_stop=should_stop,
                    )
                except BadZipFile as exc:
                    self._warn_skipped_entry(
                        archive_name,
                        item_name,
                        warnings,
                        str(exc),
                    )

        self.logger.info(
            f"Extracted raw GroundStage payloads from {archive_name}; semantic parser is not implemented yet."
        )

    def _extract_ground_stage_inner_archive(
        self,
        *,
        archive_name: str,
        item_name: str,
        item_data: bytes,
        extract_folder: Path,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        with ZipFile(BytesIO(item_data), "r") as inner_archive:
            inner_archive.setpassword(zip_password(path.basename(item_name)))
            for inner_item_name in inner_archive.namelist():
                self._ensure_not_cancelled(should_stop)
                try:
                    inner_item_data = inner_archive.read(inner_item_name)
                except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                    self._warn_skipped_entry(
                        archive_name,
                        f"{item_name}/{inner_item_name}",
                        warnings,
                        str(exc),
                    )
                    continue

                self._ensure_not_cancelled(should_stop)
                self._write_processed_file(
                    extract_folder / Path(item_name).stem,
                    ProcessedTableArtifact(inner_item_data, inner_item_name),
                )

    def _extract_zip_entry(
        self,
        *,
        archive_name: str,
        item_name: str,
        archive: ZipFile,
        extract_folder: Path,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self._ensure_not_cancelled(should_stop)
        item_data = archive.read(item_name)
        processed_file: ProcessedTableArtifact | None = None

        try:
            processed_file = self._process_zip_file(
                archive_name,
                item_name,
                item_data,
            )
        except TableProcessingError as first_error:
            try:
                detect_name = (
                    f"{archive_name.removesuffix('.zip')}Flat"
                    if "RootMotion" in archive_name
                    else item_name
                )
                processed_file = self._process_zip_file(
                    archive_name,
                    detect_name,
                    item_data,
                    detect_type=True,
                )
                if "RootMotion" in archive_name:
                    processed_file = ProcessedTableArtifact(
                        processed_file.data,
                        item_name,
                    )
            except TableProcessingError as second_error:
                self._warn_skipped_entry(
                    archive_name,
                    item_name,
                    warnings,
                    f"{first_error}; fallback failed ({second_error}).",
                )
                return

        self._ensure_not_cancelled(should_stop)
        self._write_processed_file(extract_folder, processed_file)

    def extract_table(
        self,
        file_path: str,
        *,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        if not file_path.endswith((".zip", ".db")):
            self.logger.warn(
                f"The file {file_path} is not supported in current implementation."
            )
            return

        if file_path.endswith(".db"):
            self.extract_db_file(file_path, should_stop=should_stop)
            return

        self.extract_zip_file(file_path, should_stop=should_stop)
