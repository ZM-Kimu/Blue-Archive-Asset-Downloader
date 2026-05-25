from __future__ import annotations

import zlib
from collections.abc import Callable
from io import BytesIO
from os import path
from pathlib import Path
from typing import Protocol
from zipfile import BadZipFile, ZipFile

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.table_archive_classifier import (
    TableArchiveClassifier,
    TableArchiveKind,
)
from ba_downloader.infrastructure.extractors.table_models import (
    CANCELLED_EXTRACTION_MESSAGE,
    ProcessedTableArtifact,
    ProgressCallback,
    TableProcessingError,
)
from ba_downloader.shared.crypto.encryption import zip_password


class TableArchiveServices(Protocol):
    table_file_folder: str
    extract_folder: str
    logger: LoggerPort

    def _ensure_not_cancelled(
        self,
        should_stop: Callable[[], bool] | None,
    ) -> None: ...

    def _notify_progress(
        self,
        progress_callback: ProgressCallback | None,
        current: int,
        total: int,
        unit: str,
    ) -> None: ...

    def _warn_skipped_entry(
        self,
        archive_name: str,
        entry_name: str,
        warnings: list[str],
        error: str,
    ) -> None: ...

    def _process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact: ...

    def _write_processed_file(
        self,
        extract_folder: Path,
        processed_file: ProcessedTableArtifact,
    ) -> None: ...


class RawArchiveExporter:
    def __init__(self, services: TableArchiveServices) -> None:
        self.services = services

    def extract(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
        info_message: str | None = None,
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
                    self.services._ensure_not_cancelled(should_stop)
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self.services._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    self.services._write_processed_file(
                        extract_folder,
                        ProcessedTableArtifact(
                            data=item_data,
                            file_name=path.basename(item_name),
                        ),
                    )
                finally:
                    self.services._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

        if info_message:
            self.services.logger.info(info_message)

    def extract_ground_stage_patch(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        outer_extract_folder = Path(self.services.extract_folder) / (
            archive_name.removesuffix(".zip")
        )

        with ZipFile(
            path.join(self.services.table_file_folder, file_name), "r"
        ) as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
                    self.services._ensure_not_cancelled(should_stop)
                    item_data = archive.read(item_name)
                    try:
                        self.extract_ground_stage_inner_archive(
                            archive_name=archive_name,
                            item_name=item_name,
                            item_data=item_data,
                            extract_folder=outer_extract_folder,
                            warnings=warnings,
                            should_stop=should_stop,
                        )
                    except BadZipFile as exc:
                        self.services._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                finally:
                    self.services._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

        self.services.logger.info(
            f"Extracted raw GroundStage payloads from {archive_name}; semantic parser is not implemented yet."
        )

    def extract_ground_stage_inner_archive(
        self,
        *,
        archive_name: str,
        item_name: str,
        item_data: bytes,
        extract_folder: Path,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        with ZipFile(BytesIO(item_data), "r") as inner_archive:
            inner_archive.setpassword(zip_password(path.basename(item_name)))
            for inner_item_name in inner_archive.namelist():
                self.services._ensure_not_cancelled(should_stop)
                try:
                    inner_item_data = inner_archive.read(inner_item_name)
                except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                    self.services._warn_skipped_entry(
                        archive_name,
                        f"{item_name}/{inner_item_name}",
                        warnings,
                        str(exc),
                    )
                    continue

                self.services._ensure_not_cancelled(should_stop)
                self.services._write_processed_file(
                    extract_folder / Path(item_name).stem,
                    ProcessedTableArtifact(inner_item_data, inner_item_name),
                )


class TableArchiveRouter:
    def __init__(
        self,
        services: TableArchiveServices,
        *,
        classifier: TableArchiveClassifier | None = None,
        raw_exporter: RawArchiveExporter | None = None,
    ) -> None:
        self.services = services
        self.classifier = classifier or TableArchiveClassifier()
        self.raw_exporter = raw_exporter or RawArchiveExporter(services)

    def extract_zip_file(
        self,
        file_name: str,
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        warnings: list[str] = []
        route = self.classifier.classify(archive_name)

        if route.kind is TableArchiveKind.RHYTHM_BEATMAP:
            self.raw_exporter.extract(
                file_name,
                warnings=warnings,
                should_stop=should_stop,
                progress_callback=progress_callback,
                info_message=route.info_message,
            )
            return

        try:
            if route.kind is TableArchiveKind.GROUND_GRID_PATCH:
                self.extract_ground_grid_patch_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif route.kind is TableArchiveKind.GROUND_STAGE_PATCH:
                self.raw_exporter.extract_ground_stage_patch(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif route.kind is TableArchiveKind.RAW:
                self.raw_exporter.extract(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif route.kind is TableArchiveKind.GL_GROUND:
                self.extract_gl_ground_archive(
                    file_name,
                    route.schema_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif route.kind is TableArchiveKind.GL_NUMERIC_STAGE:
                self.raw_exporter.extract(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            elif route.kind is TableArchiveKind.MGS_LOGIC_GROUND:
                self.extract_mgs_logic_ground_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
            else:
                self.extract_standard_zip_archive(
                    file_name,
                    warnings=warnings,
                    should_stop=should_stop,
                    progress_callback=progress_callback,
                )
        except RuntimeError as exc:
            if str(exc) == CANCELLED_EXTRACTION_MESSAGE:
                raise
            self.services.logger.error(f"Failed to process {archive_name}: {exc}")
            return
        except (BadZipFile, FileNotFoundError, OSError, ValueError) as exc:
            self.services.logger.error(f"Failed to process {archive_name}: {exc}")
            return

        if warnings:
            self.services.logger.warn(
                f"Skipped {len(warnings)} entries while extracting {archive_name}."
            )

    def extract_standard_zip_archive(
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
                    self.services._ensure_not_cancelled(should_stop)
                    self.extract_zip_entry(
                        archive_name=archive_name,
                        item_name=item_name,
                        archive=archive,
                        extract_folder=extract_folder,
                        warnings=warnings,
                        should_stop=should_stop,
                    )
                finally:
                    self.services._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def extract_ground_grid_patch_archive(
        self,
        file_name: str,
        *,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        outer_extract_folder = Path(self.services.extract_folder) / (
            archive_name.removesuffix(".zip")
        )

        with ZipFile(
            path.join(self.services.table_file_folder, file_name), "r"
        ) as archive:
            archive.setpassword(zip_password(archive_name))
            item_names = archive.namelist()
            for index, item_name in enumerate(item_names, start=1):
                try:
                    self.services._ensure_not_cancelled(should_stop)
                    item_data = archive.read(item_name)
                    try:
                        self.extract_ground_grid_inner_archive(
                            archive_name=archive_name,
                            item_name=item_name,
                            item_data=item_data,
                            extract_folder=outer_extract_folder,
                            warnings=warnings,
                            should_stop=should_stop,
                        )
                    except BadZipFile as exc:
                        self.services._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                finally:
                    self.services._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def extract_ground_grid_inner_archive(
        self,
        *,
        archive_name: str,
        item_name: str,
        item_data: bytes,
        extract_folder: Path,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        with ZipFile(BytesIO(item_data), "r") as inner_archive:
            inner_archive.setpassword(zip_password(path.basename(item_name)))
            for inner_item_name in inner_archive.namelist():
                self.services._ensure_not_cancelled(should_stop)
                try:
                    inner_item_data = inner_archive.read(inner_item_name)
                except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                    self.services._warn_skipped_entry(
                        archive_name,
                        f"{item_name}/{inner_item_name}",
                        warnings,
                        str(exc),
                    )
                    continue
                try:
                    processed_file = self.services._process_zip_file(
                        archive_name,
                        TableArchiveClassifier.GROUND_GRID_SCHEMA_NAME,
                        inner_item_data,
                        detect_type=True,
                    )
                except TableProcessingError as exc:
                    self.services._warn_skipped_entry(
                        archive_name,
                        f"{item_name}/{inner_item_name}",
                        warnings,
                        str(exc),
                    )
                    continue

                self.services._ensure_not_cancelled(should_stop)
                self.services._write_processed_file(
                    extract_folder / Path(item_name).stem,
                    processed_file,
                )

    def extract_gl_ground_archive(
        self,
        file_name: str,
        schema_name: str,
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
                    self.services._ensure_not_cancelled(should_stop)
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self.services._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    try:
                        processed_file = self.services._process_zip_file(
                            archive_name,
                            schema_name,
                            item_data,
                            detect_type=True,
                        )
                    except TableProcessingError as exc:
                        self.services._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    self.services._ensure_not_cancelled(should_stop)
                    self.services._write_processed_file(extract_folder, processed_file)
                finally:
                    self.services._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def extract_mgs_logic_ground_archive(
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
                    self.services._ensure_not_cancelled(should_stop)
                    try:
                        item_data = archive.read(item_name)
                    except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                        self.services._warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                        continue

                    try:
                        processed_file = self.services._process_zip_file(
                            archive_name,
                            TableArchiveClassifier.GROUND_GRID_SCHEMA_NAME,
                            item_data,
                            detect_type=True,
                        )
                    except TableProcessingError:
                        processed_file = ProcessedTableArtifact(
                            data=item_data,
                            file_name=path.basename(item_name),
                        )

                    self.services._ensure_not_cancelled(should_stop)
                    self.services._write_processed_file(extract_folder, processed_file)
                finally:
                    self.services._notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def extract_zip_entry(
        self,
        *,
        archive_name: str,
        item_name: str,
        archive: ZipFile,
        extract_folder: Path,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.services._ensure_not_cancelled(should_stop)
        item_data = archive.read(item_name)

        try:
            processed_file = self.services._process_zip_file(
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
                processed_file = self.services._process_zip_file(
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
                self.services._warn_skipped_entry(
                    archive_name,
                    item_name,
                    warnings,
                    f"{first_error}; fallback failed ({second_error}).",
                )
                return

        self.services._ensure_not_cancelled(should_stop)
        self.services._write_processed_file(extract_folder, processed_file)
