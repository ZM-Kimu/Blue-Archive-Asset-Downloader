from __future__ import annotations

import hashlib
from pathlib import Path
from zlib import crc32

import pytest

from ba_downloader.infrastructure.files import checksum as checksum_module
from ba_downloader.infrastructure.files.checksum import (
    calculate_crc,
    calculate_md5,
    calculate_sha256,
    calculate_source_fingerprint,
)


def test_calculate_md5_matches_hashlib(tmp_path: Path) -> None:
    payload = (b"BlueArchive" * 131072) + b"!"
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(payload)

    assert calculate_md5(str(file_path)) == hashlib.md5(payload).hexdigest()


def test_calculate_crc_matches_zlib(tmp_path: Path) -> None:
    payload = (b"Sensei" * 131072) + b"?"
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(payload)

    assert calculate_crc(str(file_path)) == crc32(payload) & 0xFFFFFFFF


def test_calculate_crc_falls_back_when_memory_mapping_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = (b"fallback" * 131072) + b"!"
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(payload)

    def reject_mapping(*_args: object, **_kwargs: object) -> None:
        raise OSError("mapping unavailable")

    monkeypatch.setattr(checksum_module, "mmap", reject_mapping)

    assert calculate_crc(file_path) == crc32(payload) & 0xFFFFFFFF


def test_checksum_functions_support_empty_files(tmp_path: Path) -> None:
    file_path = tmp_path / "empty.bin"
    file_path.touch()

    assert calculate_crc(file_path) == 0
    assert calculate_md5(file_path) == hashlib.md5(b"").hexdigest()
    assert calculate_sha256(file_path) == hashlib.sha256(b"").hexdigest()


def test_calculate_sha256_without_callback_matches_hashlib(tmp_path: Path) -> None:
    payload = (b"fast-sha" * 131072) + b"!"
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(payload)

    assert calculate_sha256(file_path) == hashlib.sha256(payload).hexdigest()


def test_calculate_sha256_streaming_reports_each_chunk(tmp_path: Path) -> None:
    payload = b"a" * (1024 * 1024 + 1)
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(payload)
    chunks: list[None] = []

    assert calculate_sha256(file_path, on_chunk=lambda: chunks.append(None)) == (
        hashlib.sha256(payload).hexdigest()
    )
    assert len(chunks) == 2


def test_source_fingerprint_is_ordered_and_line_ending_independent(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.cs"
    second = tmp_path / "second.csproj"
    first.write_bytes(b"line-one\r\nline-two\r\n")
    second.write_bytes(b"<Project />\r")

    windows = calculate_source_fingerprint(
        tmp_path,
        (second, first),
        identities=(("dependency", "commit-a"),),
    )
    first.write_bytes(b"line-one\nline-two\n")
    second.write_bytes(b"<Project />\n")
    unix = calculate_source_fingerprint(
        tmp_path,
        (first, second),
        identities=(("dependency", "commit-a"),),
    )

    assert windows == unix


def test_source_fingerprint_changes_with_source_or_dependency_identity(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Program.cs"
    source.write_text("first", encoding="utf8")
    initial = calculate_source_fingerprint(
        tmp_path,
        (source,),
        identities=(("dependency", "commit-a"),),
    )
    changed_dependency = calculate_source_fingerprint(
        tmp_path,
        (source,),
        identities=(("dependency", "commit-b"),),
    )
    source.write_text("second", encoding="utf8")
    changed_source = calculate_source_fingerprint(
        tmp_path,
        (source,),
        identities=(("dependency", "commit-a"),),
    )

    assert len({initial, changed_dependency, changed_source}) == 3
