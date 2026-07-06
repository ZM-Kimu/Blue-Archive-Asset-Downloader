from __future__ import annotations

from collections.abc import Callable
from os import path
from pathlib import Path
from zipfile import ZipFile

from ba_downloader.infrastructure.extraction.table.archive_support import (
    DefaultTableArchiveWarningPolicy,
    TableArchiveServices,
    TableArchiveWarningPolicy,
)
from ba_downloader.infrastructure.extraction.table.models import (
    ProcessedTableArtifact,
    ProgressCallback,
    TableProcessingError,
)
from ba_downloader.infrastructure.schema.crypto import zip_password


class StandardZipArchiveExtractor:
    def __init__(
        self,
        services: TableArchiveServices,
        *,
        warning_policy: TableArchiveWarningPolicy | None = None,
    ) -> None:
        self.services = services
        self.warning_policy = warning_policy or DefaultTableArchiveWarningPolicy()

    def extract(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        extract_folder = Path(self.services.extract_folder) / archive_name.removesuffix(
            ".zip"
        )
        with ZipFile(
            path.join(self.services.table_file_folder, file_name), "r"
        ) as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
                    self.services.ensure_not_cancelled(should_stop)
                    self.extract_entry(
                        archive_name=archive_name,
                        item_name=item_name,
                        archive=archive,
                        extract_folder=extract_folder,
                        warnings=warnings,
                        should_stop=should_stop,
                    )
                finally:
                    self.services.notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def extract_entry(
        self,
        *,
        archive_name: str,
        item_name: str,
        archive: ZipFile,
        extract_folder: Path,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.services.ensure_not_cancelled(should_stop)
        item_data = archive.read(item_name)

        try:
            processed_file = self.services.process_zip_file(
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
                processed_file = self.services.process_zip_file(
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
                self.warn_unsupported_entry(
                    archive_name,
                    item_name,
                    warnings,
                    first_error,
                    second_error,
                )
                return

        self.services.ensure_not_cancelled(should_stop)
        self.services.write_processed_file(extract_folder, processed_file)

    def warn_unsupported_entry(
        self,
        archive_name: str,
        item_name: str,
        warnings: list[str],
        first_error: TableProcessingError,
        second_error: TableProcessingError,
    ) -> None:
        if self.warning_policy.warn_unsupported_entry(
            self.services,
            archive_name,
            item_name,
            warnings,
            first_error,
            second_error,
        ):
            return

        self.services.warn_skipped_entry(
            archive_name,
            item_name,
            warnings,
            f"schema/payload unsupported; fallback failed "
            f"({first_error}; {second_error}).",
        )
