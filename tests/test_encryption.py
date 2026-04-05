from __future__ import annotations

import hashlib
from pathlib import Path
from zlib import crc32

from ba_downloader.shared.crypto.encryption import calculate_crc, calculate_md5


def test_calculate_md5_streaming_matches_hashlib(tmp_path: Path) -> None:
    payload = (b"BlueArchive" * 131072) + b"!"
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(payload)

    assert calculate_md5(str(file_path)) == hashlib.md5(payload).hexdigest()


def test_calculate_crc_streaming_matches_xxhash(tmp_path: Path) -> None:
    payload = (b"Sensei" * 131072) + b"?"
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(payload)

    assert calculate_crc(str(file_path)) == crc32(payload) & 0xFFFFFFFF
