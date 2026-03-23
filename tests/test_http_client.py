from pathlib import Path
from types import SimpleNamespace

import httpx

from ba_downloader.infrastructure.http.client import ResilientHttpClient


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
