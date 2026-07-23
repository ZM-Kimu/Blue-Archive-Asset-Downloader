from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable, Mapping
from os import path
from pathlib import Path

from ba_downloader.domain.models.database import DBTable
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.archives import TableArchiveRouter
from ba_downloader.infrastructure.extraction.table.codecs import (
    TablePayloadCodecAdapter,
)
from ba_downloader.infrastructure.extraction.table.database import (
    DatabasePathResolver,
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
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
    build_default_table_extraction_profile,
)
from ba_downloader.infrastructure.extraction.table.progress import (
    TableExtractionProgress,
)
from ba_downloader.infrastructure.extraction.table.raw_archives import (
    RawArchiveExporter,
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
    def __init__(
        self,
        table_file_folder: str,
        extract_folder: str,
        flatbuffer_data_dir: str,
        logger: LoggerPort | None = None,
        memorypack_data_dir: str | None = None,
        memorypack_formatter_path: str | None = None,
        context: RuntimeContext | None = None,
        database_path_resolver: DatabasePathResolver | None = None,
        table_profile: TableExtractionProfile | None = None,
    ) -> None:
        _ = context
        active_profile = table_profile or build_default_table_extraction_profile()
        self.table_file_folder = table_file_folder
        self.extract_folder = extract_folder
        self.flatbuffer_data_dir = flatbuffer_data_dir
        self.memorypack_data_dir = memorypack_data_dir or str(
            Path(flatbuffer_data_dir).parent / "MemoryPackData"
        )
        self.memorypack_formatter_path = memorypack_formatter_path or str(
            Path(flatbuffer_data_dir).parent
            / "Dumps"
            / TablePayloadCodecAdapter.MEMORYPACK_FORMATTER_SIDECAR_NAME
        )
        self.logger = logger or ConsoleLogger()
        self.payload_router = active_profile.payload_router
        self.top_level_memorypack_payloads = {
            Path(file_name).name.lower(): root_type
            for file_name, root_type in active_profile.top_level_memorypack_payloads.items()
        }
        self.preserved_top_level_files = {
            Path(file_name).name.lower()
            for file_name in active_profile.preserved_top_level_files
        }
        self.progress = TableExtractionProgress(self.logger)
        self.codec_adapter = TablePayloadCodecAdapter(
            self.flatbuffer_data_dir,
            self.logger,
            memorypack_data_dir=self.memorypack_data_dir,
            memorypack_formatter_path=self.memorypack_formatter_path,
            payload_router=self.payload_router,
            preserved_archive_entries=active_profile.preserved_archive_entries,
        )
        self.database_reader = TableDatabaseReader(
            self.codec_adapter,
            self.payload_router,
            self.logger,
            self.progress,
            database_path_resolver=(
                database_path_resolver
                if database_path_resolver is not None
                else active_profile.database_path_resolver
            ),
        )
        self.database_writer = TableDatabaseJsonWriter()
        self.raw_archive_exporter = RawArchiveExporter(self)
        self.archive_router = TableArchiveRouter(
            self,
            registry=active_profile.archive_registry,
            raw_exporter=self.raw_archive_exporter,
        )

    @classmethod
    def from_context(
        cls,
        context: RuntimeContext,
        logger: LoggerPort | None = None,
        table_profile: TableExtractionProfile | None = None,
    ) -> TableExtractor:
        return cls(
            str(Path(context.raw_dir) / "Table"),
            str(Path(context.extract_dir) / "Table"),
            str(Path(context.extract_dir) / "FlatBufferData"),
            logger=logger,
            table_profile=table_profile,
        )

    @staticmethod
    def ensure_not_cancelled(should_stop: Callable[[], bool] | None) -> None:
        TableExtractionProgress.ensure_not_cancelled(should_stop)

    def process_db_file(
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

    def process_zip_file(
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

    def process_memorypack_payload(
        self,
        root_type: str,
        file_data: bytes,
        output_name: str,
        *,
        compact: bool = False,
    ) -> ProcessedTableArtifact:
        return self.codec_adapter.process_memorypack_payload(
            root_type,
            file_data,
            output_name,
            compact=compact,
        )

    @staticmethod
    def write_processed_file(
        extract_folder: Path,
        processed_file: ProcessedTableArtifact,
    ) -> None:
        output_path = extract_folder / processed_file.file_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(processed_file.data)

    def warn_skipped_entry(
        self,
        archive_name: str,
        entry_name: str,
        warnings: list[str],
        error: str,
    ) -> None:
        self.progress.warn_skipped_entry(archive_name, entry_name, warnings, error)

    @staticmethod
    def notify_progress(
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
            db_tables = self.process_db_file(
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
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        self.archive_router.extract_zip_file(
            file_name,
            should_stop=should_stop,
            progress_callback=progress_callback,
            metadata=metadata,
        )

    def extract_table(
        self,
        file_path: str,
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        file_name = path.basename(file_path)
        normalized_name = file_name.lower()
        if root_type := self.top_level_memorypack_payloads.get(normalized_name):
            source_path = Path(self.table_file_folder) / file_path
            try:
                processed_file = self.process_memorypack_payload(
                    root_type,
                    source_path.read_bytes(),
                    f"{Path(file_name).stem}.json",
                )
                self.write_processed_file(Path(self.extract_folder), processed_file)
            except (OSError, TableProcessingError) as exc:
                self.logger.error(f"Failed to process {file_path}: {exc}")
            return

        if normalized_name in self.preserved_top_level_files:
            source_path = Path(self.table_file_folder) / file_path
            output_path = Path(self.extract_folder) / file_name
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, output_path)
            except OSError as exc:
                self.logger.error(f"Failed to preserve {file_path}: {exc}")
            return

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
            metadata=metadata,
        )
