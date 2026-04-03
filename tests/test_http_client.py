from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from collections.abc import Iterator

import httpx
import pytest

from ba_downloader.domain.exceptions import NetworkError
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


def test_http_client_download_falls_back_to_browser(monkeypatch, tmp_path: Path) -> None:
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

    result = client.download_to_file("https://example.com/archive.xapk", str(destination))

    assert result.status_code == 200
    assert destination.read_bytes() == b"binary"


def test_http_client_download_uses_updated_default_timeout(monkeypatch, tmp_path: Path) -> None:
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

    result = client.download_to_file("https://example.com/archive.bin", str(destination))

    assert result.status_code == 200
    assert captured["timeout"] == DEFAULT_DOWNLOAD_TIMEOUT == 600.0


class FakeHttpxResponse:
    def __init__(self, chunks: list[bytes | Exception]) -> None:
        self._chunks = list(chunks)
        self.status_code = 200
        self.headers = {"Content-Type": "application/octet-stream"}
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
    def __init__(self, response: FakeHttpxResponse) -> None:
        self.response = response
        self.stream_calls: list[dict[str, object]] = []

    def stream(self, *args, **kwargs) -> FakeStreamContext:
        self.stream_calls.append(kwargs)
        return FakeStreamContext(self.response)

    def close(self) -> None:
        return None


def test_http_client_download_tolerates_short_read_timeouts(monkeypatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr("ba_downloader.infrastructure.http.client.monotonic", lambda: next(time_points))

    result = client.download_to_file("https://example.com/archive.bin", str(destination))

    assert result.bytes_written == 6
    assert destination.read_bytes() == b"abcdef"
    timeout_config = fake_httpx.stream_calls[0]["timeout"]
    assert timeout_config.read == DOWNLOAD_READ_POLL_TIMEOUT


def test_http_client_download_cleans_partial_file_on_cancel(monkeypatch, tmp_path: Path) -> None:
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


def test_http_client_download_fails_after_stall_timeout(monkeypatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr("ba_downloader.infrastructure.http.client.monotonic", lambda: next(time_points))

    with pytest.raises(NetworkError, match="read operation timed out"):
        client.download_to_file("https://example.com/archive.bin", str(destination))
