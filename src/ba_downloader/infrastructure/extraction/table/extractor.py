from __future__ import annotations

import sqlite3
from collections.abc import Callable
from os import path
from pathlib import Path
from typing import Any

from ba_downloader.domain.models.database import DBTable
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    TableArchiveClassifier,
)
from ba_downloader.infrastructure.extraction.table.archives import (
    RawArchiveExporter,
    TableArchiveRouter,
)
from ba_downloader.infrastructure.extraction.table.codecs import (
    TablePayloadCodecAdapter,
)
from ba_downloader.infrastructure.extraction.table.database import (
    TableDatabaseJsonWriter,
    TableDatabaseReader,
)
from ba_downloader.infrastructure.extraction.table.models import (
    FlatBufferExportError,
    MalformedTablePayloadError,
    ProcessedTableArtifact,
    ProgressCallback,
    TableDecryptError,
    TableProcessingError,
    UnsupportedSchemaError,
)
from ba_downloader.infrastructure.extraction.table.payload_router import (
    TablePayloadRouter,
)
from ba_downloader.infrastructure.extraction.table.progress import (
    TableExtractionProgress,
)
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger

__all__ = [
    "FlatBufferExportError",
    "MalformedTablePayloadError",
    "ProcessedTableArtifact",
    "ProgressCallback",
    "TableDecryptError",
    "TableExtractor",
    "TableProcessingError",
    "UnsupportedSchemaError",
]


class TableExtractor:
    GROUND_GRID_SCHEMA_NAME = TableArchiveClassifier.GROUND_GRID_SCHEMA_NAME
    GROUND_NODE_LAYER_SCHEMA_NAME = TableArchiveClassifier.GROUND_NODE_LAYER_SCHEMA_NAME
    RHYTHM_BEATMAP_ARCHIVE_NAME = TableArchiveClassifier.RHYTHM_BEATMAP_ARCHIVE_NAME
    MEMORYPACK_FORMATTER_SIDECAR_NAME = (
        TablePayloadCodecAdapter.MEMORYPACK_FORMATTER_SIDECAR_NAME
    )
    RAW_SIDECAR_ENTRY_SUFFIXES = TablePayloadCodecAdapter.RAW_SIDECAR_ENTRY_SUFFIXES
    GL_GROUND_ARCHIVE_PREFIXES = TableArchiveClassifier.GL_GROUND_ARCHIVE_PREFIXES
    GL_C_SB_RAW_SCRIPT_KEYWORDS = TableArchiveClassifier.GL_C_SB_RAW_SCRIPT_KEYWORDS
    GL_RAW_SCRIPT_TEST_PREFIXES = TableArchiveClassifier.GL_RAW_SCRIPT_TEST_PREFIXES
    GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES = (
        TableArchiveClassifier.GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES
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
        self.payload_router = TablePayloadRouter()
        self.progress = TableExtractionProgress(self.logger)
        self.codec_adapter = TablePayloadCodecAdapter(
            self.flatbuffer_data_dir,
            self.logger,
            memorypack_data_dir=self.memorypack_data_dir,
            memorypack_formatter_path=self.memorypack_formatter_path,
            payload_router=self.payload_router,
        )
        self.database_reader = TableDatabaseReader(
            self.codec_adapter,
            self.payload_router,
            self.logger,
            self.progress,
        )
        self.database_writer = TableDatabaseJsonWriter()
        self.archive_classifier = TableArchiveClassifier()
        self.raw_archive_exporter = RawArchiveExporter(self)
        self.archive_router = TableArchiveRouter(
            self,
            classifier=self.archive_classifier,
            raw_exporter=self.raw_archive_exporter,
        )
        self._sync_codec_attributes()

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

    def _sync_codec_attributes(self) -> None:
        self.lower_schema_registry = self.codec_adapter.lower_schema_registry
        self.flatbuffer_exporter = self.codec_adapter.flatbuffer_exporter
        self.memorypack_schema_registry = self.codec_adapter.memorypack_schema_registry
        self.memorypack_formatter_registry = (
            self.codec_adapter.memorypack_formatter_registry
        )
        self._memorypack_warning_keys = self.codec_adapter._memorypack_warning_keys

    @staticmethod
    def _ensure_not_cancelled(should_stop: Callable[[], bool] | None) -> None:
        TableExtractionProgress.ensure_not_cancelled(should_stop)

    def _resolve_flatbuffer_schema(self, file_name: str) -> Any:
        return self.codec_adapter.resolve_flatbuffer_schema(file_name)

    def _dump_encrypted_table(
        self,
        flatbuffer_schema: Any,
        data: bytes,
    ) -> tuple[dict[str, Any] | list[Any], str]:
        return self.codec_adapter.dump_encrypted_table(flatbuffer_schema, data)

    def _dump_flatbuffer_payload(
        self,
        flatbuffer_schema: Any,
        data: bytes,
    ) -> tuple[dict[str, Any] | list[Any], str]:
        return self.codec_adapter.dump_flatbuffer_payload(flatbuffer_schema, data)

    def _process_db_file(
        self,
        file_path: str,
        table_name: str = "",
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[DBTable]:
        return self.database_reader.process_db_file(
            file_path,
            table_name,
            should_stop=should_stop,
            progress_callback=progress_callback,
        )

    def _process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact:
        return self.codec_adapter.process_zip_file(
            archive_name,
            file_name,
            file_data,
            detect_type=detect_type,
        )

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
        self.progress.warn_skipped_entry(archive_name, entry_name, warnings, error)

    @staticmethod
    def _notify_progress(
        progress_callback: ProgressCallback | None,
        current: int,
        total: int,
        unit: str,
    ) -> None:
        TableExtractionProgress.notify_progress(
            progress_callback,
            current,
            total,
            unit,
        )

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
            if TableExtractionProgress.is_cancelled(exc):
                raise
            self.logger.error(f"Failed to process {file_path}: {exc}")
            return False
        except (FileNotFoundError, OSError, ValueError, sqlite3.Error) as exc:
            self.logger.error(f"Failed to process {file_path}: {exc}")
            return False

        if not db_tables:
            self.logger.warn(f"No readable tables were found in {file_path}.")
            return False

        self.database_writer.write_tables(self.extract_folder, file_path, db_tables)
        return True

    def extract_zip_file(
        self,
        file_name: str,
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.archive_router.extract_zip_file(
            file_name,
            should_stop=should_stop,
            progress_callback=progress_callback,
        )

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
