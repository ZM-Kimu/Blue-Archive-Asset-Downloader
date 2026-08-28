from __future__ import annotations

import hashlib
import shutil
from binascii import crc32
from pathlib import Path

import pytest

from ba_downloader.infrastructure.files import checksum
from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    write_json_atomic,
)


def test_checksum_algorithms_read_expected_content(tmp_path: Path) -> None:
    payload = (b"core-integrity\x00" * 100_000) + b"tail"
    source = tmp_path / "payload.bin"
    source.write_bytes(payload)
    callback_count = 0

    def on_chunk() -> None:
        nonlocal callback_count
        callback_count += 1

    assert checksum.calculate_crc(source) == crc32(payload) & 0xFFFFFFFF
    assert checksum.calculate_md5(source) == hashlib.md5(payload).hexdigest()
    assert checksum.calculate_sha256(source) == hashlib.sha256(payload).hexdigest()
    assert (
        checksum.calculate_sha256(source, on_chunk=on_chunk)
        == hashlib.sha256(payload).hexdigest()
    )
    assert callback_count == 2


def test_crc_handles_empty_files_and_mmap_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    source = tmp_path / "payload.bin"
    source.write_bytes(b"fallback")

    def unavailable(*args: object, **kwargs: object) -> object:
        _ = (args, kwargs)
        raise ValueError("mapping unavailable")

    monkeypatch.setattr(checksum, "mmap", unavailable)

    assert checksum.calculate_crc(empty) == 0
    assert checksum.calculate_crc(source) == crc32(b"fallback") & 0xFFFFFFFF


def test_atomic_json_validation_failure_preserves_existing_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "state.json"
    destination.write_text('{"old": true}\n', encoding="utf8")

    def reject(path: Path) -> None:
        assert path.parent == destination.parent
        raise ValueError("invalid state")

    with pytest.raises(ValueError, match="invalid state"):
        write_json_atomic(destination, {"new": True}, validate=reject)

    assert destination.read_text(encoding="utf8") == '{"old": true}\n'
    assert not tuple(tmp_path.glob(".state.json.*.tmp"))


def test_directory_publication_replaces_successfully_and_rolls_back_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "published"
    destination.mkdir()
    (destination / "value.txt").write_text("old", encoding="utf8")
    successful = tmp_path / "successful"
    successful.mkdir()
    (successful / "value.txt").write_text("new", encoding="utf8")

    publish_staged_directory(successful, destination)

    assert (destination / "value.txt").read_text(encoding="utf8") == "new"
    failing = tmp_path / "failing"
    failing.mkdir()
    (failing / "value.txt").write_text("unpublished", encoding="utf8")
    real_move = shutil.move

    def fail_move(source: str, target: str) -> str:
        if Path(source) == failing:
            raise OSError("publication failed")
        return real_move(source, target)

    monkeypatch.setattr(shutil, "move", fail_move)

    with pytest.raises(OSError, match="publication failed"):
        publish_staged_directory(failing, destination)

    assert (destination / "value.txt").read_text(encoding="utf8") == "new"
