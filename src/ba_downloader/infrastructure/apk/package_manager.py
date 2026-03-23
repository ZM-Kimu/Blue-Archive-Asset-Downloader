from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse
from zipfile import ZipFile

from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.progress.rich_progress import (
    NullProgressReporter,
    RichProgressReporter,
)


def download_package_file(
    http_client: HttpClientPort,
    logger: LoggerPort,
    package_url: str,
    destination_dir: str,
    *,
    transport: str = "default",
    headers: dict[str, str] | None = None,
) -> str:
    os.makedirs(destination_dir, exist_ok=True)
    head_response = http_client.request(
        "HEAD",
        package_url,
        headers=headers,
        transport=transport,
        timeout=15.0,
    )
    file_name = _resolve_filename(
        head_response.headers.get("Content-Disposition", ""),
        package_url,
    )
    destination = str(Path(destination_dir) / file_name)
    content_length = int(head_response.headers.get("Content-Length", "0") or 0)

    if content_length and Path(destination).exists():
        if Path(destination).stat().st_size == content_length:
            return destination

    logger.info(f"Downloading package {file_name}...")
    progress = (
        RichProgressReporter(content_length, f"Downloading {file_name}", download_mode=True)
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


def _resolve_filename(content_disposition: str, package_url: str) -> str:
    if filename_match := re.search(
        r"filename\*=UTF-8''(?P<name>[^;]+)", content_disposition, re.I
    ):
        return unquote(filename_match.group("name"))

    if filename_match := re.search(r'filename="?([^";]+)"?', content_disposition, re.I):
        file_name = filename_match.group(1)
        try:
            return file_name.encode("ISO8859-1").decode()
        except UnicodeDecodeError:
            return file_name

    file_name = Path(urlparse(package_url).path).name
    if not file_name:
        return "package.xapk"
    if not file_name.lower().endswith((".apk", ".xapk")):
        return f"{file_name}.xapk"
    return file_name
