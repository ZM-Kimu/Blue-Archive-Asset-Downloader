from __future__ import annotations

import hashlib
from binascii import crc32
from collections.abc import Callable, Iterable
from mmap import ACCESS_READ, mmap
from os import PathLike
from pathlib import Path
from typing import Protocol

HASH_CHUNK_SIZE = 1024 * 1024
_TEXT_SOURCE_SUFFIXES = {".cs", ".csproj", ".json", ".props", ".py", ".targets"}


class _Digest(Protocol):
    def update(self, value: bytes) -> None: ...


def calculate_crc(path: str | PathLike[str]) -> int:
    with open(path, "rb") as file_handle:
        try:
            mapping = mmap(file_handle.fileno(), 0, access=ACCESS_READ)
        except (OSError, OverflowError, ValueError):
            file_handle.seek(0)
            checksum = 0
            for chunk in iter(lambda: file_handle.read(HASH_CHUNK_SIZE), b""):
                checksum = crc32(chunk, checksum)
            return checksum & 0xFFFFFFFF
        with mapping:
            return crc32(mapping) & 0xFFFFFFFF


def calculate_md5(path: str | PathLike[str]) -> str:
    with open(path, "rb") as file_handle:
        return hashlib.file_digest(file_handle, "md5").hexdigest()


def calculate_sha256(
    path: str | PathLike[str],
    *,
    on_chunk: Callable[[], None] | None = None,
) -> str:
    if on_chunk is None:
        with open(path, "rb") as file_handle:
            return hashlib.file_digest(file_handle, "sha256").hexdigest()

    digest = hashlib.sha256()
    with open(path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(HASH_CHUNK_SIZE), b""):
            on_chunk()
            digest.update(chunk)
    return digest.hexdigest()


def calculate_source_fingerprint(
    root: Path,
    sources: Iterable[Path],
    *,
    identities: Iterable[tuple[str, str]] = (),
) -> str:
    """Hash labeled source content deterministically across checkout line endings."""
    resolved_root = root.resolve(strict=True)
    normalized_sources: list[tuple[str, Path]] = []
    for source in sources:
        resolved_source = source.resolve(strict=True)
        try:
            relative = resolved_source.relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"Fingerprint source is outside its root: {source}"
            ) from exc
        normalized_sources.append((relative, resolved_source))

    digest = hashlib.sha256()
    for label, value in sorted(identities):
        _update_fingerprint_part(digest, f"identity:{label}".encode())
        _update_fingerprint_part(digest, value.encode("utf8"))
    for relative, source in sorted(normalized_sources):
        content = source.read_bytes()
        if source.suffix.casefold() in _TEXT_SOURCE_SUFFIXES:
            content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        _update_fingerprint_part(digest, relative.encode("utf8"))
        _update_fingerprint_part(digest, content)
    return digest.hexdigest()


def _update_fingerprint_part(digest: _Digest, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)
