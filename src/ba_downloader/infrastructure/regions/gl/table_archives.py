from __future__ import annotations

import zlib
from collections.abc import Callable, Mapping
from os import path
from pathlib import Path
from zipfile import ZipFile

from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    ROUTE_RAW,
    ROUTE_STANDARD,
    TableArchiveRoute,
    TableArchiveRouteKey,
    classify_table_archive,
)
from ba_downloader.infrastructure.extraction.table.archive_support import (
    TableArchiveServices,
)
from ba_downloader.infrastructure.extraction.table.archives import ArchiveHandler
from ba_downloader.infrastructure.extraction.table.crypto import zip_password
from ba_downloader.infrastructure.extraction.table.models import (
    ProcessedTableArtifact,
    ProgressCallback,
    TableProcessingError,
)
from ba_downloader.infrastructure.extraction.table.raw_archives import (
    RawArchiveExporter,
)
from ba_downloader.infrastructure.regions.cn_gl_table_archives import (
    GROUND_GRID_SCHEMA_NAME,
    is_c_sb_raw_script_archive,
    is_eliminate_raid_archive,
    is_enemy_boss_script_archive,
    is_ground_archive,
    is_mgs_logic_ground_archive,
    is_numeric_stage_archive,
    is_raw_script_test_archive,
    resolve_ground_schema_name,
)

GROUND_FLATBUFFER_ARCHIVE_ROUTE = "ground_flatbuffer_archive"
MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE = "mgs_logic_ground_mixed_archive"


def classify_gl_table_archive(file_name: str) -> TableArchiveRoute:
    archive_name = path.basename(file_name)

    standard_route = classify_table_archive(archive_name)
    if standard_route.route_key != ROUTE_STANDARD:
        return standard_route
    if is_mgs_logic_ground_archive(archive_name):
        return TableArchiveRoute(MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE)

    lower_name = archive_name.lower()
    if is_c_sb_raw_script_archive(lower_name):
        return TableArchiveRoute(ROUTE_RAW)
    if is_ground_archive(lower_name):
        return TableArchiveRoute(
            GROUND_FLATBUFFER_ARCHIVE_ROUTE,
            schema_name=resolve_ground_schema_name(lower_name),
        )
    if (
        is_eliminate_raid_archive(lower_name)
        or is_enemy_boss_script_archive(lower_name)
        or is_raw_script_test_archive(lower_name)
        or is_numeric_stage_archive(lower_name)
    ):
        return TableArchiveRoute(ROUTE_RAW)

    return TableArchiveRoute(ROUTE_STANDARD)


class GlGroundArchiveExtractor:
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


def build_gl_table_archive_handlers(
    services: TableArchiveServices,
    raw_exporter: RawArchiveExporter,
) -> Mapping[TableArchiveRouteKey, ArchiveHandler]:
    extractor = GlGroundArchiveExtractor(services)

    def decode_ground_archive(
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

    def decode_mgs_logic_ground_archive(
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

    _ = raw_exporter

    return {
        GROUND_FLATBUFFER_ARCHIVE_ROUTE: decode_ground_archive,
        MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE: decode_mgs_logic_ground_archive,
    }
