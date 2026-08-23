from __future__ import annotations

import hashlib
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
from ba_downloader.infrastructure.files.checksum import calculate_sha256

SHARPZIPLIB_VERSION = "1.4.2"
SHARPZIPLIB_COMMIT = "33f64eb0f28cdd2b084cb822fcc224c7c5aba553"
SHARPZIPLIB_ARCHIVE_SHA256 = (
    "dee76dcef0dc43c1f63661f2df3e79ee4d2b9f0005158d3997bb3b6eb3e40e2f"
)
SHARPZIPLIB_SOURCE_TREE_SHA256 = (
    "174df15c715c196108ad6763159e3253136995b6a16f6bdf5b560d20956a5b94"
)
SHARPZIPLIB_ARCHIVE_URL = (
    f"https://github.com/icsharpcode/SharpZipLib/archive/{SHARPZIPLIB_COMMIT}.zip"
)


class SharpZipLibSourcePort(Protocol):
    def resolve(self, context: ExecutionContext) -> Path: ...


class SharpZipLibSourceError(ExternalToolError):
    """Pinned SharpZipLib source could not be resolved or verified."""


class SharpZipLibSourceResolver:
    MAX_ARCHIVE_FILES = 5_000
    MAX_ARCHIVE_BYTES = 256 * 1024 * 1024

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        *,
        cancellation: CancellationPort | None = None,
        repository_root: Path | None = None,
        archive_url: str = SHARPZIPLIB_ARCHIVE_URL,
        archive_sha256: str = SHARPZIPLIB_ARCHIVE_SHA256,
        source_tree_sha256: str = SHARPZIPLIB_SOURCE_TREE_SHA256,
        commit: str = SHARPZIPLIB_COMMIT,
    ) -> None:
        self._http_client = http_client
        self._logger = logger
        self._cancellation = cancellation or NeverCancelled()
        self._repository_root = repository_root or Path(__file__).resolve().parents[5]
        self._archive_url = archive_url
        self._archive_sha256 = archive_sha256.lower()
        self._source_tree_sha256 = source_tree_sha256.lower()
        self._commit = commit

    def resolve(self, context: ExecutionContext) -> Path:
        self._cancellation.raise_if_cancelled()
        submodule = self._repository_root / "third_party" / "SharpZipLib"
        if self._is_verified_source(submodule):
            return submodule

        cache_root = self._cache_root(context)
        if self._is_verified_source(cache_root):
            return cache_root

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
            actual_hash = calculate_sha256(
                archive,
                on_chunk=self._cancellation.raise_if_cancelled,
            )
            if actual_hash != self._archive_sha256:
                raise SharpZipLibSourceError(
                    "SharpZipLib source archive checksum mismatch: "
                    f"expected {self._archive_sha256}, got {actual_hash}."
                )
            with ZipFile(archive) as source_archive:
                self._safe_extract(source_archive, staging)
            source_root = next(
                (
                    path
                    for path in staging.iterdir()
                    if path.is_dir() and self._is_verified_source(path)
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

    def _safe_extract(self, archive: ZipFile, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=False)
        root = destination.resolve(strict=True)
        infos = archive.infolist()
        if len(infos) > self.MAX_ARCHIVE_FILES:
            raise SharpZipLibSourceError(
                f"SharpZipLib source archive has too many files: {len(infos)}."
            )
        total_size = 0
        for info in infos:
            self._cancellation.raise_if_cancelled()
            total_size += max(info.file_size, 0)
            if total_size > self.MAX_ARCHIVE_BYTES:
                raise SharpZipLibSourceError(
                    "SharpZipLib source archive exceeds the extraction size limit."
                )
            target = (destination / info.filename).resolve(strict=False)
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise SharpZipLibSourceError(
                    "SharpZipLib source archive contains an unsafe path: "
                    f"{info.filename}"
                ) from exc
        archive.extractall(destination)

    def _is_verified_source(self, path: Path) -> bool:
        if not self._is_source_tree(path):
            return False
        return self.source_tree_hash(path) == self._source_tree_sha256

    @staticmethod
    def _is_source_tree(path: Path) -> bool:
        source = path / "src" / "ICSharpCode.SharpZipLib"
        return (
            (source / "ICSharpCode.SharpZipLib.csproj").is_file()
            and (source / "Zip" / "ZipFile.cs").is_file()
            and (source / "Checksum" / "Crc32.cs").is_file()
        )

    @staticmethod
    def source_tree_hash(path: Path) -> str:
        digest = hashlib.sha256()
        sources = sorted(
            (
                source
                for source in (path / "src" / "ICSharpCode.SharpZipLib").rglob("*.cs")
                if not {"bin", "obj"}.intersection(source.relative_to(path).parts)
            ),
            key=lambda item: item.relative_to(path).as_posix(),
        )
        for source in sources:
            relative = source.relative_to(path).as_posix()
            digest.update(relative.encode("utf8"))
            digest.update(b"\0")
            content = source.read_bytes().replace(b"\r\n", b"\n")
            digest.update(hashlib.sha256(content).hexdigest().encode("ascii"))
            digest.update(b"\n")
        return digest.hexdigest()

    def _cache_root(self, context: ExecutionContext) -> Path:
        return context.workspace.tools_cache / f"SharpZipLib-{self._commit[:12]}"
