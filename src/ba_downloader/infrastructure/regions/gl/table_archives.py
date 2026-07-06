from __future__ import annotations

import zlib
from collections.abc import Callable, Mapping
from os import path
from pathlib import Path
from zipfile import ZipFile

from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    TableArchiveRoute,
    TableArchiveRouteKey,
)
from ba_downloader.infrastructure.extraction.table.archive_support import (
    TableArchiveServices,
)
from ba_downloader.infrastructure.extraction.table.archives import (
    GROUND_GRID_SCHEMA_NAME,
    ArchiveHandler,
)
from ba_downloader.infrastructure.extraction.table.crypto import zip_password
from ba_downloader.infrastructure.extraction.table.models import (
    ProcessedTableArtifact,
    ProgressCallback,
    TableProcessingError,
)
from ba_downloader.infrastructure.extraction.table.raw_archives import (
    RawArchiveExporter,
)
from ba_downloader.infrastructure.regions.legacy_table_archives import (
    LEGACY_GL_GROUND_ROUTE,
    LEGACY_GL_NUMERIC_STAGE_ROUTE,
    LEGACY_MGS_LOGIC_GROUND_ROUTE,
)


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


def build_gl_legacy_archive_handlers(
    services: TableArchiveServices,
    raw_exporter: RawArchiveExporter,
) -> Mapping[TableArchiveRouteKey, ArchiveHandler]:
    extractor = GlLegacyArchiveExtractor(services)

    def extract_gl_ground(
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = inner_password_names
        extractor.extract_ground(
            file_name,
            schema_name=route.schema_name,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
        )

    def extract_mgs_logic_ground(
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = (route, inner_password_names)
        extractor.extract_mgs_logic_ground(
            file_name,
            grid_schema_name=GROUND_GRID_SCHEMA_NAME,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
        )

    def extract_legacy_raw(
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = inner_password_names
        raw_exporter.extract(
            file_name,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
            info_message=route.info_message,
        )

    return {
        LEGACY_GL_GROUND_ROUTE: extract_gl_ground,
        LEGACY_GL_NUMERIC_STAGE_ROUTE: extract_legacy_raw,
        LEGACY_MGS_LOGIC_GROUND_ROUTE: extract_mgs_logic_ground,
    }
