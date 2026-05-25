from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from time import monotonic
from typing import Any

from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.domain.ports.http import DownloadResult, get_header

CONTENT_RANGE_PATTERN = re.compile(r"bytes (\d+)-(\d+)/(\d+)")


class CancelledDownloadError(Exception):
    """Internal sentinel for cooperative cancellation."""


class DownloadResumeSession:
    def __init__(
        self,
        *,
        url: str,
        destination: Path,
        headers: Mapping[str, str] | None,
        max_retries: int,
        timeout: float,
        progress_callback: Callable[[int], None] | None,
        should_stop: Callable[[], bool] | None,
        open_stream: Callable[[Mapping[str, str]], Any],
        iter_chunks: Callable[[Any], Iterator[bytes]],
        timeout_exceptions: tuple[type[BaseException], ...],
        resumable_exceptions: tuple[type[BaseException], ...],
    ) -> None:
        self.url = url
        self.destination = destination
        self.headers = headers
        self.max_retries = max_retries
        self.timeout = timeout
        self.progress_callback = progress_callback
        self.should_stop = should_stop
        self.open_stream = open_stream
        self.iter_chunks = iter_chunks
        self.timeout_exceptions = timeout_exceptions
        self.resumable_exceptions = resumable_exceptions

    def run(self) -> DownloadResult:
        part_path = self.partial_download_path(self.destination)
        self.destination.unlink(missing_ok=True)
        part_path.unlink(missing_ok=True)
        last_error: BaseException | None = None

        try:
            for _attempt in range(max(1, self.max_retries + 1)):
                if self.should_stop is not None and self.should_stop():
                    raise CancelledDownloadError()

                resume_offset = self.safe_file_size(part_path)
                request_headers = self.build_download_headers(
                    self.headers,
                    resume_offset,
                )
                try:
                    with self.open_stream(request_headers) as response:
                        status_code = int(response.status_code)
                        response_headers = dict(response.headers)
                        response_url = str(response.url)
                        start_offset, file_mode = self.prepare_download_segment(
                            part_path,
                            status_code=status_code,
                            headers=response_headers,
                            resume_offset=resume_offset,
                        )
                        bytes_written = self.stream_to_destination(
                            part_path,
                            url=self.url,
                            mode=file_mode,
                            iterator=self.iter_chunks(response),
                            timeout_exceptions=self.timeout_exceptions,
                            stall_timeout=self.timeout,
                            progress_callback=self.progress_callback,
                            should_stop=self.should_stop,
                        )
                        if not self.is_download_complete(
                            status_code=status_code,
                            headers=response_headers,
                            start_offset=start_offset,
                            bytes_written=bytes_written,
                            part_size=self.safe_file_size(part_path),
                        ):
                            raise NetworkError(
                                "incomplete response body "
                                f"(expected complete file, got {self.safe_file_size(part_path)} bytes)"
                            )

                        part_path.replace(self.destination)
                        return DownloadResult(
                            path=str(self.destination),
                            bytes_written=self.destination.stat().st_size,
                            status_code=status_code,
                            headers=response_headers,
                            url=response_url,
                        )
                except CancelledDownloadError:
                    raise
                except self.resumable_exceptions as exc:
                    if self.should_stop is not None and self.should_stop():
                        raise CancelledDownloadError() from exc
                    last_error = exc

            raise NetworkError(
                "download did not complete after "
                f"{max(1, self.max_retries + 1)} attempts: {last_error}"
            ) from last_error
        except BaseException:
            self.destination.unlink(missing_ok=True)
            part_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def partial_download_path(destination: Path) -> Path:
        return destination.with_name(f"{destination.name}.part")

    @staticmethod
    def safe_file_size(path: Path) -> int:
        try:
            return path.stat().st_size
        except FileNotFoundError:
            return 0

    @staticmethod
    def build_download_headers(
        headers: Mapping[str, str] | None,
        resume_offset: int,
    ) -> dict[str, str]:
        request_headers = dict(headers or {})
        request_headers.setdefault("Accept-Encoding", "identity")
        if resume_offset:
            request_headers["Range"] = f"bytes={resume_offset}-"
        else:
            request_headers.pop("Range", None)
        return request_headers

    def prepare_download_segment(
        self,
        part_path: Path,
        *,
        status_code: int,
        headers: Mapping[str, str],
        resume_offset: int,
    ) -> tuple[int, str]:
        if not resume_offset:
            return 0, "wb"

        if status_code == 200:
            part_path.unlink(missing_ok=True)
            return 0, "wb"

        if status_code != 206:
            raise NetworkError(f"unexpected HTTP status {status_code}")

        self.parse_content_range(headers, expected_start=resume_offset)
        return resume_offset, "ab"

    def stream_to_destination(
        self,
        destination: Path,
        *,
        url: str,
        mode: str = "wb",
        iterator: Iterator[bytes],
        timeout_exceptions: tuple[type[BaseException], ...],
        stall_timeout: float,
        progress_callback: Callable[[int], None] | None,
        should_stop: Callable[[], bool] | None,
    ) -> int:
        bytes_written = 0
        last_chunk_at = monotonic()

        with destination.open(mode) as file_handle:
            while True:
                if should_stop is not None and should_stop():
                    raise CancelledDownloadError()

                try:
                    chunk = next(iterator)
                except StopIteration:
                    break
                except timeout_exceptions as exc:
                    if should_stop is not None and should_stop():
                        raise CancelledDownloadError() from exc
                    if monotonic() - last_chunk_at >= stall_timeout:
                        raise NetworkError(
                            f"Failed to download {url}: the read operation timed out."
                        ) from exc
                    continue

                if not chunk:
                    continue

                file_handle.write(chunk)
                bytes_written += len(chunk)
                last_chunk_at = monotonic()
                if progress_callback is not None:
                    progress_callback(len(chunk))

        return bytes_written

    def is_download_complete(
        self,
        *,
        status_code: int,
        headers: Mapping[str, str],
        start_offset: int,
        bytes_written: int,
        part_size: int,
    ) -> bool:
        if status_code == 206:
            range_start, range_end, total_size = self.parse_content_range(
                headers,
                expected_start=start_offset,
            )
            expected_bytes = range_end - range_start + 1
            if bytes_written != expected_bytes:
                raise NetworkError(
                    "incomplete response body "
                    f"(expected {expected_bytes} bytes, got {bytes_written} bytes)"
                )
            return part_size == total_size

        if status_code >= 400:
            return True

        if get_header(headers, "Content-Encoding"):
            return True

        content_length = get_header(headers, "Content-Length").strip()
        if not content_length:
            return True

        try:
            expected_bytes = int(content_length)
        except ValueError:
            return True

        if expected_bytes != bytes_written:
            raise NetworkError(
                "incomplete response body "
                f"(expected {expected_bytes} bytes, got {bytes_written} bytes)"
            )

        return True

    @staticmethod
    def parse_content_range(
        headers: Mapping[str, str],
        *,
        expected_start: int,
    ) -> tuple[int, int, int]:
        content_range = get_header(headers, "Content-Range").strip()
        range_match = CONTENT_RANGE_PATTERN.fullmatch(content_range)
        if range_match is None:
            raise NetworkError(
                "Missing or invalid Content-Range "
                f"for resume offset {expected_start}: {content_range!r}"
            )

        actual_start = int(range_match.group(1))
        actual_end = int(range_match.group(2))
        total_size = int(range_match.group(3))
        if actual_start != expected_start or actual_end < actual_start:
            raise NetworkError(
                "Unexpected Content-Range "
                f"for resume offset {expected_start}: {content_range!r}"
            )
        return actual_start, actual_end, total_size
