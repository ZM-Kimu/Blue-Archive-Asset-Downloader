from __future__ import annotations

import os
import re
import shutil
from base64 import b64decode
from binascii import Error as BinasciiError
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, unquote, urlparse
from zipfile import BadZipFile, ZipFile, is_zipfile

from ba_downloader.domain.exceptions import NetworkError, OperationCancelledError
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.http import HttpClientPort, TransportKind, get_header
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import (
    ProgressMeasure,
    ProgressReporterFactoryPort,
    ProgressState,
)
from ba_downloader.infrastructure.files.size import format_file_size
from ba_downloader.infrastructure.progress import NullProgressReporterFactory


@dataclass(frozen=True)
class PackageMetadata:
    file_name: str
    content_length: int


class PackageArchiveError(LookupError):
    """Package archive is invalid or incomplete."""


@dataclass(frozen=True)
class PackagePart:
    index: int
    start: int
    end: int
    path: Path

    @property
    def size(self) -> int:
        return self.end - self.start + 1


MULTIPART_MIN_PACKAGE_BYTES = 32 * 1024 * 1024
MULTIPART_PART_BYTES = 8 * 1024 * 1024
MULTIPART_MAX_WORKERS = 4
MULTIPART_PART_ATTEMPTS = 3
MULTIPART_PROBE_TIMEOUT = 30.0
MULTIPART_PART_TIMEOUT = 120.0


def download_package_file(
    http_client: HttpClientPort,
    logger: LoggerPort,
    package_url: str,
    destination_dir: str,
    *,
    transport: TransportKind = "default",
    headers: Mapping[str, str] | None = None,
    progress_factory: ProgressReporterFactoryPort | None = None,
    cancellation: CancellationPort | None = None,
) -> str:
    active_cancellation = cancellation or NeverCancelled()
    active_cancellation.raise_if_cancelled()
    os.makedirs(destination_dir, exist_ok=True)
    metadata = _resolve_package_metadata(
        http_client,
        package_url,
        transport=transport,
        headers=headers,
    )
    destination = str(Path(destination_dir) / metadata.file_name)
    content_length = metadata.content_length

    if (
        content_length
        and Path(destination).exists()
        and Path(destination).stat().st_size == content_length
    ):
        try:
            _validate_package_file(destination, expected_size=content_length)
        except PackageArchiveError:
            pass
        else:
            return destination

    logger.info(f"Downloading package {metadata.file_name}...")
    initial_progress = ProgressState(
        "Package",
        "downloading",
        overall=(
            ProgressMeasure(0, content_length, "bytes")
            if content_length
            else ProgressMeasure(0, 1, "files")
        ),
        item=metadata.file_name,
    )
    with (progress_factory or NullProgressReporterFactory()).create(
        initial_progress
    ) as progress:
        completed = 0
        progress_lock = Lock()

        def report_download(amount: int) -> None:
            nonlocal completed
            with progress_lock:
                completed = min(completed + amount, content_length)
                progress.update(
                    ProgressState(
                        "Package",
                        "downloading",
                        overall=ProgressMeasure(completed, content_length, "bytes"),
                        item=metadata.file_name,
                    )
                )

        try:
            if _should_use_multipart_download(
                http_client,
                package_url,
                expected_size=content_length,
                transport=transport,
                headers=headers,
            ):
                result_path = _download_package_with_parts(
                    http_client,
                    package_url,
                    destination,
                    expected_size=content_length,
                    transport=transport,
                    headers=headers,
                    progress_callback=report_download,
                    cancellation=active_cancellation,
                )
            else:
                download_result = http_client.download_to_file(
                    package_url,
                    destination,
                    headers=headers,
                    transport=transport,
                    progress_callback=report_download if content_length else None,
                )
                active_cancellation.raise_if_cancelled()
                _validate_package_file(
                    download_result.path,
                    expected_size=content_length,
                )
                result_path = download_result.path
        except OperationCancelledError:
            progress.update(
                ProgressState(
                    "Package",
                    "cancelled",
                    overall=(
                        ProgressMeasure(completed, content_length, "bytes")
                        if content_length
                        else ProgressMeasure(0, 1, "files")
                    ),
                    item=metadata.file_name,
                )
            )
            raise
        except BaseException:
            progress.update(
                ProgressState(
                    "Package",
                    "failed",
                    overall=(
                        ProgressMeasure(completed, content_length, "bytes")
                        if content_length
                        else ProgressMeasure(0, 1, "files")
                    ),
                    item=metadata.file_name,
                    failures=1,
                )
            )
            raise
        progress.update(
            ProgressState(
                "Package",
                "complete",
                overall=(
                    ProgressMeasure(content_length, content_length, "bytes")
                    if content_length
                    else ProgressMeasure(1, 1, "files")
                ),
                item=metadata.file_name,
            )
        )
        return result_path


def extract_xapk_file(
    package_path: str,
    extract_dest: str,
    temp_dir: str,
    *,
    cancellation: CancellationPort | None = None,
) -> None:
    active_cancellation = cancellation or NeverCancelled()
    active_cancellation.raise_if_cancelled()
    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)
    extract_path = Path(extract_dest)
    extract_path.mkdir(parents=True, exist_ok=True)

    _validate_package_file(package_path)
    apk_files: list[Path] = []
    try:
        with ZipFile(package_path, "r") as package_zip:
            for member in package_zip.namelist():
                active_cancellation.raise_if_cancelled()
                if member.lower().endswith(".apk"):
                    package_zip.extract(member, temp_path)
                    apk_files.append(temp_path / member)

        for apk_file in apk_files:
            active_cancellation.raise_if_cancelled()
            with ZipFile(apk_file, "r") as apk_zip:
                for archive_member in apk_zip.infolist():
                    active_cancellation.raise_if_cancelled()
                    apk_zip.extract(archive_member, extract_path)
    except (BadZipFile, OSError) as exc:
        _discard_invalid_package(Path(package_path))
        raise PackageArchiveError(
            _build_package_error_message(
                Path(package_path),
                actual_size=_safe_file_size(Path(package_path)),
                reason=f"archive extraction failed with {exc.__class__.__name__}: {exc}",
            )
        ) from exc


def extract_jp_xapk_file(
    package_path: str,
    extract_dest: str,
    temp_dir: str,
    *,
    cancellation: CancellationPort | None = None,
) -> None:
    active_cancellation = cancellation or NeverCancelled()
    active_cancellation.raise_if_cancelled()
    package = Path(package_path)
    extract_root = Path(extract_dest)
    inner_root = Path(temp_dir)
    extract_root.mkdir(parents=True, exist_ok=True)
    inner_root.mkdir(parents=True, exist_ok=True)
    _validate_package_file(package_path)

    selected: list[tuple[Path, str]] = []
    try:
        with ZipFile(package, "r") as xapk:
            apk_members = [
                info
                for info in xapk.infolist()
                if not info.is_dir() and info.filename.lower().endswith(".apk")
            ]
            for index, member in enumerate(apk_members):
                active_cancellation.raise_if_cancelled()
                inner_path = inner_root / f"part-{index:03d}.apk"
                with xapk.open(member) as source, inner_path.open("wb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                with ZipFile(inner_path, "r") as apk:
                    names = [
                        info.filename.replace("\\", "/") for info in apk.infolist()
                    ]
                has_metadata = (
                    "assets/bin/Data/Managed/Metadata/global-metadata.dat" in names
                )
                has_arm64 = any(name.startswith("lib/arm64-v8a/") for name in names)
                has_unity_data = any(
                    name.startswith("assets/bin/Data/") for name in names
                )
                if has_metadata:
                    selected.append((inner_path, "base"))
                elif has_arm64:
                    selected.append((inner_path, "arm64"))
                elif has_unity_data:
                    selected.append((inner_path, "unity_data"))

        roles = [role for _, role in selected]
        if roles.count("base") != 1 or roles.count("arm64") != 1:
            raise PackageArchiveError(
                "JP XAPK must contain exactly one base APK and one ARM64 split."
            )
        for inner_path, role in selected:
            active_cancellation.raise_if_cancelled()
            with ZipFile(inner_path, "r") as apk:
                for member in apk.infolist():
                    active_cancellation.raise_if_cancelled()
                    normalized = member.filename.replace("\\", "/")
                    if member.is_dir():
                        continue
                    if role == "arm64":
                        include = normalized.startswith(
                            "lib/arm64-v8a/"
                        ) and normalized.lower().endswith(".so")
                    else:
                        include = normalized.startswith("assets/bin/Data/")
                    if include:
                        _extract_member_safely(apk, member, extract_root)
    except PackageArchiveError:
        raise
    except (BadZipFile, OSError) as exc:
        raise PackageArchiveError(
            _build_package_error_message(
                package,
                actual_size=_safe_file_size(package),
                reason=f"selective JP extraction failed with {exc.__class__.__name__}: {exc}",
            )
        ) from exc
    finally:
        shutil.rmtree(inner_root, ignore_errors=True)


def _extract_member_safely(
    archive: ZipFile,
    member,
    destination_root: Path,
) -> None:
    normalized = member.filename.replace("\\", "/").lstrip("/")
    destination = (destination_root / normalized).resolve()
    try:
        destination.relative_to(destination_root.resolve())
    except ValueError as exc:
        raise PackageArchiveError(
            f"Archive member escapes extraction root: {member.filename!r}."
        ) from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as source, destination.open("wb") as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)


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
        content_length=head_content_length
        or _resolve_content_length_from_url(package_url),
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


def _should_use_multipart_download(
    http_client: HttpClientPort,
    package_url: str,
    *,
    expected_size: int,
    transport: TransportKind,
    headers: Mapping[str, str] | None,
) -> bool:
    if expected_size < MULTIPART_MIN_PACKAGE_BYTES:
        return False

    try:
        response = http_client.request(
            "GET",
            package_url,
            headers=_build_range_headers(headers, 0, 0),
            transport=transport,
            timeout=MULTIPART_PROBE_TIMEOUT,
        )
    except NetworkError:
        return False

    try:
        _validate_range_response(response, start=0, end=0, total_size=expected_size)
    except PackageArchiveError:
        return False
    return True


def _download_package_with_parts(
    http_client: HttpClientPort,
    package_url: str,
    destination: str,
    *,
    expected_size: int,
    transport: TransportKind,
    headers: Mapping[str, str] | None,
    progress_callback: Callable[[int], None] | None,
    cancellation: CancellationPort,
) -> str:
    destination_path = Path(destination)
    parts_dir = destination_path.with_name(f"{destination_path.name}.parts")
    progress_lock = Lock()
    parts = _build_package_parts(parts_dir, expected_size)
    _reset_parts_directory(parts_dir)

    try:
        with ThreadPoolExecutor(
            max_workers=min(MULTIPART_MAX_WORKERS, max(len(parts), 1))
        ) as executor:
            future_map: dict[Future[None], PackagePart] = {
                executor.submit(
                    _download_package_part,
                    http_client,
                    package_url,
                    part,
                    expected_size=expected_size,
                    transport=transport,
                    headers=headers,
                    cancellation=cancellation,
                ): part
                for part in parts
            }
            pending_futures = set(future_map)
            while pending_futures:
                cancellation.raise_if_cancelled()
                done_futures, pending_futures = wait(
                    pending_futures,
                    timeout=0.1,
                    return_when=FIRST_COMPLETED,
                )
                for future in done_futures:
                    part = future_map[future]
                    try:
                        future.result()
                    except (OperationCancelledError, PackageArchiveError):
                        for pending in pending_futures:
                            pending.cancel()
                        raise

                    if progress_callback is not None:
                        with progress_lock:
                            progress_callback(part.size)

        _assemble_package_file(parts, destination_path)
        _validate_package_file(str(destination_path), expected_size=expected_size)
        return str(destination_path)
    except (OSError, OperationCancelledError, PackageArchiveError):
        destination_path.unlink(missing_ok=True)
        raise
    finally:
        _cleanup_parts_directory(parts_dir)


def _build_package_parts(parts_dir: Path, total_size: int) -> list[PackagePart]:
    parts: list[PackagePart] = []
    for index, start in enumerate(range(0, total_size, MULTIPART_PART_BYTES)):
        end = min(total_size - 1, start + MULTIPART_PART_BYTES - 1)
        parts.append(
            PackagePart(
                index=index,
                start=start,
                end=end,
                path=parts_dir / f"part-{index:05d}.bin",
            )
        )
    return parts


def _download_package_part(
    http_client: HttpClientPort,
    package_url: str,
    part: PackagePart,
    *,
    expected_size: int,
    transport: TransportKind,
    headers: Mapping[str, str] | None,
    cancellation: CancellationPort,
) -> None:
    last_error: Exception | None = None
    for _attempt in range(1, MULTIPART_PART_ATTEMPTS + 1):
        cancellation.raise_if_cancelled()
        part.path.unlink(missing_ok=True)
        try:
            response = http_client.request(
                "GET",
                package_url,
                headers=_build_range_headers(headers, part.start, part.end),
                transport=transport,
                timeout=MULTIPART_PART_TIMEOUT,
            )
            _validate_range_response(
                response,
                start=part.start,
                end=part.end,
                total_size=expected_size,
            )
            if len(response.content) != part.size:
                raise PackageArchiveError(
                    f"Package part {part.index} returned "
                    f"{format_file_size(len(response.content))}, expected "
                    f"{format_file_size(part.size)}."
                )
            part.path.write_bytes(response.content)
            cancellation.raise_if_cancelled()
            return
        except (NetworkError, OSError, PackageArchiveError) as exc:
            last_error = exc

    raise PackageArchiveError(
        f"Failed to download package part {part.index} after "
        f"{MULTIPART_PART_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def _build_range_headers(
    headers: Mapping[str, str] | None,
    start: int,
    end: int,
) -> dict[str, str]:
    request_headers = dict(headers or {})
    request_headers["Range"] = f"bytes={start}-{end}"
    return request_headers


def _validate_range_response(
    response,
    *,
    start: int,
    end: int,
    total_size: int,
) -> None:
    if response.status_code != 206:
        raise PackageArchiveError(
            f"Unexpected HTTP status {response.status_code} for requested range "
            f"{start}-{end}."
        )

    content_range = get_header(response.headers, "Content-Range")
    range_match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range.strip())
    if range_match is None:
        raise PackageArchiveError(
            f"Missing or invalid Content-Range for requested range {start}-{end}: "
            f"{content_range!r}."
        )

    actual_start = int(range_match.group(1))
    actual_end = int(range_match.group(2))
    actual_total = int(range_match.group(3))
    if actual_start != start or actual_end != end or actual_total != total_size:
        raise PackageArchiveError(
            f"Unexpected Content-Range for requested range {start}-{end}: "
            f"{content_range!r}."
        )


def _assemble_package_file(parts: list[PackagePart], destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with destination_path.open("wb") as destination_handle:
        for part in sorted(parts, key=lambda item: item.index):
            if not part.path.exists():
                raise PackageArchiveError(
                    f"Package part {part.index} is missing during assembly."
                )
            actual_size = part.path.stat().st_size
            if actual_size != part.size:
                raise PackageArchiveError(
                    f"Package part {part.index} has size "
                    f"{format_file_size(actual_size)}, expected "
                    f"{format_file_size(part.size)}."
                )
            with part.path.open("rb") as part_handle:
                shutil.copyfileobj(part_handle, destination_handle)


def _reset_parts_directory(parts_dir: Path) -> None:
    _cleanup_parts_directory(parts_dir)
    parts_dir.mkdir(parents=True, exist_ok=True)


def _cleanup_parts_directory(parts_dir: Path) -> None:
    shutil.rmtree(parts_dir, ignore_errors=True)


def _validate_package_file(package_path: str, *, expected_size: int = 0) -> None:
    path = Path(package_path)
    actual_size = _safe_file_size(path)

    if expected_size and actual_size != expected_size:
        _discard_invalid_package(path)
        raise PackageArchiveError(
            _build_package_error_message(
                path,
                expected_size=expected_size,
                actual_size=actual_size,
                reason="downloaded file size does not match the expected package size",
            )
        )

    try:
        is_archive = is_zipfile(path)
    except OSError:
        is_archive = False

    if not is_archive:
        signature = _read_file_signature(path)
        _discard_invalid_package(path)
        raise PackageArchiveError(
            _build_package_error_message(
                path,
                expected_size=expected_size,
                actual_size=actual_size,
                reason="downloaded file is not a valid ZIP/XAPK archive",
                signature=signature,
            )
        )


def _build_package_error_message(
    package_path: Path,
    *,
    reason: str,
    expected_size: int = 0,
    actual_size: int = 0,
    signature: str = "",
) -> str:
    details = [
        f"Package archive validation failed for {package_path}.",
        f"Reason: {reason}.",
        f"Actual size: {format_file_size(actual_size)}.",
    ]
    if expected_size:
        details.append(f"Expected size: {format_file_size(expected_size)}.")
    if signature:
        details.append(f"Signature: {signature}.")
    return " ".join(details)


def _discard_invalid_package(package_path: Path) -> None:
    try:
        package_path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _safe_file_size(package_path: Path) -> int:
    try:
        return package_path.stat().st_size
    except OSError:
        return 0


def _read_file_signature(package_path: Path, *, preview_bytes: int = 16) -> str:
    try:
        with package_path.open("rb") as package_file:
            signature = package_file.read(preview_bytes)
    except OSError:
        return "unavailable"
    if not signature:
        return "empty"
    return signature.hex(" ")
