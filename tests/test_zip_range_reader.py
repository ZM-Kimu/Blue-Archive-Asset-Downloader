from __future__ import annotations

import re
import struct
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpResponse
from ba_downloader.infrastructure.apk import (
    UnsupportedZipLayoutError,
    ZipCentralDirectoryError,
    ZipEntry,
    ZipEntryNotFoundError,
    extract_zip_entry,
    find_zip_entry,
    read_zip_entries,
)
from ba_downloader.infrastructure.regions.providers.cn import (
    CNRuntimeAssetPreparer,
    CNServer,
)


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="cn",
        threads=1,
        version="",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _build_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for entry_name, content in entries.items():
            archive.writestr(entry_name, content)
    return buffer.getvalue()


class RangeHttpClient:
    def __init__(self, archive_bytes: bytes) -> None:
        self.archive_bytes = archive_bytes
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: object | None = None,
        data: object | None = None,
        params: dict[str, object] | None = None,
        transport: str = "default",
        timeout: float = 10.0,
    ) -> HttpResponse:
        _ = (json, data, params, timeout)
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "transport": transport,
            }
        )
        if method == "HEAD":
            return HttpResponse(
                status_code=200,
                headers={"Content-Length": str(len(self.archive_bytes))},
                content=b"",
                url=url,
            )

        range_header = dict(headers or {}).get("Range", "")
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", range_header)
        if match is None:
            raise AssertionError(f"Unexpected range header: {range_header!r}")
        start = int(match.group(1))
        end = int(match.group(2))
        return HttpResponse(
            status_code=206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(self.archive_bytes)}"},
            content=self.archive_bytes[start : end + 1],
            url=url,
        )

    def download_to_file(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        raise AssertionError("download_to_file must not be called for ZIP range tests.")

    def close(self) -> None:
        return None


class RecordingLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warn_messages: list[str] = []
        self.error_messages: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def warn(self, message: str) -> None:
        self.warn_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)


def test_zip_range_reader_reads_entries_and_extracts_metadata(tmp_path: Path) -> None:
    archive_bytes = _build_zip_bytes(
        {
            "assets/bin/Data/Managed/Metadata/global-metadata.dat": b"metadata",
            "assets/bin/Data/other.bin": b"payload",
        }
    )
    client = RangeHttpClient(archive_bytes)
    url = "https://example.invalid/cn.apk"

    entries = read_zip_entries(url, client)
    entry = find_zip_entry(
        entries,
        preferred_path="assets/bin/Data/Managed/Metadata/global-metadata.dat",
        fallback_name="global-metadata.dat",
    )
    destination = tmp_path / "global-metadata.dat"

    extracted_path = extract_zip_entry(url, entry, destination, client)

    assert extracted_path == destination
    assert destination.read_bytes() == b"metadata"
    assert [call["method"] for call in client.calls] == ["HEAD", "GET", "GET", "GET", "GET"]


def test_find_zip_entry_raises_when_basename_match_is_ambiguous() -> None:
    entries = [
        ZipEntry(
            path="a/global-metadata.dat",
            crc32=0,
            local_header_offset=0,
            compressed_size=1,
            uncompressed_size=1,
            compression_method=0,
            file_name_length=1,
            extra_field_length=0,
        ),
        ZipEntry(
            path="b/global-metadata.dat",
            crc32=0,
            local_header_offset=2,
            compressed_size=1,
            uncompressed_size=1,
            compression_method=0,
            file_name_length=1,
            extra_field_length=0,
        ),
    ]

    with pytest.raises(ZipEntryNotFoundError, match="Multiple ZIP entries matched basename"):
        find_zip_entry(
            entries,
            preferred_path="assets/bin/Data/Managed/Metadata/global-metadata.dat",
            fallback_name="global-metadata.dat",
        )


def test_zip_range_reader_raises_when_eocd_is_missing() -> None:
    client = RangeHttpClient(b"not a zip archive")

    with pytest.raises(ZipCentralDirectoryError, match="EOCD"):
        read_zip_entries("https://example.invalid/cn.apk", client)


def test_zip_range_reader_raises_when_zip64_eocd_is_detected() -> None:
    eocd_bytes = b"prefix" + struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        0,
        0,
        0xFFFFFFFF,
        0xFFFFFFFF,
        0,
    )
    client = RangeHttpClient(eocd_bytes)

    with pytest.raises(UnsupportedZipLayoutError, match="ZIP64"):
        read_zip_entries("https://example.invalid/cn.apk", client)


def test_cn_runtime_asset_preparer_extracts_metadata_without_full_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_bytes = _build_zip_bytes(
        {
            "assets/bin/Data/Managed/Metadata/global-metadata.dat": b"metadata",
            "assets/bin/Data/other.bin": b"payload",
        }
    )
    client = RangeHttpClient(archive_bytes)
    logger = RecordingLogger()
    context = _build_context(tmp_path)
    preparer = CNRuntimeAssetPreparer(client, logger)

    monkeypatch.setattr(
        CNServer,
        "get_apk_url",
        lambda self, server="official": "https://example.invalid/cn.apk",
    )

    preparer.prepare(context)

    metadata_path = Path(context.temp_dir) / "CN_Metadata" / "global-metadata.dat"
    assert metadata_path.read_bytes() == b"metadata"
    assert all(
        call["method"] == "HEAD" or "Range" in call["headers"]
        for call in client.calls
    )
    assert logger.info_messages == ["Preparing CN metadata from APK central directory..."]


def test_cn_runtime_asset_preparer_raises_when_metadata_entry_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_bytes = _build_zip_bytes(
        {
            "assets/bin/Data/other.bin": b"payload",
        }
    )
    client = RangeHttpClient(archive_bytes)
    preparer = CNRuntimeAssetPreparer(client, RecordingLogger())
    context = _build_context(tmp_path)

    monkeypatch.setattr(
        CNServer,
        "get_apk_url",
        lambda self, server="official": "https://example.invalid/cn.apk",
    )

    with pytest.raises(ZipEntryNotFoundError, match=r"global-metadata\.dat"):
        preparer.prepare(context)


def test_cn_runtime_asset_preparer_raises_when_metadata_basename_is_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_bytes = _build_zip_bytes(
        {
            "a/global-metadata.dat": b"first",
            "b/global-metadata.dat": b"second",
        }
    )
    client = RangeHttpClient(archive_bytes)
    preparer = CNRuntimeAssetPreparer(client, RecordingLogger())
    context = _build_context(tmp_path)

    monkeypatch.setattr(
        CNServer,
        "get_apk_url",
        lambda self, server="official": "https://example.invalid/cn.apk",
    )

    with pytest.raises(ZipEntryNotFoundError, match="Multiple ZIP entries matched basename"):
        preparer.prepare(context)


def test_cn_runtime_asset_preparer_raises_for_zip64_layout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    eocd_bytes = b"prefix" + struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        0,
        0,
        0xFFFFFFFF,
        0xFFFFFFFF,
        0,
    )
    client = RangeHttpClient(eocd_bytes)
    preparer = CNRuntimeAssetPreparer(client, RecordingLogger())
    context = _build_context(tmp_path)

    monkeypatch.setattr(
        CNServer,
        "get_apk_url",
        lambda self, server="official": "https://example.invalid/cn.apk",
    )

    with pytest.raises(UnsupportedZipLayoutError, match="ZIP64"):
        preparer.prepare(context)
