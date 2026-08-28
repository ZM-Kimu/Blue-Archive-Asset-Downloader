from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from ba_downloader.domain.exceptions import ExternalToolError, OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.files.atomic import publish_staged_directory
from ba_downloader.infrastructure.files.lock import wait_for_interprocess_lock

SHARPZIPLIB_VERSION = "1.4.2"
SHARPZIPLIB_COMMIT = "33f64eb0f28cdd2b084cb822fcc224c7c5aba553"
SHARPZIPLIB_ARCHIVE_URL = (
    f"https://github.com/icsharpcode/SharpZipLib/archive/{SHARPZIPLIB_COMMIT}.zip"
)


class SharpZipLibSourcePort(Protocol):
    def resolve(self, context: ExecutionContext) -> Path: ...


class SharpZipLibSourceError(ExternalToolError):
    """Pinned SharpZipLib source could not be resolved or verified."""


class SharpZipLibSourceResolver:
    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        *,
        cancellation: CancellationPort | None = None,
        repository_root: Path | None = None,
        archive_url: str = SHARPZIPLIB_ARCHIVE_URL,
        commit: str = SHARPZIPLIB_COMMIT,
    ) -> None:
        self._http_client = http_client
        self._logger = logger
        self._cancellation = cancellation or NeverCancelled()
        self._repository_root = repository_root or Path(__file__).resolve().parents[5]
        self._archive_url = archive_url
        self._commit = commit

    def resolve(self, context: ExecutionContext) -> Path:
        self._cancellation.raise_if_cancelled()
        submodule = self._repository_root / "third_party" / "SharpZipLib"
        if self._is_source_tree(submodule):
            return submodule

        cache_root = self._cache_root(context)
        if self._is_source_tree(cache_root):
            return cache_root

        lock_path = (
            context.workspace.locks / f"sharpziplib-source-{self._commit[:12]}.lock"
        )
        try:
            with wait_for_interprocess_lock(
                lock_path,
                operation="SharpZipLib source preparation",
                cancellation_check=self._cancellation.raise_if_cancelled,
            ):
                if self._is_source_tree(submodule):
                    return submodule
                if self._is_source_tree(cache_root):
                    return cache_root
                return self._resolve_fallback(context, cache_root)
        except SharpZipLibSourceError:
            raise
        except OSError as exc:
            raise SharpZipLibSourceError(
                f"SharpZipLib source lock is unavailable: {exc}"
            ) from exc

    def _resolve_fallback(
        self,
        context: ExecutionContext,
        cache_root: Path,
    ) -> Path:

        self._logger.warn(
            "SharpZipLib source is missing. Downloading fallback source package..."
        )
        last_error: Exception | None = None
        for _attempt in range(max(1, context.max_retries + 1)):
            try:
                self._download_to_cache(cache_root)
                return cache_root
            except OperationCancelledError:
                raise
            except (BadZipFile, OSError, SharpZipLibSourceError, ValueError) as exc:
                last_error = exc

        raise SharpZipLibSourceError(
            "Unable to resolve SharpZipLib source. Initialize the submodule or "
            f"retry the verified fallback download. Details: {last_error}"
        ) from last_error

    def _download_to_cache(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        archive = destination.parent / f"SharpZipLib-{self._commit}.zip"
        staging = destination.with_name(f".{destination.name}.staging-{uuid4().hex}")
        archive.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        try:
            self._http_client.download_to_file(self._archive_url, str(archive))
            self._cancellation.raise_if_cancelled()
            with ZipFile(archive) as source_archive:
                source_archive.extractall(staging)
            source_root = next(
                (
                    path
                    for path in staging.iterdir()
                    if path.is_dir() and self._is_source_tree(path)
                ),
                None,
            )
            if source_root is None:
                raise SharpZipLibSourceError(
                    "Downloaded SharpZipLib archive has an invalid source tree."
                )
            publish_staged_directory(source_root, destination)
        finally:
            archive.unlink(missing_ok=True)
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _is_source_tree(path: Path) -> bool:
        source = path / "src" / "ICSharpCode.SharpZipLib"
        return (
            (source / "ICSharpCode.SharpZipLib.csproj").is_file()
            and (source / "Zip" / "ZipFile.cs").is_file()
            and (source / "Checksum" / "Crc32.cs").is_file()
        )

    def _cache_root(self, context: ExecutionContext) -> Path:
        return context.workspace.tools_cache / f"SharpZipLib-{self._commit[:12]}"
