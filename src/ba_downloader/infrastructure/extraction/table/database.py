from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from ba_downloader.domain.models.database import DBColumn, DBTable, SQLiteDataType
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.codecs import (
    TablePayloadCodecAdapter,
)
from ba_downloader.infrastructure.extraction.table.models import (
    ProgressCallback,
    TableProcessingError,
)
from ba_downloader.infrastructure.extraction.table.payload_router import (
    TablePayloadCodec,
    TablePayloadRouter,
)
from ba_downloader.infrastructure.extraction.table.progress import (
    TableExtractionProgress,
)
from ba_downloader.infrastructure.storage import TableDatabase


class DatabasePathResolver(Protocol):
    def resolve(self, database_path: Path) -> Path: ...


class TableDatabaseReader:
    def __init__(
        self,
        codec_adapter: TablePayloadCodecAdapter,
        payload_router: TablePayloadRouter,
        logger: LoggerPort,
        progress: TableExtractionProgress,
        database_path_resolver: DatabasePathResolver | None = None,
    ) -> None:
        self.codec_adapter = codec_adapter
        self.payload_router = payload_router
        self.logger = logger
        self.progress = progress
        self.database_path_resolver = database_path_resolver

    def process_db_file(
        self,
        file_path: str,
        table_name: str = "",
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[DBTable]:
        source_path = Path(file_path)
        database_path = (
            self.database_path_resolver.resolve(source_path)
            if self.database_path_resolver is not None
            else source_path
        )
        with TableDatabase(str(database_path)) as db:
            tables: list[DBTable] = []
            table_list = [table_name] if table_name else db.get_table_list()
            db_name = source_path.name

            for index, table in enumerate(table_list, start=1):
                self.progress.ensure_not_cancelled(should_stop)
                tables.append(
                    self.read_database_table(
                        db,
                        table,
                        db_name=db_name,
                        should_stop=should_stop,
                    )
                )
                self.progress.notify_progress(
                    progress_callback,
                    index,
                    len(table_list),
                    "tables",
                )
            return tables

    def read_database_table(
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
            self.progress.ensure_not_cancelled(should_stop)
            row_data = []
            for column, value in zip(columns, row, strict=True):
                row_data.append(
                    self.convert_database_value(
                        db_name,
                        schema_name,
                        table_name,
                        column,
                        value,
                    )
                )
            table_data.append(row_data)

        return DBTable(table_name, columns, table_data)

    def convert_database_value(
        self,
        db_name: str,
        schema_name: str,
        table_name: str,
        column: Any,
        value: Any,
        *,
        strict_blob: bool = False,
    ) -> Any:
        column_type = SQLiteDataType[column.data_type].value
        if column_type is bytes:
            route = self.payload_router.resolve_database_blob(
                db_name,
                table_name,
                column.name,
            )
            if route.codec is TablePayloadCodec.MEMORYPACK:
                return self.codec_adapter.convert_memorypack_database_value(
                    db_name,
                    table_name,
                    column.name,
                    value,
                    route.root_type,
                    allow_partial=route.allow_partial_memorypack,
                )
            try:
                processed, _ = self.codec_adapter.process_bytes_file(
                    schema_name,
                    value,
                )
                return processed
            except TableProcessingError as exc:
                if strict_blob:
                    raise TableProcessingError(
                        f"Failed to decode bytes field {column.name} in "
                        f"required table {table_name}: {exc}"
                    ) from exc
                self.logger.warn(
                    f"Skipping bytes field {column.name} in {table_name}: {exc}"
                )
                return {}
        if column_type is bool:
            return bool(value)
        return value

    def process_character_index_tables(
        self,
        file_path: str,
        table_names: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        source_path = Path(file_path)
        retryable_errors = (
            LookupError,
            OSError,
            sqlite3.Error,
            TableProcessingError,
            TypeError,
            ValueError,
        )
        for attempt in range(2):
            database_path = (
                self.database_path_resolver.resolve(source_path)
                if self.database_path_resolver is not None
                else source_path
            )
            try:
                return self._read_character_index_tables(
                    source_path,
                    database_path,
                    table_names,
                )
            except retryable_errors:
                invalidator = getattr(
                    self.database_path_resolver,
                    "invalidate",
                    None,
                )
                if attempt != 0 or not callable(invalidator):
                    raise
                invalidator(source_path)
        raise AssertionError("database retry loop exhausted unexpectedly")

    def _read_character_index_tables(
        self,
        source_path: Path,
        database_path: Path,
        table_names: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        result: dict[str, list[dict[str, Any]]] = {}
        with sqlite3.connect(database_uri, uri=True) as connection:
            inventory_cursor = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            )
            inventory = {
                str(row[0]) for row in inventory_cursor if row and row[0] is not None
            }
            missing = [name for name in table_names if name not in inventory]
            if missing:
                raise LookupError(
                    "Required character index database tables are missing: "
                    + ", ".join(missing)
                )

            for table_name in table_names:
                quoted_table = '"' + table_name.replace('"', '""') + '"'
                rows: list[dict[str, Any]] = []
                cursor = connection.execute(f'SELECT "Bytes" FROM {quoted_table};')
                schema_name = table_name.replace("DBSchema", "Excel")
                bytes_column = DBColumn(name="Bytes", data_type="BLOB")
                for row_index, row in enumerate(cursor, start=1):
                    if not row or not isinstance(row[0], bytes):
                        raise TableProcessingError(
                            f"Required table {table_name} row {row_index} has no "
                            "binary Bytes payload."
                        )
                    decoded = self.convert_database_value(
                        source_path.name,
                        schema_name,
                        table_name,
                        bytes_column,
                        row[0],
                        strict_blob=True,
                    )
                    if not isinstance(decoded, dict) or not decoded:
                        raise TableProcessingError(
                            f"Required table {table_name} row {row_index} decoded "
                            "to an empty or invalid payload."
                        )
                    rows.append({"Bytes": decoded})
                if not rows:
                    raise LookupError(
                        f"Required character index database table {table_name} is empty."
                    )
                result[table_name] = rows
        return result


class TableDatabaseJsonWriter:
    def write_tables(
        self,
        extract_folder: str,
        file_path: str,
        db_tables: list[DBTable],
    ) -> None:
        db_name = file_path.removesuffix(".db")
        db_extract_folder = os.path.join(extract_folder, db_name)
        os.makedirs(db_extract_folder, exist_ok=True)
        for table in db_tables:
            output_path = os.path.join(db_extract_folder, f"{table.name}.json")
            with open(output_path, "w", encoding="utf8") as file_handle:
                json.dump(
                    TableDatabase.convert_to_list_dict(table),
                    file_handle,
                    indent=4,
                    ensure_ascii=False,
                )
