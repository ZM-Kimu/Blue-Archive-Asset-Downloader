from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from ba_downloader.domain.models.database import DatabaseSourceIdentity, DBTable
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.schema import PreparedSchemaSnapshot
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.extractor import TableExtractor
from ba_downloader.infrastructure.extraction.table.models import ProcessedTableArtifact
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
    build_default_table_profile_for_context,
)

TableProfileFactory = Callable[
    [ExecutionContext, DatabaseSourceIdentity | None], TableExtractionProfile
]


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
        context: ExecutionContext,
        logger: LoggerPort | None = None,
        table_profile_factory: TableProfileFactory | None = None,
        *,
        schema_snapshot: PreparedSchemaSnapshot | None = None,
        database_source_identity: DatabaseSourceIdentity | None = None,
    ) -> TableExtractorCharacterTableSource:
        active_table_profile_factory = (
            table_profile_factory or build_default_table_profile_for_context
        )
        return cls(
            TableExtractor(
                str(context.workspace.raw_tables),
                str(Path(context.workspace.temp_state) / "Table"),
                str(
                    schema_snapshot.flatbuffer_path
                    if schema_snapshot is not None
                    else context.workspace.flatbuffer_schemas
                ),
                logger=logger,
                table_profile=active_table_profile_factory(
                    context, database_source_identity
                ),
                schema_cache_identity=(
                    schema_snapshot.fingerprint if schema_snapshot is not None else None
                ),
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

    def process_character_index_tables(
        self,
        file_path: str,
        table_names: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        return self._extractor.process_character_index_tables(file_path, table_names)
