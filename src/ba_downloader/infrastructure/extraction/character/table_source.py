from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ba_downloader.domain.models.database import DBTable
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.extractor import TableExtractor
from ba_downloader.infrastructure.extraction.table.models import ProcessedTableArtifact


class CharacterTableSource(Protocol):
    table_file_folder: str
    extract_folder: str

    def process_db_file(
        self,
        file_path: str,
        table_name: str = "",
    ) -> list[DBTable]: ...

    def process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact: ...


class TableExtractorCharacterTableSource:
    def __init__(self, extractor: TableExtractor) -> None:
        self._extractor = extractor

    @classmethod
    def from_context(
        cls,
        context: RuntimeContext,
        logger: LoggerPort | None = None,
    ) -> TableExtractorCharacterTableSource:
        return cls(
            TableExtractor(
                str(Path(context.raw_dir) / "Table"),
                str(Path(context.temp_dir) / "Table"),
                str(Path(context.extract_dir) / "FlatBufferData"),
                logger=logger,
                context=context,
            )
        )

    @property
    def table_file_folder(self) -> str:
        return self._extractor.table_file_folder

    @property
    def extract_folder(self) -> str:
        return self._extractor.extract_folder

    def process_db_file(
        self,
        file_path: str,
        table_name: str = "",
    ) -> list[DBTable]:
        return self._extractor.process_db_file(file_path, table_name)

    def process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact:
        return self._extractor.process_zip_file(
            archive_name,
            file_name,
            file_data,
            detect_type=detect_type,
        )
