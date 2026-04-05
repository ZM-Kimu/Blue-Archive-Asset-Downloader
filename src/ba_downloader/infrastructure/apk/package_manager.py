from __future__ import annotations

import os
import re
from base64 import b64decode
from binascii import Error as BinasciiError
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from zipfile import ZipFile

from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.domain.ports.http import HttpClientPort, TransportKind, get_header
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.progress.rich_progress import (
    NullProgressReporter,
    RichProgressReporter,
)


@dataclass(frozen=True)
class PackageMetadata:
    file_name: str
    content_length: int


def download_package_file(
    http_client: HttpClientPort,
    logger: LoggerPort,
    package_url: str,
    destination_dir: str,
    *,
    transport: TransportKind = "default",
    headers: Mapping[str, str] | None = None,
) -> str:
    os.makedirs(destination_dir, exist_ok=True)
    metadata = _resolve_package_metadata(
        http_client,
        package_url,
        transport=transport,
        headers=headers,
    )
    destination = str(Path(destination_dir) / metadata.file_name)
    content_length = metadata.content_length

    if content_length and Path(destination).exists() and Path(destination).stat().st_size == content_length:
        return destination

    logger.info(f"Downloading package {metadata.file_name}...")
    progress = (
        RichProgressReporter(
            content_length,
            f"Downloading {metadata.file_name}",
            download_mode=True,
        )
        if content_length
        else NullProgressReporter()
    )
    with progress:
        http_client.download_to_file(
            package_url,
            destination,
            headers=headers,
            transport=transport,
            progress_callback=progress.advance if content_length else None,
        )
    return destination


def extract_xapk_file(package_path: str, extract_dest: str, temp_dir: str) -> None:
    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)
    extract_path = Path(extract_dest)
    extract_path.mkdir(parents=True, exist_ok=True)

    apk_files: list[Path] = []
    with ZipFile(package_path, "r") as package_zip:
        for member in package_zip.namelist():
            if member.lower().endswith(".apk"):
                package_zip.extract(member, temp_path)
                apk_files.append(temp_path / member)

    for apk_file in apk_files:
        with ZipFile(apk_file, "r") as apk_zip:
            apk_zip.extractall(extract_path)


def _resolve_package_metadata(
    http_client: HttpClientPort,
    package_url: str,
    *,
    transport: TransportKind,
    headers: Mapping[str, str] | None,
) -> PackageMetadata:
    head_file_name = ""
    head_content_length = 0

    try:
        head_response = http_client.request(
            "HEAD",
            package_url,
            headers=headers,
            transport=transport,
            timeout=15.0,
        )
    except NetworkError:
        head_response = None

    if head_response is not None and 200 <= head_response.status_code < 400:
        head_file_name = _resolve_filename(
            get_header(head_response.headers, "Content-Disposition"),
            head_response.url,
        )
        head_content_length = _resolve_content_length(head_response.headers)

    return PackageMetadata(
        file_name=head_file_name or _resolve_filename("", package_url),
        content_length=head_content_length or _resolve_content_length_from_url(package_url),
    )


def _resolve_content_length(headers: Mapping[str, str]) -> int:
    if (content_range := get_header(headers, "Content-Range")) and (
        match := re.search(r"/(?P<size>\d+)$", content_range)
    ):
        return int(match.group("size"))

    if content_length := get_header(headers, "Content-Length"):
        try:
            return int(content_length)
        except ValueError:
            return 0

    return 0


def _resolve_content_length_from_url(package_url: str) -> int:
    query = parse_qs(urlparse(package_url).query)
    encoded_context = query.get("c", [""])[0]
    if not encoded_context:
        return 0

    parts = encoded_context.split("|", maxsplit=2)
    metadata_query = parts[-1] if parts else ""
    if "s=" not in metadata_query:
        padded = metadata_query + "=" * (-len(metadata_query) % 4)
        try:
            metadata_query = b64decode(padded).decode("utf-8")
        except (BinasciiError, UnicodeDecodeError):
            return 0

    size = parse_qs(metadata_query).get("s", [""])[0]
    return int(size) if size.isdigit() else 0


def _resolve_filename(content_disposition: str, package_url: str) -> str:
    return (
        _resolve_filename_from_disposition(content_disposition)
        or _resolve_filename_from_query(package_url)
        or _resolve_filename_from_path(package_url)
    )


def _resolve_filename_from_disposition(content_disposition: str) -> str:
    if filename_match := re.search(
        r"filename\*=UTF-8''(?P<name>[^;]+)", content_disposition, re.I
    ):
        return _sanitize_file_name(unquote(filename_match.group("name")))

    if filename_match := re.search(r'filename="?([^";]+)"?', content_disposition, re.I):
        file_name = filename_match.group(1)
        try:
            return _sanitize_file_name(file_name.encode("ISO8859-1").decode())
        except UnicodeDecodeError:
            return _sanitize_file_name(file_name)

    return ""


def _resolve_filename_from_query(package_url: str) -> str:
    query = parse_qs(urlparse(package_url).query)
    raw_name = query.get("_fn", [""])[0]
    if not raw_name:
        return ""

    candidate = unquote(raw_name)
    if not candidate.lower().endswith((".apk", ".xapk")):
        padded = candidate + "=" * (-len(candidate) % 4)
        try:
            candidate = b64decode(padded).decode("utf-8")
        except (BinasciiError, UnicodeDecodeError):
            return ""

    return _sanitize_file_name(candidate)


def _resolve_filename_from_path(package_url: str) -> str:
    file_name = Path(urlparse(package_url).path).name
    if not file_name:
        return "package.xapk"
    if file_name.lower().endswith((".apk", ".xapk")):
        return _sanitize_file_name(file_name)
    return _sanitize_file_name(f"{file_name}.xapk")


def _sanitize_file_name(file_name: str) -> str:
    normalized = Path(file_name.replace("\\", "/")).name.strip()
    return normalized or "package.xapk"
