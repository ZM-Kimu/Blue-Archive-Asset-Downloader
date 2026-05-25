from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.infrastructure.http import client as http_client_module
from ba_downloader.infrastructure.http.client import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DOWNLOAD_READ_POLL_TIMEOUT,
    ResilientHttpClient,
)


def test_http_client_falls_back_to_browser_for_blocked_responses(monkeypatch) -> None:
    client = ResilientHttpClient(max_retries=0)

    def fake_httpx(*args, **kwargs):
        request = httpx.Request("GET", "https://example.com")
        return httpx.Response(403, request=request, content=b"blocked")

    def fake_browser(*args, **kwargs):
        return SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "application/json"},
            content=b'{"ok": true}',
            url="https://example.com",
        )

    monkeypatch.setattr(client, "_request_with_httpx", fake_httpx)
    monkeypatch.setattr(client, "_request_with_browser", fake_browser)

    response = client.request("GET", "https://example.com")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_http_client_download_falls_back_to_browser(
    monkeypatch, tmp_path: Path
) -> None:
    client = ResilientHttpClient(max_retries=0)
    destination = tmp_path / "archive.xapk"

    def fake_download_with_httpx(*args, **kwargs):
        destination.write_text("Cloudflare", encoding="utf-8")
        return SimpleNamespace(
            path=str(destination),
            bytes_written=destination.stat().st_size,
            status_code=403,
            headers={"Content-Type": "text/html"},
            url="https://example.com/archive.xapk",
        )

    def fake_download_with_browser(*args, **kwargs):
        destination.write_bytes(b"binary")
        return SimpleNamespace(
            path=str(destination),
            bytes_written=destination.stat().st_size,
            status_code=200,
            headers={"Content-Type": "application/octet-stream"},
            url="https://example.com/archive.xapk",
        )

    monkeypatch.setattr(client, "_download_with_httpx", fake_download_with_httpx)
    monkeypatch.setattr(client, "_download_with_browser", fake_download_with_browser)

    result = client.download_to_file(
        "https://example.com/archive.xapk", str(destination)
    )

    assert result.status_code == 200
    assert destination.read_bytes() == b"binary"


def test_http_client_download_uses_updated_default_timeout(
    monkeypatch, tmp_path: Path
) -> None:
    client = ResilientHttpClient(max_retries=0)
    destination = tmp_path / "archive.bin"
    captured: dict[str, float] = {}

    def fake_download_with_httpx(*args, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        destination.write_bytes(b"binary")
        return SimpleNamespace(
            path=str(destination),
            bytes_written=destination.stat().st_size,
            status_code=200,
            headers={"Content-Type": "application/octet-stream"},
            url="https://example.com/archive.bin",
        )

    monkeypatch.setattr(client, "_download_with_httpx", fake_download_with_httpx)

    result = client.download_to_file(
        "https://example.com/archive.bin", str(destination)
    )

    assert result.status_code == 200
    assert captured["timeout"] == DEFAULT_DOWNLOAD_TIMEOUT == 600.0


def test_http_client_browser_request_does_not_retry_programming_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ResilientHttpClient(max_retries=3)
    attempts = {"count": 0}

    def fake_browser_request(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        attempts["count"] += 1
        raise ValueError("bad serialization")

    monkeypatch.setattr(client._browser, "request", fake_browser_request)

    with pytest.raises(ValueError, match="bad serialization"):
        client._request_with_browser(
            "GET",
            "https://example.com",
            headers=None,
            json=None,
            data=None,
            params=None,
            timeout=5.0,
        )

    assert attempts["count"] == 1


def test_http_resume_state_machine_is_separated_from_client() -> None:
    assert hasattr(http_client_module, "DownloadResumeSession")
    concentrated_methods = {
        "_download_with_resume",
        "_prepare_download_segment",
        "_is_download_complete",
        "_parse_content_range",
    }

    assert not concentrated_methods.intersection(ResilientHttpClient.__dict__)


class FakeHttpxResponse:
    def __init__(
        self,
        chunks: list[bytes | Exception],
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/octet-stream"}
        self.url = "https://example.com/archive.xapk"

    def iter_bytes(self, chunk_size: int | None = None) -> Iterator[bytes]:
        _ = chunk_size
        return _ChunkIterator(self._chunks)


class _ChunkIterator:
    def __init__(self, chunks: list[bytes | Exception]) -> None:
        self._chunks = list(chunks)
        self._index = 0

    def __iter__(self) -> _ChunkIterator:
        return self

    def __next__(self) -> bytes:
        if self._index >= len(self._chunks):
            raise StopIteration
        chunk = self._chunks[self._index]
        self._index += 1
        if isinstance(chunk, Exception):
            raise chunk
        return chunk


class FakeStreamContext:
    def __init__(self, response: FakeHttpxResponse) -> None:
        self.response = response

    def __enter__(self) -> FakeHttpxResponse:
        return self.response

    def __exit__(self, *_: object) -> None:
        return None


class FakeHttpxClient:
    def __init__(self, response: FakeHttpxResponse | list[FakeHttpxResponse]) -> None:
        self.responses = list(response if isinstance(response, list) else [response])
        self.stream_calls: list[dict[str, object]] = []

    def stream(self, *args, **kwargs) -> FakeStreamContext:
        _ = args
        self.stream_calls.append(kwargs)
        return FakeStreamContext(self.responses.pop(0))

    def close(self) -> None:
        return None


class FakeBrowserResponse:
    def __init__(
        self,
        chunks: list[bytes | Exception],
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/octet-stream"}
        self.url = "https://example.com/archive.xapk"
        self.closed = False

    def iter_content(self, chunk_size: int | None = None) -> Iterator[bytes]:
        _ = chunk_size
        return _ChunkIterator(self._chunks)

    def close(self) -> None:
        self.closed = True


class FakeBrowserSession:
    def __init__(self, responses: list[FakeBrowserResponse]) -> None:
        self.responses = list(responses)
        self.get_calls: list[dict[str, object]] = []

    def get(self, *args, **kwargs) -> FakeBrowserResponse:
        _ = args
        self.get_calls.append(kwargs)
        return self.responses.pop(0)

    def close(self) -> None:
        return None


def test_http_client_download_tolerates_short_read_timeouts(
    monkeypatch, tmp_path: Path
) -> None:
    client = ResilientHttpClient(max_retries=0)
    destination = tmp_path / "archive.bin"
    response = FakeHttpxResponse(
        [
            httpx.ReadTimeout("slow"),
            b"abc",
            httpx.ReadTimeout("slow"),
            b"def",
        ]
    )
    fake_httpx = FakeHttpxClient(response)
    time_points = iter([0.0, 0.5, 0.6, 1.1, 1.2, 1.6])

    monkeypatch.setattr(client, "_httpx", fake_httpx)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.http.resume.monotonic", lambda: next(time_points)
    )

    result = client.download_to_file(
        "https://example.com/archive.bin", str(destination)
    )

    assert result.bytes_written == 6
    assert destination.read_bytes() == b"abcdef"
    timeout_config = fake_httpx.stream_calls[0]["timeout"]
    assert timeout_config.read == DOWNLOAD_READ_POLL_TIMEOUT


def test_http_client_download_cleans_partial_file_on_cancel(
    monkeypatch, tmp_path: Path
) -> None:
    client = ResilientHttpClient(max_retries=0)
    destination = tmp_path / "archive.bin"
    response = FakeHttpxResponse([b"abc", b"def"])
    fake_httpx = FakeHttpxClient(response)
    should_stop_state = {"value": False}

    def progress_callback(amount: int) -> None:
        _ = amount
        should_stop_state["value"] = True

    monkeypatch.setattr(client, "_httpx", fake_httpx)

    with pytest.raises(NetworkError, match="cancelled by user"):
        client.download_to_file(
            "https://example.com/archive.bin",
            str(destination),
            progress_callback=progress_callback,
            should_stop=lambda: should_stop_state["value"],
        )

    assert not destination.exists()
    assert not destination.with_name("archive.bin.part").exists()


def test_http_client_download_rejects_short_response_body(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = ResilientHttpClient(max_retries=0)
    destination = tmp_path / "archive.bin"
    response = FakeHttpxResponse(
        [b"abc"],
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": "10",
        },
    )
    fake_httpx = FakeHttpxClient(response)

    monkeypatch.setattr(client, "_httpx", fake_httpx)

    with pytest.raises(NetworkError, match="incomplete response body"):
        client.download_to_file("https://example.com/archive.bin", str(destination))

    assert not destination.exists()


def test_http_client_download_resumes_incomplete_full_response(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = ResilientHttpClient(max_retries=1)
    destination = tmp_path / "archive.bin"
    fake_httpx = FakeHttpxClient(
        [
            FakeHttpxResponse(
                [b"abc"],
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "6",
                },
            ),
            FakeHttpxResponse(
                [b"def"],
                status_code=206,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "3",
                    "Content-Range": "bytes 3-5/6",
                },
            ),
        ]
    )

    monkeypatch.setattr(client, "_httpx", fake_httpx)

    result = client.download_to_file("https://example.com/archive.bin", str(destination))

    assert result.bytes_written == 6
    assert destination.read_bytes() == b"abcdef"
    assert not destination.with_name("archive.bin.part").exists()
    assert fake_httpx.stream_calls[0]["headers"]["Accept-Encoding"] == "identity"
    assert "Range" not in fake_httpx.stream_calls[0]["headers"]
    assert fake_httpx.stream_calls[1]["headers"]["Range"] == "bytes=3-"


def test_http_client_browser_download_uses_same_range_resume(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = ResilientHttpClient(max_retries=1)
    destination = tmp_path / "archive.bin"
    fake_browser = FakeBrowserSession(
        [
            FakeBrowserResponse(
                [b"abc"],
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "6",
                },
            ),
            FakeBrowserResponse(
                [b"def"],
                status_code=206,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "3",
                    "Content-Range": "bytes 3-5/6",
                },
            ),
        ]
    )

    monkeypatch.setattr(client, "_browser", fake_browser)

    result = client.download_to_file(
        "https://example.com/archive.bin",
        str(destination),
        transport="browser",
    )

    assert result.bytes_written == 6
    assert destination.read_bytes() == b"abcdef"
    assert fake_browser.get_calls[1]["headers"]["Range"] == "bytes=3-"


def test_http_client_download_restarts_when_range_is_ignored(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = ResilientHttpClient(max_retries=2)
    destination = tmp_path / "archive.bin"
    fake_httpx = FakeHttpxClient(
        [
            FakeHttpxResponse(
                [b"abc"],
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "6",
                },
            ),
            FakeHttpxResponse(
                [b"abcdef"],
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "6",
                },
            ),
        ]
    )

    monkeypatch.setattr(client, "_httpx", fake_httpx)

    result = client.download_to_file("https://example.com/archive.bin", str(destination))

    assert result.bytes_written == 6
    assert destination.read_bytes() == b"abcdef"
    assert not destination.with_name("archive.bin.part").exists()
    assert fake_httpx.stream_calls[1]["headers"]["Range"] == "bytes=3-"


@pytest.mark.parametrize(
    ("status_code", "headers", "chunks", "match"),
    [
        (
            206,
            {"Content-Length": "3"},
            [b"def"],
            "Missing or invalid Content-Range",
        ),
        (
            206,
            {
                "Content-Length": "3",
                "Content-Range": "bytes 4-6/7",
            },
            [b"def"],
            "Unexpected Content-Range",
        ),
        (
            206,
            {
                "Content-Length": "3",
                "Content-Range": "bytes 3-5/6",
            },
            [b"de"],
            "incomplete response body",
        ),
        (
            416,
            {"Content-Length": "0"},
            [],
            "unexpected HTTP status 416",
        ),
    ],
)
def test_http_client_download_rejects_invalid_range_resume(
    monkeypatch,
    tmp_path: Path,
    status_code: int,
    headers: dict[str, str],
    chunks: list[bytes],
    match: str,
) -> None:
    client = ResilientHttpClient(max_retries=1)
    destination = tmp_path / "archive.bin"
    fake_httpx = FakeHttpxClient(
        [
            FakeHttpxResponse(
                [b"abc"],
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "6",
                },
            ),
            FakeHttpxResponse(
                chunks,
                status_code=status_code,
                headers={
                    "Content-Type": "application/octet-stream",
                    **headers,
                },
            ),
        ]
    )

    monkeypatch.setattr(client, "_httpx", fake_httpx)

    with pytest.raises(NetworkError, match=match):
        client.download_to_file("https://example.com/archive.bin", str(destination))

    assert not destination.exists()
    assert not destination.with_name("archive.bin.part").exists()


def test_http_client_download_fails_after_stall_timeout(
    monkeypatch, tmp_path: Path
) -> None:
    client = ResilientHttpClient(max_retries=0)
    destination = tmp_path / "archive.bin"
    response = FakeHttpxResponse(
        [
            httpx.ReadTimeout("slow"),
            httpx.ReadTimeout("slow"),
            httpx.ReadTimeout("slow"),
        ]
    )
    fake_httpx = FakeHttpxClient(response)
    time_points = iter([0.0, 0.0, 300.0, 601.0])

    monkeypatch.setattr(client, "_httpx", fake_httpx)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.http.resume.monotonic", lambda: next(time_points)
    )

    with pytest.raises(NetworkError, match="read operation timed out"):
        client.download_to_file("https://example.com/archive.bin", str(destination))
