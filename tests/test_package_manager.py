from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ba_downloader.domain.ports.http import DownloadResult, HttpResponse
from ba_downloader.infrastructure.apk.package_manager import (
    _resolve_filename,
    download_package_file,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger


class RecordingHttpClient:
    def __init__(
        self,
        *,
        head_response: HttpResponse,
        download_payload: bytes = b"",
        download_url: str | None = None,
    ) -> None:
        self.head_response = head_response
        self.download_payload = download_payload
        self.download_url = download_url or head_response.url
        self.download_calls = 0
        self.destinations: list[str] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: dict[str, Any] | None = None,
        transport: str = "default",
        timeout: float = 10.0,
    ) -> HttpResponse:
        _ = (url, headers, json, data, params, transport, timeout)
        assert method == "HEAD"
        return self.head_response

    def download_to_file(
        self,
        url: str,
        destination: str,
        *,
        headers: dict[str, str] | None = None,
        transport: str = "default",
        timeout: float = 30.0,
        progress_callback: Any = None,
    ) -> DownloadResult:
        _ = (url, headers, transport, timeout, progress_callback)
        self.download_calls += 1
        self.destinations.append(destination)
        destination_path = Path(destination)
        destination_path.write_bytes(self.download_payload)
        return DownloadResult(
            path=str(destination_path),
            bytes_written=len(self.download_payload),
            status_code=200,
            headers={},
            url=self.download_url,
        )


def test_resolve_filename_prefers_pureapk_fn_query() -> None:
    encoded_name = b64encode(b"BlueArchive_v1.66.405117.xapk").decode("ascii").rstrip("=")

    file_name = _resolve_filename(
        "",
        f"https://download.pureapk.com/b/XAPK/token?_fn={encoded_name}",
    )

    assert file_name == "BlueArchive_v1.66.405117.xapk"


def test_download_package_file_uses_redirected_head_url_for_cached_file(
    tmp_path: Path,
) -> None:
    final_url = "https://cdn.example.com/files/blue-archive-real.xapk"
    destination = tmp_path / "blue-archive-real.xapk"
    destination.write_bytes(b"12345")
    client = RecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": "5"},
            content=b"",
            url=final_url,
        ),
    )

    result = download_package_file(
        client,
        NullLogger(),
        "https://download.example.com/archive?id=123",
        str(tmp_path),
    )

    assert result == str(destination)
    assert client.download_calls == 0


def test_download_package_file_falls_back_to_pureapk_query_metadata(
    tmp_path: Path,
) -> None:
    encoded_name = b64encode(b"BlueArchive_v1.66.405117.xapk").decode("ascii").rstrip("=")
    encoded_context = b64encode(
        b"dev=Yostar&t=xapk&s=7&vn=1.66.405117"
    ).decode("ascii").rstrip("=")
    package_url = "https://download.pureapk.com/b/XAPK/token?" + urlencode(
        {
            "_fn": encoded_name,
            "c": f"2|GAME_ROLE_PLAYING|{encoded_context}",
        }
    )
    client = RecordingHttpClient(
        head_response=HttpResponse(
            status_code=405,
            headers={"Content-Length": "19"},
            content=b"Method Not Allowed",
            url=package_url,
        ),
        download_payload=b"1234567",
    )

    result = download_package_file(
        client,
        NullLogger(),
        package_url,
        str(tmp_path),
    )

    assert Path(result).name == "BlueArchive_v1.66.405117.xapk"
    assert Path(result).stat().st_size == 7
    assert client.destinations == [str(tmp_path / "BlueArchive_v1.66.405117.xapk")]
