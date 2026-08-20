from __future__ import annotations

import hashlib
from binascii import crc32
from collections.abc import Callable
from os import PathLike

HASH_CHUNK_SIZE = 1024 * 1024


def calculate_crc(path: str | PathLike[str]) -> int:
    checksum = 0
    with open(path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(HASH_CHUNK_SIZE), b""):
            checksum = crc32(chunk, checksum)
    return checksum & 0xFFFFFFFF


def calculate_md5(path: str | PathLike[str]) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def calculate_sha256(
    path: str | PathLike[str],
    *,
    on_chunk: Callable[[], None] | None = None,
) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(HASH_CHUNK_SIZE), b""):
            if on_chunk is not None:
                on_chunk()
            digest.update(chunk)
    return digest.hexdigest()
