from __future__ import annotations

from collections.abc import Callable, Mapping
from os import path
from pathlib import Path
from typing import Protocol

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.models import (
    ProcessedTableArtifact,
    ProgressCallback,
)

STAGE_SAVE_DATA_ROOT = "MX.Logic.Battles.StageSaveData.StageSaveData"
STAGE_SAVE_DATA_OUTPUT_NAME = "StageSaveData.json"


def resolve_inner_password_name(
    item_name: str,
    inner_password_names: Mapping[str, str] | None,
) -> str:
    item_basename = path.basename(item_name)
    if not inner_password_names:
        return item_basename
    return inner_password_names.get(item_basename.lower(), item_basename)


class TableArchiveServices(Protocol):
    table_file_folder: str
    extract_folder: str
    logger: LoggerPort

    def ensure_not_cancelled(
        self,
        should_stop: Callable[[], bool] | None,
    ) -> None: ...

    def notify_progress(
        self,
        progress_callback: ProgressCallback | None,
        current: int,
        total: int,
        unit: str,
    ) -> None: ...

    def warn_skipped_entry(
        self,
        archive_name: str,
        entry_name: str,
        warnings: list[str],
        error: str,
    ) -> None: ...

    def process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact: ...

    def process_memorypack_payload(
        self,
        root_type: str,
        file_data: bytes,
        output_name: str,
        *,
        compact: bool = False,
    ) -> ProcessedTableArtifact: ...

    def write_processed_file(
        self,
        extract_folder: Path,
        processed_file: ProcessedTableArtifact,
    ) -> None: ...


class TableArchiveWarningPolicy(Protocol):
    def warn_unsupported_entry(
        self,
        services: TableArchiveServices,
        archive_name: str,
        item_name: str,
        warnings: list[str],
        first_error: Exception,
        second_error: Exception,
    ) -> bool: ...

    def emit_warning_summary(
        self,
        services: TableArchiveServices,
        archive_name: str,
        warnings: list[str],
    ) -> None: ...


class DefaultTableArchiveWarningPolicy:
    def warn_unsupported_entry(
        self,
        services: TableArchiveServices,
        archive_name: str,
        item_name: str,
        warnings: list[str],
        first_error: Exception,
        second_error: Exception,
    ) -> bool:
        _ = (services, archive_name, item_name, warnings, first_error, second_error)
        return False

    def emit_warning_summary(
        self,
        services: TableArchiveServices,
        archive_name: str,
        warnings: list[str],
    ) -> None:
        _ = (services, archive_name, warnings)
