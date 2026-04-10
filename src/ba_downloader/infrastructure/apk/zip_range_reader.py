from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from ba_downloader.domain.ports.http import HttpClientPort, TransportKind

EOCD_SIGNATURE = 0x06054B50
CENTRAL_DIRECTORY_SIGNATURE = 0x02014B50
LOCAL_FILE_HEADER_SIGNATURE = 0x04034B50
MAX_EOCD_SEARCH_BYTES = 65535 + 22


class ZipCentralDirectoryError(RuntimeError):
    """Raised when the ZIP central directory cannot be located or parsed."""


class ZipEntryNotFoundError(LookupError):
    """Raised when a requested ZIP entry cannot be resolved unambiguously."""


class UnsupportedZipLayoutError(RuntimeError):
    """Raised when the ZIP layout or compression method is unsupported."""


@dataclass(frozen=True, slots=True)
class ZipEntry:
    path: str
    crc32: int
    local_header_offset: int
    compressed_size: int
    uncompressed_size: int
    compression_method: int
    file_name_length: int
    extra_field_length: int


@dataclass(frozen=True, slots=True)
class LocalFileHeader:
    compression_method: int
    compressed_size: int
    uncompressed_size: int
    file_name_length: int
    extra_field_length: int


def read_zip_entries(
    url: str,
    http_client: HttpClientPort,
    *,
    transport: TransportKind = "default",
    timeout: float = 30.0,
) -> list[ZipEntry]:
    file_size = _read_content_length(url, http_client, transport=transport, timeout=timeout)
    if file_size <= 0:
        raise ZipCentralDirectoryError("ZIP content length must be a positive integer.")

    tail_size = min(file_size, MAX_EOCD_SEARCH_BYTES)
    tail_start = file_size - tail_size
    tail_bytes = _request_range(
        url,
        tail_start,
        file_size - 1,
        http_client,
        transport=transport,
        timeout=timeout,
    )
    central_directory_offset, central_directory_size = _parse_eocd(tail_bytes)
    if central_directory_offset + central_directory_size > file_size:
        raise ZipCentralDirectoryError(
            "Central directory points outside the ZIP file bounds.",
        )

    central_directory_bytes = _request_range(
        url,
        central_directory_offset,
        central_directory_offset + central_directory_size - 1,
        http_client,
        transport=transport,
        timeout=timeout,
    )
    return _parse_central_directory(central_directory_bytes)


def find_zip_entry(
    entries: list[ZipEntry],
    *,
    preferred_path: str,
    fallback_name: str,
) -> ZipEntry:
    normalized_preferred = preferred_path.replace("\\", "/").casefold()
    exact_match = next(
        (
            entry
            for entry in entries
            if entry.path.replace("\\", "/").casefold() == normalized_preferred
        ),
        None,
    )
    if exact_match is not None:
        return exact_match

    normalized_name = fallback_name.casefold()
    basename_matches = [
        entry for entry in entries if Path(entry.path).name.casefold() == normalized_name
    ]
    if not basename_matches:
        raise ZipEntryNotFoundError(
            f"Unable to find ZIP entry {preferred_path!r} or basename {fallback_name!r}.",
        )
    if len(basename_matches) > 1:
        matches = ", ".join(sorted(entry.path for entry in basename_matches))
        raise ZipEntryNotFoundError(
            f"Multiple ZIP entries matched basename {fallback_name!r}: {matches}.",
        )
    return basename_matches[0]


def extract_zip_entry(
    url: str,
    entry: ZipEntry,
    destination: str | Path,
    http_client: HttpClientPort,
    *,
    transport: TransportKind = "default",
    timeout: float = 30.0,
) -> Path:
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    local_header = _request_range(
        url,
        entry.local_header_offset,
        entry.local_header_offset + 29,
        http_client,
        transport=transport,
        timeout=timeout,
    )
    if len(local_header) != 30:
        raise ZipCentralDirectoryError(
            f"Incomplete local file header for ZIP entry {entry.path!r}.",
        )

    header = _parse_local_file_header(local_header, entry.path)
    if header.compression_method != entry.compression_method:
        raise ZipCentralDirectoryError(
            f"Compression method mismatch for ZIP entry {entry.path!r}.",
        )
    if header.compressed_size in {0xFFFFFFFF, 0xFFFF} or header.uncompressed_size in {
        0xFFFFFFFF,
        0xFFFF,
    }:
        raise UnsupportedZipLayoutError(
            f"ZIP64 local header is not supported for ZIP entry {entry.path!r}.",
        )

    data_offset = (
        entry.local_header_offset
        + 30
        + header.file_name_length
        + header.extra_field_length
    )
    compressed_data = b""
    if entry.compressed_size:
        compressed_data = _request_range(
            url,
            data_offset,
            data_offset + entry.compressed_size - 1,
            http_client,
            transport=transport,
            timeout=timeout,
        )
    decompressed = _decompress_entry(entry, compressed_data)
    if len(decompressed) != entry.uncompressed_size:
        raise ZipCentralDirectoryError(
            f"Extracted ZIP entry {entry.path!r} has unexpected size "
            f"{len(decompressed)} (expected {entry.uncompressed_size}).",
        )

    destination_path.write_bytes(decompressed)
    return destination_path


def _read_content_length(
    url: str,
    http_client: HttpClientPort,
    *,
    transport: TransportKind,
    timeout: float,
) -> int:
    response = http_client.request(
        "HEAD",
        url,
        transport=transport,
        timeout=timeout,
    )
    content_length = response.header("Content-Length").strip()
    if not content_length:
        raise ZipCentralDirectoryError(
            f"Content-Length was not provided for ZIP URL {url!r}.",
        )
    try:
        return int(content_length)
    except ValueError as exc:
        raise ZipCentralDirectoryError(
            f"Content-Length was invalid for ZIP URL {url!r}: {content_length!r}.",
        ) from exc


def _request_range(
    url: str,
    start: int,
    end: int,
    http_client: HttpClientPort,
    *,
    transport: TransportKind,
    timeout: float,
) -> bytes:
    if start < 0 or end < start:
        raise ZipCentralDirectoryError(
            f"Invalid byte range requested for ZIP URL {url!r}: {start}-{end}.",
        )
    response = http_client.request(
        "GET",
        url,
        headers={"Range": f"bytes={start}-{end}"},
        transport=transport,
        timeout=timeout,
    )
    return response.content


def _parse_eocd(data: bytes) -> tuple[int, int]:
    signature_bytes = struct.pack("<I", EOCD_SIGNATURE)
    eocd_offset = data.rfind(signature_bytes)
    if eocd_offset == -1 or eocd_offset + 22 > len(data):
        raise ZipCentralDirectoryError("Unable to locate a valid EOCD record.")

    (
        _signature,
        disk_number,
        central_directory_disk,
        _entries_this_disk,
        _entries_total,
        central_directory_size,
        central_directory_offset,
        _comment_length,
    ) = struct.unpack("<IHHHHIIH", data[eocd_offset : eocd_offset + 22])

    if disk_number != 0 or central_directory_disk != 0:
        raise UnsupportedZipLayoutError("Multi-disk ZIP archives are not supported.")
    if central_directory_size == 0xFFFFFFFF or central_directory_offset == 0xFFFFFFFF:
        raise UnsupportedZipLayoutError("ZIP64 archives are not supported.")
    return central_directory_offset, central_directory_size


def _parse_central_directory(data: bytes) -> list[ZipEntry]:
    entries: list[ZipEntry] = []
    offset = 0
    while offset < len(data):
        entry, offset = _parse_central_directory_record(data, offset)
        entries.append(entry)
    return entries


def _parse_local_file_header(data: bytes, entry_path: str) -> LocalFileHeader:
    (
        signature,
        _version_needed,
        _flags,
        compression_method,
        _modified_time,
        _modified_date,
        _crc,
        compressed_size,
        uncompressed_size,
        file_name_length,
        extra_field_length,
    ) = struct.unpack("<IHHHHHIIIHH", data)
    if signature != LOCAL_FILE_HEADER_SIGNATURE:
        raise ZipCentralDirectoryError(
            f"Invalid local file header signature for ZIP entry {entry_path!r}.",
        )
    return LocalFileHeader(
        compression_method=compression_method,
        compressed_size=compressed_size,
        uncompressed_size=uncompressed_size,
        file_name_length=file_name_length,
        extra_field_length=extra_field_length,
    )


def _parse_central_directory_record(
    data: bytes,
    offset: int,
) -> tuple[ZipEntry, int]:
    if offset + 46 > len(data):
        raise ZipCentralDirectoryError("Central directory record is truncated.")

    record = struct.unpack("<IHHHHHHIIIHHHHHII", data[offset : offset + 46])
    if record[0] != CENTRAL_DIRECTORY_SIGNATURE:
        raise ZipCentralDirectoryError("Invalid central directory signature.")
    if (
        record[8] == 0xFFFFFFFF
        or record[9] == 0xFFFFFFFF
        or record[16] == 0xFFFFFFFF
    ):
        raise UnsupportedZipLayoutError("ZIP64 central directory entries are not supported.")
    if record[13] != 0:
        raise UnsupportedZipLayoutError("Multi-disk ZIP entries are not supported.")

    name_start = offset + 46
    name_end = name_start + record[10]
    extra_end = name_end + record[11]
    comment_end = extra_end + record[12]
    if comment_end > len(data):
        raise ZipCentralDirectoryError("Central directory entry exceeds payload bounds.")

    return (
        ZipEntry(
            path=_decode_file_name(data[name_start:name_end], record[3]),
            crc32=record[7],
            local_header_offset=record[16],
            compressed_size=record[8],
            uncompressed_size=record[9],
            compression_method=record[4],
            file_name_length=record[10],
            extra_field_length=record[11],
        ),
        comment_end,
    )


def _decode_file_name(raw_name: bytes, flags: int) -> str:
    if flags & 0x0800:
        return raw_name.decode("utf8")
    return raw_name.decode("cp437")


def _decompress_entry(entry: ZipEntry, compressed_data: bytes) -> bytes:
    if entry.compression_method == 0:
        return compressed_data
    if entry.compression_method == 8:
        try:
            return zlib.decompress(compressed_data, -zlib.MAX_WBITS)
        except zlib.error as exc:
            raise ZipCentralDirectoryError(
                f"Failed to decompress ZIP entry {entry.path!r}: {exc}.",
            ) from exc
    raise UnsupportedZipLayoutError(
        f"Compression method {entry.compression_method} is not supported for ZIP entry {entry.path!r}.",
    )
