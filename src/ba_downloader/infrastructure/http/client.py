from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

import httpx
from curl_cffi import requests as curl_requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.domain.ports.http import DownloadResult, HttpClientPort, HttpResponse


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


class ResilientHttpClient(HttpClientPort):
    def __init__(self, *, proxy_url: str | None = None, max_retries: int = 5) -> None:
        self.proxy_url = proxy_url
        self.max_retries = max_retries
        self._httpx = httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            proxy=proxy_url,
        )
        self._browser = curl_requests.Session(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            impersonate="chrome",
        )
        if proxy_url:
            self._browser.proxies = {"http": proxy_url, "https": proxy_url}

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: Mapping[str, Any] | None = None,
        transport: str = "default",
        timeout: float = 10.0,
    ) -> HttpResponse:
        method = method.upper()

        if transport == "browser":
            response = self._request_with_browser(
                method,
                url,
                headers=headers,
                json=json,
                data=data,
                params=params,
                timeout=timeout,
            )
            return self._to_response(response)

        response = self._request_with_httpx(
            method,
            url,
            headers=headers,
            json=json,
            data=data,
            params=params,
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
                params=params,
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
        transport: str = "default",
        timeout: float = 30.0,
        progress_callback: Callable[[int], None] | None = None,
    ) -> DownloadResult:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        if transport == "browser":
            return self._download_with_browser(
                url,
                destination_path,
                headers=headers,
                timeout=timeout,
                progress_callback=progress_callback,
            )

        result = self._download_with_httpx(
            url,
            destination_path,
            headers=headers,
            timeout=timeout,
            progress_callback=progress_callback,
        )
        if result.status_code in {403, 429} or (
            "text/html" in result.headers.get("Content-Type", "").lower()
            and destination_path.read_bytes()[:4096].find(b"Cloudflare") != -1
        ):
            destination_path.unlink(missing_ok=True)
            return self._download_with_browser(
                url,
                destination_path,
                headers=headers,
                timeout=timeout,
                progress_callback=progress_callback,
            )
        return result

    def _request_with_httpx(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        json: Any | None,
        data: Any | None,
        params: Mapping[str, Any] | None,
        timeout: float,
    ) -> httpx.Response:
        retrying = Retrying(
            stop=stop_after_attempt(max(1, self.max_retries + 1)),
            wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
            retry=retry_if_exception_type(
                (httpx.HTTPError, httpx.TimeoutException, OSError)
            ),
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
        except Exception as exc:
            raise NetworkError(f"Failed to fetch {url}: {exc}") from exc
        raise NetworkError(f"Failed to fetch {url}: unexpected retry state.")

    def _request_with_browser(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        json: Any | None,
        data: Any | None,
        params: Mapping[str, Any] | None,
        timeout: float,
    ):
        retrying = Retrying(
            stop=stop_after_attempt(max(1, self.max_retries + 1)),
            wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
            retry=retry_if_exception_type(Exception),
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
        except Exception as exc:
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
    ) -> DownloadResult:
        try:
            with self._httpx.stream(
                "GET",
                url,
                headers=headers,
                timeout=timeout,
            ) as response:
                with destination.open("wb") as file_handle:
                    total = 0
                    for chunk in response.iter_bytes():
                        if not chunk:
                            continue
                        file_handle.write(chunk)
                        total += len(chunk)
                        if progress_callback is not None:
                            progress_callback(len(chunk))
            return DownloadResult(
                path=str(destination),
                bytes_written=destination.stat().st_size if destination.exists() else 0,
                status_code=response.status_code,
                headers=dict(response.headers),
                url=str(response.url),
            )
        except Exception as exc:
            raise NetworkError(f"Failed to download {url}: {exc}") from exc

    def _download_with_browser(
        self,
        url: str,
        destination: Path,
        *,
        headers: Mapping[str, str] | None,
        timeout: float,
        progress_callback: Callable[[int], None] | None,
    ) -> DownloadResult:
        try:
            response = self._browser.get(
                url,
                headers=dict(headers or {}),
                timeout=timeout,
                stream=True,
            )
            with destination.open("wb") as file_handle:
                total = 0
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    file_handle.write(chunk)
                    total += len(chunk)
                    if progress_callback is not None:
                        progress_callback(len(chunk))
            return DownloadResult(
                path=str(destination),
                bytes_written=destination.stat().st_size if destination.exists() else 0,
                status_code=response.status_code,
                headers=dict(response.headers),
                url=response.url,
            )
        except Exception as exc:
            raise NetworkError(f"Failed to download {url}: {exc}") from exc

    @staticmethod
    def _should_fallback(response: HttpResponse) -> bool:
        if response.status_code in {403, 429}:
            return True
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            return False
        sample = response.content[:4096]
        return any(marker in sample for marker in CHALLENGE_MARKERS)

    @staticmethod
    def _to_response(response: Any) -> HttpResponse:
        headers = {str(key): str(value) for key, value in response.headers.items()}
        content = response.content if hasattr(response, "content") else bytes()
        url = str(response.url)
        return HttpResponse(
            status_code=int(response.status_code),
            headers=headers,
            content=content,
            url=url,
        )
