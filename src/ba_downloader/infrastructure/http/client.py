from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path
from time import monotonic
from typing import Any, Literal

import httpx
from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import RequestException as CurlRequestError
from curl_cffi.requests.exceptions import Timeout as CurlTimeout
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.domain.ports.http import (
    DownloadResult,
    HttpClientPort,
    HttpResponse,
    TransportKind,
    get_header,
)

CURL_TIMEOUT_EXCEPTIONS: tuple[type[BaseException], ...] = (CurlTimeout,)
BROWSER_REQUEST_EXCEPTIONS: tuple[type[BaseException], ...] = (
    CurlRequestError,
    OSError,
)
HTTPX_REQUEST_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.HTTPError,
    httpx.TimeoutException,
    OSError,
)
HTTPX_DOWNLOAD_EXCEPTIONS: tuple[type[BaseException], ...] = (
    *HTTPX_REQUEST_EXCEPTIONS,
    NetworkError,
)
BROWSER_DOWNLOAD_EXCEPTIONS: tuple[type[BaseException], ...] = (
    *BROWSER_REQUEST_EXCEPTIONS,
    NetworkError,
)


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)
CHALLENGE_MARKERS = (
    b"Just a moment",
    b"Attention Required",
    b"cf-chl",
    b"Cloudflare",
)
DEFAULT_DOWNLOAD_TIMEOUT = 600.0
DOWNLOAD_READ_POLL_TIMEOUT = 1.0
DOWNLOAD_CHUNK_SIZE = 64 * 1024
CONNECT_TIMEOUT_CAP = 20.0
CONTENT_RANGE_PATTERN = re.compile(r"bytes (\d+)-(\d+)/(\d+)")


class _CancelledDownloadError(Exception):
    """Internal sentinel for cooperative cancellation."""


class ResilientHttpClient(HttpClientPort):
    def __init__(self, *, proxy_url: str | None = None, max_retries: int = 5) -> None:
        self.proxy_url = proxy_url
        self.max_retries = max_retries
        self._httpx = httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            proxy=proxy_url,
        )
        self._browser: Any = curl_requests.Session(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            impersonate="chrome",
        )
        if proxy_url:
            self._browser.proxies = {"http": proxy_url, "https": proxy_url}

    def request(
        self,
        method: Literal["GET", "POST", "HEAD"],
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: Mapping[str, Any] | None = None,
        transport: TransportKind = "default",
        timeout: float = 10.0,
    ) -> HttpResponse:
        normalized_params = dict(params) if params is not None else None

        if transport == "browser":
            response = self._request_with_browser(
                method,
                url,
                headers=headers,
                json=json,
                data=data,
                params=normalized_params,
                timeout=timeout,
            )
            return self._to_response(response)

        response = self._request_with_httpx(
            method,
            url,
            headers=headers,
            json=json,
            data=data,
            params=normalized_params,
            timeout=timeout,
        )
        normalized = self._to_response(response)
        if self._should_fallback(normalized):
            browser_response = self._request_with_browser(
                method,
                url,
                headers=headers,
                json=json,
                data=data,
                params=normalized_params,
                timeout=timeout,
            )
            return self._to_response(browser_response)
        return normalized

    def download_to_file(
        self,
        url: str,
        destination: str,
        *,
        headers: Mapping[str, str] | None = None,
        transport: TransportKind = "default",
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        progress_callback: Callable[[int], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> DownloadResult:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        if should_stop is not None and should_stop():
            raise NetworkError(f"Failed to download {url}: download cancelled by user.")

        if transport == "browser":
            return self._download_with_browser(
                url,
                destination_path,
                headers=headers,
                timeout=timeout,
                progress_callback=progress_callback,
                should_stop=should_stop,
            )

        result = self._download_with_httpx(
            url,
            destination_path,
            headers=headers,
            timeout=timeout,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        if result.status_code in {403, 429} or (
            "text/html" in get_header(result.headers, "Content-Type").lower()
            and destination_path.read_bytes()[:4096].find(b"Cloudflare") != -1
        ):
            destination_path.unlink(missing_ok=True)
            return self._download_with_browser(
                url,
                destination_path,
                headers=headers,
                timeout=timeout,
                progress_callback=progress_callback,
                should_stop=should_stop,
            )
        return result

    def close(self) -> None:
        self._httpx.close()
        self._browser.close()

    def _request_with_httpx(
        self,
        method: Literal["GET", "POST", "HEAD"],
        url: str,
        *,
        headers: Mapping[str, str] | None,
        json: Any | None,
        data: Any | None,
        params: dict[str, Any] | None,
        timeout: float,
    ) -> httpx.Response:
        retrying = Retrying(
            stop=stop_after_attempt(max(1, self.max_retries + 1)),
            wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
            retry=retry_if_exception_type(HTTPX_REQUEST_EXCEPTIONS),
            reraise=True,
        )
        try:
            for attempt in retrying:
                with attempt:
                    return self._httpx.request(
                        method,
                        url,
                        headers=headers,
                        json=json,
                        data=data,
                        params=params,
                        timeout=timeout,
                    )
        except HTTPX_REQUEST_EXCEPTIONS as exc:
            raise NetworkError(f"Failed to fetch {url}: {exc}") from exc
        raise NetworkError(f"Failed to fetch {url}: unexpected retry state.")

    def _request_with_browser(
        self,
        method: Literal["GET", "POST", "HEAD"],
        url: str,
        *,
        headers: Mapping[str, str] | None,
        json: Any | None,
        data: Any | None,
        params: dict[str, Any] | None,
        timeout: float,
    ):
        retrying = Retrying(
            stop=stop_after_attempt(max(1, self.max_retries + 1)),
            wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
            retry=retry_if_exception_type(BROWSER_REQUEST_EXCEPTIONS),
            reraise=True,
        )
        try:
            for attempt in retrying:
                with attempt:
                    return self._browser.request(
                        method,
                        url,
                        headers=dict(headers or {}),
                        json=json,
                        data=data,
                        params=params,
                        timeout=timeout,
                    )
        except BROWSER_REQUEST_EXCEPTIONS as exc:
            raise NetworkError(f"Failed to fetch {url}: {exc}") from exc
        raise NetworkError(f"Failed to fetch {url}: unexpected retry state.")

    def _download_with_httpx(
        self,
        url: str,
        destination: Path,
        *,
        headers: Mapping[str, str] | None,
        timeout: float,
        progress_callback: Callable[[int], None] | None,
        should_stop: Callable[[], bool] | None,
    ) -> DownloadResult:
        try:
            return self._download_with_resume(
                url,
                destination,
                headers=headers,
                timeout=timeout,
                progress_callback=progress_callback,
                should_stop=should_stop,
                open_stream=lambda request_headers: self._httpx.stream(
                    "GET",
                    url,
                    headers=request_headers,
                    timeout=httpx.Timeout(
                        connect=min(timeout, CONNECT_TIMEOUT_CAP),
                        read=DOWNLOAD_READ_POLL_TIMEOUT,
                        write=min(timeout, CONNECT_TIMEOUT_CAP),
                        pool=min(timeout, CONNECT_TIMEOUT_CAP),
                    ),
                ),
                iter_chunks=lambda response: response.iter_bytes(
                    chunk_size=DOWNLOAD_CHUNK_SIZE
                ),
                timeout_exceptions=(httpx.ReadTimeout,),
                resumable_exceptions=HTTPX_DOWNLOAD_EXCEPTIONS,
            )
        except _CancelledDownloadError as exc:
            destination.unlink(missing_ok=True)
            self._partial_download_path(destination).unlink(missing_ok=True)
            raise NetworkError(
                f"Failed to download {url}: download cancelled by user."
            ) from exc
        except KeyboardInterrupt:
            destination.unlink(missing_ok=True)
            self._partial_download_path(destination).unlink(missing_ok=True)
            raise
        except HTTPX_DOWNLOAD_EXCEPTIONS as exc:
            if should_stop is not None and should_stop():
                destination.unlink(missing_ok=True)
                self._partial_download_path(destination).unlink(missing_ok=True)
                raise NetworkError(
                    f"Failed to download {url}: download cancelled by user."
                ) from exc
            raise NetworkError(f"Failed to download {url}: {exc}") from exc

    def _download_with_browser(
        self,
        url: str,
        destination: Path,
        *,
        headers: Mapping[str, str] | None,
        timeout: float,
        progress_callback: Callable[[int], None] | None,
        should_stop: Callable[[], bool] | None,
    ) -> DownloadResult:
        try:
            return self._download_with_resume(
                url,
                destination,
                headers=headers,
                timeout=timeout,
                progress_callback=progress_callback,
                should_stop=should_stop,
                open_stream=lambda request_headers: self._open_browser_download_stream(
                    url,
                    headers=request_headers,
                    timeout=timeout,
                ),
                iter_chunks=lambda response: response.iter_content(
                    chunk_size=DOWNLOAD_CHUNK_SIZE
                ),
                timeout_exceptions=CURL_TIMEOUT_EXCEPTIONS,
                resumable_exceptions=BROWSER_DOWNLOAD_EXCEPTIONS,
            )
        except _CancelledDownloadError as exc:
            destination.unlink(missing_ok=True)
            self._partial_download_path(destination).unlink(missing_ok=True)
            raise NetworkError(
                f"Failed to download {url}: download cancelled by user."
            ) from exc
        except KeyboardInterrupt:
            destination.unlink(missing_ok=True)
            self._partial_download_path(destination).unlink(missing_ok=True)
            raise
        except BROWSER_DOWNLOAD_EXCEPTIONS as exc:
            if should_stop is not None and should_stop():
                destination.unlink(missing_ok=True)
                self._partial_download_path(destination).unlink(missing_ok=True)
                raise NetworkError(
                    f"Failed to download {url}: download cancelled by user."
                ) from exc
            raise NetworkError(f"Failed to download {url}: {exc}") from exc

    @contextmanager
    def _open_browser_download_stream(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: float,
    ) -> Iterator[Any]:
        response: Any | None = None
        try:
            response = self._browser.get(
                url,
                headers=dict(headers),
                timeout=(min(timeout, CONNECT_TIMEOUT_CAP), DOWNLOAD_READ_POLL_TIMEOUT),
                stream=True,
            )
            yield response
        finally:
            if response is not None:
                with suppress(OSError, RuntimeError, ValueError):
                    response.close()

    def _download_with_resume(
        self,
        url: str,
        destination: Path,
        *,
        headers: Mapping[str, str] | None,
        timeout: float,
        progress_callback: Callable[[int], None] | None,
        should_stop: Callable[[], bool] | None,
        open_stream: Callable[[Mapping[str, str]], Any],
        iter_chunks: Callable[[Any], Iterator[bytes]],
        timeout_exceptions: tuple[type[BaseException], ...],
        resumable_exceptions: tuple[type[BaseException], ...],
    ) -> DownloadResult:
        part_path = self._partial_download_path(destination)
        destination.unlink(missing_ok=True)
        part_path.unlink(missing_ok=True)
        last_error: BaseException | None = None

        try:
            for _attempt in range(max(1, self.max_retries + 1)):
                if should_stop is not None and should_stop():
                    raise _CancelledDownloadError()

                resume_offset = self._safe_file_size(part_path)
                request_headers = self._build_download_headers(headers, resume_offset)
                try:
                    with open_stream(request_headers) as response:
                        status_code = int(response.status_code)
                        response_headers = dict(response.headers)
                        response_url = str(response.url)
                        start_offset, file_mode = self._prepare_download_segment(
                            part_path,
                            status_code=status_code,
                            headers=response_headers,
                            resume_offset=resume_offset,
                        )
                        bytes_written = self._stream_to_destination(
                            part_path,
                            url=url,
                            mode=file_mode,
                            iterator=iter_chunks(response),
                            timeout_exceptions=timeout_exceptions,
                            stall_timeout=timeout,
                            progress_callback=progress_callback,
                            should_stop=should_stop,
                        )
                        if not self._is_download_complete(
                            status_code=status_code,
                            headers=response_headers,
                            start_offset=start_offset,
                            bytes_written=bytes_written,
                            part_size=self._safe_file_size(part_path),
                        ):
                            raise NetworkError(
                                "incomplete response body "
                                f"(expected complete file, got {self._safe_file_size(part_path)} bytes)"
                            )

                        part_path.replace(destination)
                        return DownloadResult(
                            path=str(destination),
                            bytes_written=destination.stat().st_size,
                            status_code=status_code,
                            headers=response_headers,
                            url=response_url,
                        )
                except _CancelledDownloadError:
                    raise
                except resumable_exceptions as exc:
                    if should_stop is not None and should_stop():
                        raise _CancelledDownloadError() from exc
                    last_error = exc

            raise NetworkError(
                f"download did not complete after {max(1, self.max_retries + 1)} attempts: {last_error}"
            ) from last_error
        except BaseException:
            destination.unlink(missing_ok=True)
            part_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _partial_download_path(destination: Path) -> Path:
        return destination.with_name(f"{destination.name}.part")

    @staticmethod
    def _safe_file_size(path: Path) -> int:
        try:
            return path.stat().st_size
        except FileNotFoundError:
            return 0

    @staticmethod
    def _build_download_headers(
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

    def _prepare_download_segment(
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

        self._parse_content_range(headers, expected_start=resume_offset)
        return resume_offset, "ab"

    def _stream_to_destination(
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
                    raise _CancelledDownloadError()

                try:
                    chunk = next(iterator)
                except StopIteration:
                    break
                except timeout_exceptions as exc:
                    if should_stop is not None and should_stop():
                        raise _CancelledDownloadError() from exc
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

    def _is_download_complete(
        self,
        *,
        status_code: int,
        headers: Mapping[str, str],
        start_offset: int,
        bytes_written: int,
        part_size: int,
    ) -> bool:
        if status_code == 206:
            range_start, range_end, total_size = self._parse_content_range(
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
    def _parse_content_range(
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

    @staticmethod
    def _should_fallback(response: HttpResponse) -> bool:
        if response.status_code in {403, 429}:
            return True
        content_type = get_header(response.headers, "Content-Type").lower()
        if "text/html" not in content_type:
            return False
        sample = response.content[:4096]
        return any(marker in sample for marker in CHALLENGE_MARKERS)

    @staticmethod
    def _to_response(response: Any) -> HttpResponse:
        headers = {str(key): str(value) for key, value in response.headers.items()}
        content = response.content if hasattr(response, "content") else b""
        url = str(response.url)
        return HttpResponse(
            status_code=int(response.status_code),
            headers=headers,
            content=content,
            url=url,
        )
