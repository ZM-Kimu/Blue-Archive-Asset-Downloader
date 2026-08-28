from __future__ import annotations

import io
import re
from dataclasses import replace
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from ba_downloader.domain.ports.http import DownloadResult, HttpResponse
from ba_downloader.infrastructure.packages.zip_range_reader import (
    UnsupportedZipLayoutError,
    ZipCentralDirectoryError,
    extract_zip_entry,
    find_zip_entry,
    read_zip_entries,
)


class RangeHttpClient:
    def __init__(self, payload: bytes, *, honor_ranges: bool = True) -> None:
        self.payload = payload
        self.honor_ranges = honor_ranges
        self.ranges: list[tuple[int, int]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: object,
    ) -> HttpResponse:
        _ = (url, kwargs)
        if method == "HEAD":
            return HttpResponse(
                200,
                {"Content-Length": str(len(self.payload))},
                b"",
                url,
            )
        assert headers is not None
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", headers["Range"])
        assert match is not None
        start, end = (int(part) for part in match.groups())
        self.ranges.append((start, end))
        if not self.honor_ranges:
            return HttpResponse(200, {}, self.payload, url)
        return HttpResponse(
            206,
            {"Content-Range": f"bytes {start}-{end}/{len(self.payload)}"},
            self.payload[start : end + 1],
            url,
        )

    def download_to_file(self, *args: object, **kwargs: object) -> DownloadResult:
        raise AssertionError("Range tests must not perform a full download.")

    def close(self) -> None:
        return None


@pytest.mark.parametrize("compression", [ZIP_STORED, ZIP_DEFLATED])
def test_reads_central_directory_and_extracts_verified_entry_atomically(
    tmp_path: Path, compression: int
) -> None:
    archive = _zip_bytes(compression, {"folder/asset.bundle": b"bundle payload"})
    client = RangeHttpClient(archive)

    entries = read_zip_entries(
        "https://cdn.example/archive.zip",
        client,
        file_size=len(archive),
    )
    entry = find_zip_entry(
        entries,
        preferred_path=r"folder\ASSET.bundle",
        fallback_name="unused.bundle",
    )
    destination = tmp_path / "asset.bundle"
    destination.write_bytes(b"old")
    extract_zip_entry(
        "https://cdn.example/archive.zip",
        entry,
        destination,
        client,
    )

    assert destination.read_bytes() == b"bundle payload"
    assert len(client.ranges) == 3
    assert not tuple(tmp_path.glob(".asset.bundle.*.tmp"))


def test_rejects_ignored_range_without_touching_destination(tmp_path: Path) -> None:
    archive = _zip_bytes(ZIP_DEFLATED, {"asset.bundle": b"payload"})
    destination = tmp_path / "asset.bundle"
    destination.write_bytes(b"old")

    with pytest.raises(UnsupportedZipLayoutError, match="did not honor"):
        read_zip_entries(
            "https://cdn.example/archive.zip",
            RangeHttpClient(archive, honor_ranges=False),
            file_size=len(archive),
        )

    assert destination.read_bytes() == b"old"


def test_crc_failure_preserves_existing_destination(tmp_path: Path) -> None:
    archive = _zip_bytes(ZIP_STORED, {"asset.bundle": b"payload"})
    client = RangeHttpClient(archive)
    entry = read_zip_entries(
        "https://cdn.example/archive.zip",
        client,
        file_size=len(archive),
    )[0]
    destination = tmp_path / "asset.bundle"
    destination.write_bytes(b"old")

    with pytest.raises(ZipCentralDirectoryError, match="CRC"):
        extract_zip_entry(
            "https://cdn.example/archive.zip",
            replace(entry, crc32=entry.crc32 ^ 1),
            destination,
            client,
        )

    assert destination.read_bytes() == b"old"


def _zip_bytes(compression: int, entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=compression) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return stream.getvalue()
