from __future__ import annotations

import zlib
from collections.abc import Callable
from os import path
from pathlib import Path
from zipfile import ZipFile

from ba_downloader.infrastructure.extraction.table.archive_support import (
    TableArchiveServices,
)
from ba_downloader.infrastructure.extraction.table.models import (
    ProcessedTableArtifact,
    ProgressCallback,
    TableProcessingError,
)
from ba_downloader.infrastructure.schema.crypto import zip_password


class GlLegacyArchiveExtractor:
    def __init__(self, services: TableArchiveServices) -> None:
        self.services = services

    def extract_ground(
        self,
        file_name: str,
        *,
        schema_name: str,
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
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self.services.warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    try:
                        processed_file = self.services.process_zip_file(
                            archive_name,
                            schema_name,
                            item_data,
                            detect_type=True,
                        )
                    except TableProcessingError as exc:
                        self.services.warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    self.services.ensure_not_cancelled(should_stop)
                    self.services.write_processed_file(extract_folder, processed_file)
                finally:
                    self.services.notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def extract_mgs_logic_ground(
        self,
        file_name: str,
        *,
        grid_schema_name: str,
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
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self.services.warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    try:
                        processed_file = self.services.process_zip_file(
                            archive_name,
                            grid_schema_name,
                            item_data,
                            detect_type=True,
                        )
                    except TableProcessingError:
                        processed_file = ProcessedTableArtifact(
                            data=item_data,
                            file_name=path.basename(item_name),
                        )

                    self.services.ensure_not_cancelled(should_stop)
                    self.services.write_processed_file(extract_folder, processed_file)
                finally:
                    self.services.notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )
