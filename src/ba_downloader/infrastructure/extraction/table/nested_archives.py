from __future__ import annotations

import zlib
from collections.abc import Callable, Mapping
from io import BytesIO
from os import path
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from ba_downloader.infrastructure.extraction.table.archive_support import (
    TableArchiveServices,
    resolve_inner_password_name,
)
from ba_downloader.infrastructure.extraction.table.models import (
    ProcessedTableArtifact,
    ProgressCallback,
    TableProcessingError,
)
from ba_downloader.infrastructure.schema.crypto import zip_password


class NestedZipPatchArchiveExtractor:
    def __init__(self, services: TableArchiveServices) -> None:
        self.services = services

    def extract(
        self,
        file_name: str,
        *,
        schema_name: str,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
        inner_password_names: Mapping[str, str] | None = None,
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
                    self._notify_entry_start(
                        progress_callback,
                        index,
                        len(item_names),
                        item_name,
                    )
                    item_data = archive.read(item_name)
                    try:
                        self._extract_inner_archive(
                            archive_name=archive_name,
                            item_name=item_name,
                            item_data=item_data,
                            schema_name=schema_name,
                            extract_folder=extract_folder,
                            warnings=warnings,
                            should_stop=should_stop,
                            password_name=resolve_inner_password_name(
                                item_name,
                                inner_password_names,
                            ),
                        )
                    except BadZipFile as exc:
                        self.services.warn_skipped_entry(
                            archive_name,
                            item_name,
                            warnings,
                            str(exc),
                        )
                finally:
                    self.services.notify_progress(
                        progress_callback,
                        index,
                        len(item_names),
                        "entries",
                    )

    def _extract_inner_archive(
        self,
        *,
        archive_name: str,
        item_name: str,
        item_data: bytes,
        schema_name: str,
        extract_folder: Path,
        warnings: list[str],
        should_stop: Callable[[], bool] | None = None,
        password_name: str | None = None,
    ) -> None:
        with ZipFile(BytesIO(item_data), "r") as inner_archive:
            inner_archive.setpassword(
                zip_password(password_name or path.basename(item_name))
            )
            for inner_item_name in inner_archive.namelist():
                self.services.ensure_not_cancelled(should_stop)
                try:
                    inner_item_data = inner_archive.read(inner_item_name)
                except (RuntimeError, OSError, ValueError, zlib.error) as exc:
                    if "Bad password" in str(exc):
                        preserved_path = self.preserve_encrypted_inner_archive(
                            item_name=item_name,
                            item_data=item_data,
                            extract_folder=extract_folder,
                        )
                        warnings.append(
                            f"{item_name} saved to {preserved_path.as_posix()}: {exc}"
                        )
                        continue
                    self.services.warn_skipped_entry(
                        archive_name,
                        f"{item_name}/{inner_item_name}",
                        warnings,
                        str(exc),
                    )
                    continue

                try:
                    processed_file = self.services.process_zip_file(
                        archive_name,
                        schema_name,
                        inner_item_data,
                        detect_type=True,
                    )
                except TableProcessingError as exc:
                    self.services.warn_skipped_entry(
                        archive_name,
                        f"{item_name}/{inner_item_name}",
                        warnings,
                        str(exc),
                    )
                    continue

                self.services.ensure_not_cancelled(should_stop)
                self.services.write_processed_file(
                    extract_folder / Path(item_name).stem,
                    processed_file,
                )

    def preserve_encrypted_inner_archive(
        self,
        *,
        item_name: str,
        item_data: bytes,
        extract_folder: Path,
    ) -> Path:
        encrypted_folder = extract_folder / "_encrypted"
        self.services.write_processed_file(
            encrypted_folder,
            ProcessedTableArtifact(
                item_data,
                path.basename(item_name),
            ),
        )
        return encrypted_folder / path.basename(item_name)

    @staticmethod
    def _notify_entry_start(
        progress_callback: ProgressCallback | None,
        current: int,
        total: int,
        entry_name: str,
    ) -> None:
        if progress_callback is not None:
            progress_callback(f"{current}/{total} entries: {entry_name}")
