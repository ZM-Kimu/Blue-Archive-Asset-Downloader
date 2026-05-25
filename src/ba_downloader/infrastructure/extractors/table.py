from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import struct
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from os import path
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from ba_downloader.domain.models.database import DBTable, SQLiteDataType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.table_payload_router import (
    TablePayloadCodec,
    TablePayloadRouter,
)
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
from ba_downloader.infrastructure.schema.common.generated_registry import (
    GeneratedSchemaRegistry,
)
from ba_downloader.infrastructure.schema.flatbuffer.reader import FlatBufferExporter
from ba_downloader.infrastructure.schema.memorypack.formatters import (
    MemoryPackFormatterRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.reader import (
    MemoryPackReader,
    MemoryPackSchemaRegistry,
)
from ba_downloader.infrastructure.storage import TableDatabase
from ba_downloader.shared.crypto.encryption import (
    create_key,
    xor_with_key,
    zip_password,
)

ProgressCallback = Callable[[str], None]


class TableProcessingError(RuntimeError):
    """Raised when a table payload cannot be processed."""


class UnsupportedSchemaError(TableProcessingError):
    """Raised when no generated FlatBufferData schema matches a payload."""


class FlatBufferExportError(TableProcessingError):
    """Raised when generated FlatBufferData schemas cannot export a payload."""


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
    GROUND_NODE_LAYER_SCHEMA_NAME = "GroundNodeLayerFlat.bytes"
    RHYTHM_BEATMAP_ARCHIVE_NAME = "RhythmBeatmapData.zip"
    MEMORYPACK_FORMATTER_SIDECAR_NAME = "memorypack_formatters.json"
    RAW_SIDECAR_ENTRY_SUFFIXES = frozenset({".bin", ".txt"})
    GL_GROUND_ARCHIVE_PREFIXES = ("sb_", "rb_", "rd_", "db_", "c_sb_")
    GL_C_SB_RAW_SCRIPT_KEYWORDS = (
        "destroyhyakkiyakomatsuri",
        "wildhuntstreet",
        "expresstrain",
        "hyakkiyakomatsuri",
        "hyakkiyakomoviestreet",
        "hyakkiyakonorthtown",
        "trainroof",
    )
    GL_RAW_SCRIPT_TEST_PREFIXES = (
        "basementtest",
        "character_resource_",
        "charactertest",
        "ch0265test",
        "chesedscenariotest",
        "combattest_",
        "damagetest_",
        "effectcountlimittest_",
        "groundpassivetest",
        "holdtest",
        "hovercrafttest",
        "hyakkiyako",
        "newyearpathvisualtest",
        "np186test",
        "npctest",
        "overridetest_",
        "playground_obstacleset_",
        "raidtest",
    )
    GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES = (
        "camerarotatetest.zip",
        "changelooktargettest.zip",
        "ch0265test2.zip",
    )

    def __init__(
        self,
        table_file_folder: str,
        extract_folder: str,
        flatbuffer_data_dir: str,
        logger: LoggerPort | None = None,
        memorypack_data_dir: str | None = None,
        memorypack_formatter_path: str | None = None,
    ) -> None:
        self.table_file_folder = table_file_folder
        self.extract_folder = extract_folder
        self.flatbuffer_data_dir = flatbuffer_data_dir
        self.memorypack_data_dir = memorypack_data_dir or str(
            Path(flatbuffer_data_dir).parent / "MemoryPackData"
        )
        self.memorypack_formatter_path = memorypack_formatter_path or str(
            Path(flatbuffer_data_dir).parent
            / "Dumps"
            / self.MEMORYPACK_FORMATTER_SIDECAR_NAME
        )
        self.logger = logger or ConsoleLogger()
        self.lower_schema_registry: dict[str, Any] = {}
        self.flatbuffer_exporter: FlatBufferExporter
        self.payload_router = TablePayloadRouter()
        self.memorypack_schema_registry = MemoryPackSchemaRegistry(types={}, enums={})
        self.memorypack_formatter_registry: MemoryPackFormatterRegistry | None = None
        self._memorypack_warning_keys: set[tuple[str, str, str, str, str]] = set()
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
            str(Path(context.extract_dir) / "FlatBufferData"),
            logger=logger,
        )

    def _load_modules(self) -> None:
        registry = self._load_flat_buffer_data_registry()
        self.flatbuffer_exporter = FlatBufferExporter(
            registry.types,
            registry.enums,
        )
        self.lower_schema_registry = self.flatbuffer_exporter.lower_type_registry
        self._load_memorypack_data_registry()
        self._load_memorypack_formatter_registry()

    @staticmethod
    def _ensure_not_cancelled(should_stop: Callable[[], bool] | None) -> None:
        if should_stop is not None and should_stop():
            raise RuntimeError("Extraction cancelled by user.")

    @staticmethod
    def _is_generated_stop_iteration(exc: RuntimeError) -> bool:
        return str(exc) == "generator raised StopIteration"

    def _load_flat_buffer_data_registry(self) -> GeneratedSchemaRegistry:
        try:
            return GeneratedSchemaRegistry.from_directory(
                self.flatbuffer_data_dir,
                type_registry_name="FLATBUFFER_TYPES",
                enum_registry_name="FLATBUFFER_ENUMS",
                package_prefix="ba_downloader_generated_flatbufferdata",
            )
        except FileNotFoundError as exc:
            message = str(exc)
            if "directory does not exist" in message:
                raise FileNotFoundError(
                    f"FlatBufferData directory does not exist: {self.flatbuffer_data_dir}."
                ) from exc
            if "initializer is missing" in message:
                raise FileNotFoundError(
                    "FlatBufferData package initializer is missing: "
                    f"{Path(self.flatbuffer_data_dir) / '__init__.py'}."
                ) from exc
            if "registry is missing" in message:
                raise FileNotFoundError(
                    f"FlatBufferData registry is missing: {Path(self.flatbuffer_data_dir) / '_registry.py'}."
                ) from exc
            raise
        except ImportError as exc:
            raise ImportError(
                f"Unable to create FlatBufferData import spec for {self.flatbuffer_data_dir}."
            ) from exc

    def _load_memorypack_data_registry(self) -> None:
        try:
            self.memorypack_schema_registry = MemoryPackSchemaRegistry.from_directory(
                self.memorypack_data_dir,
            )
        except (FileNotFoundError, ImportError, TypeError):
            self.memorypack_schema_registry = MemoryPackSchemaRegistry(
                types={},
                enums={},
            )

    def _load_memorypack_formatter_registry(self) -> None:
        sidecar_path = Path(self.memorypack_formatter_path)
        if not sidecar_path.is_file():
            self.memorypack_formatter_registry = None
            return
        try:
            self.memorypack_formatter_registry = MemoryPackFormatterRegistry.from_file(
                sidecar_path,
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.memorypack_formatter_registry = None

    def _process_bytes_file(
        self, file_name: str, data: bytes
    ) -> tuple[dict[str, Any] | list[Any], str]:
        flatbuffer_schema = self._resolve_flatbuffer_schema(file_name)
        normalized_name = flatbuffer_schema.__name__

        if normalized_name.endswith("Table"):
            encrypted_error: TableProcessingError | None = None
            try:
                return self._dump_encrypted_table(flatbuffer_schema, data)
            except TableProcessingError as exc:
                encrypted_error = exc

            try:
                return self._dump_flatbuffer_payload(flatbuffer_schema, data)
            except TableProcessingError as exc:
                raise MalformedTablePayloadError(
                    f"Malformed flatbuffer payload for {file_name}: "
                    f"encrypted decode failed ({encrypted_error}); raw decode failed ({exc})."
                ) from exc

        return self._dump_flatbuffer_payload(flatbuffer_schema, data)

    def _resolve_flatbuffer_schema(self, file_name: str) -> Any:
        flatbuffer_schema = self.lower_schema_registry.get(
            file_name.removesuffix(".bytes").lower()
        )
        if flatbuffer_schema is None:
            raise UnsupportedSchemaError(
                f"Unsupported schema for {file_name}: generated FlatBufferData schema is missing."
            )
        return flatbuffer_schema

    def _dump_encrypted_table(
        self, flatbuffer_schema: Any, data: bytes
    ) -> tuple[dict[str, Any] | list[Any], str]:
        try:
            decrypted_data = xor_with_key(flatbuffer_schema.__name__, data)
        except (TypeError, ValueError) as exc:
            raise TableDecryptError(
                f"xor/decrypt failed for {flatbuffer_schema.__name__}: {exc}"
            ) from exc

        try:
            excel_name = flatbuffer_schema.__name__.removesuffix("Table")
            password = create_key(excel_name.removesuffix("Excel"))
            return (
                self.flatbuffer_exporter.export_payload(
                    flatbuffer_schema,
                    decrypted_data,
                    password=password,
                ),
                f"{flatbuffer_schema.__name__}.json",
            )
        except RuntimeError as exc:
            raise TableDecryptError(
                f"xor/decrypt failed for {flatbuffer_schema.__name__}: {exc}"
            ) from exc
        except (
            EOFError,
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            struct.error,
        ) as exc:
            raise TableDecryptError(
                f"xor/decrypt failed for {flatbuffer_schema.__name__}: {exc}"
            ) from exc

    def _dump_flatbuffer_payload(
        self,
        flatbuffer_schema: Any,
        data: bytes,
    ) -> tuple[dict[str, Any] | list[Any], str]:
        try:
            return (
                self.flatbuffer_exporter.export_payload(flatbuffer_schema, data),
                f"{flatbuffer_schema.__name__}.json",
            )
        except RuntimeError as exc:
            raise MalformedTablePayloadError(
                f"Malformed flatbuffer payload for {flatbuffer_schema.__name__}: {exc}"
            ) from exc
        except (
            EOFError,
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            struct.error,
        ) as exc:
            raise MalformedTablePayloadError(
                f"Malformed flatbuffer payload for {flatbuffer_schema.__name__}: {exc}"
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
        progress_callback: ProgressCallback | None = None,
    ) -> list[DBTable]:
        with TableDatabase(file_path) as db:
            tables: list[DBTable] = []
            table_list = [table_name] if table_name else db.get_table_list()
            db_name = Path(file_path).name

            for index, table in enumerate(table_list, start=1):
                self._ensure_not_cancelled(should_stop)
                tables.append(
                    self._read_database_table(
                        db,
                        table,
                        db_name=db_name,
                        should_stop=should_stop,
                    )
                )
                self._notify_progress(
                    progress_callback,
                    index,
                    len(table_list),
                    "tables",
                )
            return tables

    def _read_database_table(
        self,
        db: TableDatabase,
        table_name: str,
        *,
        db_name: str,
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
                row_data.append(
                    self._convert_database_value(
                        db_name,
                        schema_name,
                        table_name,
                        column,
                        value,
                    )
                )
            table_data.append(row_data)

        return DBTable(table_name, columns, table_data)

    def _convert_database_value(
        self,
        db_name: str,
        schema_name: str,
        table_name: str,
        column: Any,
        value: Any,
    ) -> Any:
        column_type = SQLiteDataType[column.data_type].value
        if column_type is bytes:
            route = self.payload_router.resolve_database_blob(
                db_name,
                table_name,
                column.name,
            )
            if route.codec is TablePayloadCodec.MEMORYPACK:
                return self._convert_memorypack_database_value(
                    db_name,
                    table_name,
                    column.name,
                    value,
                    route.root_type,
                    allow_partial=route.allow_partial_memorypack,
                )
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

    def _convert_memorypack_database_value(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
        value: bytes,
        root_type: str,
        *,
        allow_partial: bool,
    ) -> dict[str, Any]:
        if self.memorypack_formatter_registry is not None:
            formatter = self.memorypack_formatter_registry.resolve(root_type)
            if formatter is not None and formatter.is_available:
                try:
                    return MemoryPackReader(value).read_formatter_object(
                        root_type,
                        self.memorypack_schema_registry,
                        self.memorypack_formatter_registry,
                    )
                except (EOFError, TypeError, ValueError, struct.error):
                    pass

        if allow_partial:
            try:
                result = MemoryPackReader(value).read_cn_table_dao_partial(
                    root_type,
                    self.memorypack_schema_registry,
                )
            except (EOFError, TypeError, ValueError, struct.error) as exc:
                message = f"MemoryPack partial decode failed for {root_type}: {exc}"
                self._warn_memorypack_database_value_once(
                    db_name,
                    table_name,
                    column_name,
                    root_type,
                    message,
                )
                return self._memorypack_raw_fallback(value, root_type, error=str(exc))

            return result

        message = f"MemoryPack formatter layout is unavailable for {root_type}."
        self._warn_memorypack_database_value_once(
            db_name,
            table_name,
            column_name,
            root_type,
            message,
        )
        return self._memorypack_raw_fallback(value, root_type)

    def _warn_memorypack_database_value_once(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
        root_type: str,
        message: str,
    ) -> None:
        warning_key = (db_name, table_name, column_name, root_type, message)
        if warning_key in self._memorypack_warning_keys:
            return
        self._memorypack_warning_keys.add(warning_key)
        self.logger.warn(
            f"Using raw MemoryPack fallback for bytes field {column_name} "
            f"in {table_name}: {message}"
        )

    @staticmethod
    def _memorypack_raw_fallback(
        value: bytes,
        root_type: str,
        *,
        error: str = "MemoryPack formatter layout is unavailable.",
    ) -> dict[str, Any]:
        return {
            "__memorypack_error__": error,
            "__root_type__": root_type,
            "__payload_size__": len(value),
            "__payload_sha256__": hashlib.sha256(value).hexdigest(),
            "__payload_head__": value[:64].hex(),
        }

    def _process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact:
        if file_name.endswith(".json") and (
            json_bytes := self._process_json_file(file_data)
        ):
            return ProcessedTableArtifact(json_bytes, file_name)

        if Path(file_name).suffix.lower() in self.RAW_SIDECAR_ENTRY_SUFFIXES:
            return ProcessedTableArtifact(file_data, file_name)

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
        return (
            archive_name.startswith("TablePatchPack_") and "GroundGrid" in archive_name
        )

    @staticmethod
    def _is_ground_stage_patch_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name)
        return (
            archive_name.startswith("TablePatchPack_") and "GroundStage" in archive_name
        )

    @classmethod
    def _is_gl_ground_archive(cls, file_name: str) -> bool:
        archive_name = path.basename(file_name)
        lower_name = archive_name.lower()
        return lower_name.endswith(".zip") and lower_name.startswith(
            cls.GL_GROUND_ARCHIVE_PREFIXES
        )

    @classmethod
    def _is_gl_c_sb_raw_script_archive(cls, file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return archive_name.endswith(".zip") and archive_name.startswith(
            "c_sb_"
        ) and any(keyword in archive_name for keyword in cls.GL_C_SB_RAW_SCRIPT_KEYWORDS)

    @classmethod
    def _resolve_gl_ground_schema_name(cls, archive_name: str) -> str:
        if "_nodelayer" in archive_name.lower():
            return cls.GROUND_NODE_LAYER_SCHEMA_NAME
        return cls.GROUND_GRID_SCHEMA_NAME

    @staticmethod
    def _is_gl_numeric_stage_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return (
            archive_name.endswith(".zip")
            and archive_name[:1].isdigit()
            and "eliminateraid" not in archive_name
        )

    @staticmethod
    def _is_gl_eliminate_raid_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return archive_name.endswith(".zip") and "eliminateraid" in archive_name

    @staticmethod
    def _is_gl_enemy_boss_script_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return (
            archive_name.endswith(".zip")
            and archive_name.startswith("en")
            and len(archive_name) >= 6
            and archive_name[2:6].isdigit()
        )

    @staticmethod
    def _is_mgs_logic_ground_archive(file_name: str) -> bool:
        return path.basename(file_name) == "MGSLogicGroundData.zip"

    @classmethod
    def _is_gl_raw_script_test_archive(cls, file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return (
            archive_name.startswith(cls.GL_RAW_SCRIPT_TEST_PREFIXES)
            or "obstest" in archive_name
            or "timelinetest" in archive_name
            or "emojitest" in archive_name
            or archive_name in cls.GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES
        )

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

    @staticmethod
    def _notify_progress(
        progress_callback: ProgressCallback | None,
        current: int,
        total: int,
        unit: str,
    ) -> None:
        if progress_callback is not None:
            progress_callback(f"{current}/{total} {unit}")

    def extract_db_file(
        self,
        file_path: str,
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> bool:
        source_path = path.join(self.table_file_folder, file_path)
        try:
            db_tables = self._process_db_file(
                source_path,
                should_stop=should_stop,
                progress_callback=progress_callback,
            )
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
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        warnings: list[str] = []

        if self._is_rhythm_beatmap_archive(archive_name):
            self._extract_raw_zip_archive(
                file_name,
                warnings=warnings,
                should_stop=should_stop,
                progress_callback=progress_callback,
                info_message=(
                    f"Extracted raw rhythm beatmap payloads from {archive_name}; "
                    "semantic parser is not implemented yet."
                ),
            )
            return

        try:
            if self._is_ground_grid_patch_archive(archive_name):
                self._extract_ground_grid_patch_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif self._is_ground_stage_patch_archive(archive_name):
                self._extract_ground_stage_patch_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif self._is_gl_c_sb_raw_script_archive(archive_name):
                self._extract_raw_zip_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif self._is_gl_ground_archive(archive_name):
                self._extract_gl_ground_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif (
                self._is_gl_eliminate_raid_archive(archive_name)
                or self._is_gl_enemy_boss_script_archive(archive_name)
                or self._is_gl_raw_script_test_archive(archive_name)
            ):
                self._extract_raw_zip_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif self._is_gl_numeric_stage_archive(archive_name):
                self._extract_gl_numeric_stage_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif self._is_mgs_logic_ground_archive(archive_name):
                self._extract_mgs_logic_ground_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            else:
                self._extract_standard_zip_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
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
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        extract_folder = Path(self.extract_folder) / archive_name.removesuffix(".zip")
        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
                    self._ensure_not_cancelled(should_stop)
                    self._extract_zip_entry(
                        archive_name=archive_name,
                        item_name=item_name,
                        archive=archive,
                        extract_folder=extract_folder,
                        warnings=warnings,
                        should_stop=should_stop,
                    )
                finally:
                    self._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def _extract_ground_grid_patch_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        outer_extract_folder = Path(self.extract_folder) / archive_name.removesuffix(
            ".zip"
        )

        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
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
                finally:
                    self._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
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
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        outer_extract_folder = Path(self.extract_folder) / archive_name.removesuffix(
            ".zip"
        )

        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
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
                finally:
                    self._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

        self.logger.info(
            f"Extracted raw GroundStage payloads from {archive_name}; semantic parser is not implemented yet."
        )

    def _extract_gl_ground_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        schema_name = self._resolve_gl_ground_schema_name(archive_name)
        extract_folder = Path(self.extract_folder) / archive_name.removesuffix(".zip")

        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
                    self._ensure_not_cancelled(should_stop)
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    try:
                        processed_file = self._process_zip_file(
                            archive_name,
                            schema_name,
                            item_data,
                            detect_type=True,
                        )
                    except TableProcessingError as exc:
                        self._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    self._ensure_not_cancelled(should_stop)
                    self._write_processed_file(extract_folder, processed_file)
                finally:
                    self._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def _extract_gl_numeric_stage_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        extract_folder = Path(self.extract_folder) / archive_name.removesuffix(".zip")

        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
                    self._ensure_not_cancelled(should_stop)
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    self._write_processed_file(
                        extract_folder,
                        ProcessedTableArtifact(
                            data=item_data,
                            file_name=path.basename(item_name),
                        ),
                    )
                finally:
                    self._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def _extract_mgs_logic_ground_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        extract_folder = Path(self.extract_folder) / archive_name.removesuffix(".zip")

        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
                    self._ensure_not_cancelled(should_stop)
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    try:
                        processed_file = self._process_zip_file(
                            archive_name,
                            self.GROUND_GRID_SCHEMA_NAME,
                            item_data,
                            detect_type=True,
                        )
                    except TableProcessingError:
                        processed_file = ProcessedTableArtifact(
                            data=item_data,
                            file_name=path.basename(item_name),
                        )

                    self._ensure_not_cancelled(should_stop)
                    self._write_processed_file(extract_folder, processed_file)
                finally:
                    self._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def _extract_raw_zip_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
        info_message: str | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        extract_folder = Path(self.extract_folder) / archive_name.removesuffix(".zip")

        with ZipFile(path.join(self.table_file_folder, file_name), "r") as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
                    self._ensure_not_cancelled(should_stop)
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    self._write_processed_file(
                        extract_folder,
                        ProcessedTableArtifact(
                            data=item_data,
                            file_name=path.basename(item_name),
                        ),
                    )
                finally:
                    self._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

        if info_message:
            self.logger.info(info_message)

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
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        if not file_path.endswith((".zip", ".db")):
            self.logger.warn(
                f"The file {file_path} is not supported in current implementation."
            )
            return

        if file_path.endswith(".db"):
            self.extract_db_file(
                file_path,
                should_stop=should_stop,
                progress_callback=progress_callback,
            )
            return

        self.extract_zip_file(
            file_path,
            should_stop=should_stop,
            progress_callback=progress_callback,
        )
