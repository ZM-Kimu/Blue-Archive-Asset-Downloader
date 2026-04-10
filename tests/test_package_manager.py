from __future__ import annotations

import re
from io import BytesIO
from base64 import b64encode
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlencode
from zipfile import ZipFile

import pytest

import ba_downloader.infrastructure.apk.package_manager as package_manager
from ba_downloader.domain.ports.http import DownloadResult, HttpResponse
from ba_downloader.infrastructure.apk.package_manager import (
    PackageArchiveError,
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
        timeout: float = 300.0,
        progress_callback: Any = None,
        should_stop: Any = None,
    ) -> DownloadResult:
        _ = (url, headers, transport, timeout, progress_callback, should_stop)
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

    def close(self) -> None:
        return None


class MultipartRecordingHttpClient:
    def __init__(
        self,
        *,
        head_response: HttpResponse,
        package_bytes: bytes,
        fallback_payload: bytes | None = None,
        probe_status_code: int = 206,
        probe_content_range: str | None = None,
        part_failures: dict[tuple[int, int], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.head_response = head_response
        self.package_bytes = package_bytes
        self.fallback_payload = fallback_payload or package_bytes
        self.probe_status_code = probe_status_code
        self.probe_content_range = probe_content_range
        self.part_failures = {
            key: list(value) for key, value in (part_failures or {}).items()
        }
        self.download_calls = 0
        self.destinations: list[str] = []
        self.range_calls: list[tuple[int, int]] = []
        self.range_attempts: dict[tuple[int, int], int] = defaultdict(int)
        self._lock = Lock()

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
        _ = (json, data, params, transport, timeout)
        if method == "HEAD":
            return self.head_response

        range_header = dict(headers or {}).get("Range", "")
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", range_header)
        assert match is not None
        start = int(match.group(1))
        end = int(match.group(2))

        with self._lock:
            self.range_calls.append((start, end))
            self.range_attempts[(start, end)] += 1
            scripted_failures = self.part_failures.get((start, end), [])
            scripted_response = scripted_failures.pop(0) if scripted_failures else None

        if start == 0 and end == 0 and self.probe_status_code != 206:
            return HttpResponse(
                status_code=self.probe_status_code,
                headers={},
                content=self.package_bytes[:1],
                url=url,
            )

        if start == 0 and end == 0 and self.probe_content_range is not None:
            return HttpResponse(
                status_code=206,
                headers={"Content-Range": self.probe_content_range},
                content=self.package_bytes[:1],
                url=url,
            )

        if scripted_response is not None:
            headers_out = scripted_response.get("headers")
            if headers_out is None:
                range_start = int(scripted_response.get("start", start))
                range_end = int(scripted_response.get("end", end))
                total = int(scripted_response.get("total", len(self.package_bytes)))
                headers_out = {
                    "Content-Range": f"bytes {range_start}-{range_end}/{total}"
                }
            return HttpResponse(
                status_code=int(scripted_response.get("status_code", 206)),
                headers=headers_out,
                content=scripted_response.get(
                    "content",
                    self.package_bytes[start : end + 1],
                ),
                url=url,
            )

        return HttpResponse(
            status_code=206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(self.package_bytes)}"},
            content=self.package_bytes[start : end + 1],
            url=url,
        )

    def download_to_file(
        self,
        url: str,
        destination: str,
        *,
        headers: dict[str, str] | None = None,
        transport: str = "default",
        timeout: float = 300.0,
        progress_callback: Any = None,
        should_stop: Any = None,
    ) -> DownloadResult:
        _ = (url, headers, transport, timeout, progress_callback, should_stop)
        self.download_calls += 1
        self.destinations.append(destination)
        destination_path = Path(destination)
        destination_path.write_bytes(self.fallback_payload)
        return DownloadResult(
            path=str(destination_path),
            bytes_written=len(self.fallback_payload),
            status_code=200,
            headers={},
            url=self.head_response.url,
        )

    def close(self) -> None:
        return None


def _build_zip_bytes(file_name: str = "base.apk", payload: bytes = b"apk") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(file_name, payload)
    return buffer.getvalue()


def _configure_multipart_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_manager, "MULTIPART_MIN_PACKAGE_BYTES", 1)
    monkeypatch.setattr(package_manager, "MULTIPART_PART_BYTES", 16)
    monkeypatch.setattr(package_manager, "MULTIPART_MAX_WORKERS", 2)


def _expected_ranges(total_size: int, part_size: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for start in range(0, total_size, part_size):
        end = min(total_size - 1, start + part_size - 1)
        ranges.append((start, end))
    return ranges


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
    cached_payload = _build_zip_bytes()
    destination.write_bytes(cached_payload)
    client = RecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": str(len(cached_payload))},
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
    payload = _build_zip_bytes()
    encoded_context = b64encode(
        f"dev=Yostar&t=xapk&s={len(payload)}&vn=1.66.405117".encode("utf-8")
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
        download_payload=payload,
    )

    result = download_package_file(
        client,
        NullLogger(),
        package_url,
        str(tmp_path),
    )

    assert Path(result).name == "BlueArchive_v1.66.405117.xapk"
    assert Path(result).stat().st_size == len(payload)
    assert client.destinations == [str(tmp_path / "BlueArchive_v1.66.405117.xapk")]


def test_download_package_file_removes_incomplete_package_when_size_mismatches(
    tmp_path: Path,
) -> None:
    package_url = "https://download.example.com/archive.xapk"
    client = RecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": "9"},
            content=b"",
            url=package_url,
        ),
        download_payload=b"short",
    )

    with pytest.raises(PackageArchiveError, match="Expected size: 9 bytes"):
        download_package_file(
            client,
            NullLogger(),
            package_url,
            str(tmp_path),
        )

    assert not (tmp_path / "archive.xapk").exists()


def test_download_package_file_removes_non_zip_package_and_reports_signature(
    tmp_path: Path,
) -> None:
    package_url = "https://download.example.com/archive.xapk"
    client = RecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": "8"},
            content=b"",
            url=package_url,
        ),
        download_payload=b"notazip!",
    )

    with pytest.raises(PackageArchiveError, match="Signature: 6e 6f 74 61 7a 69 70 21"):
        download_package_file(
            client,
            NullLogger(),
            package_url,
            str(tmp_path),
        )

    assert not (tmp_path / "archive.xapk").exists()


def test_download_package_file_accepts_valid_zip_archive(tmp_path: Path) -> None:
    package_url = "https://download.example.com/archive.xapk"
    payload = _build_zip_bytes()
    client = RecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": str(len(payload))},
            content=b"",
            url=package_url,
        ),
        download_payload=payload,
    )

    result = download_package_file(
        client,
        NullLogger(),
        package_url,
        str(tmp_path),
    )

    assert result == str(tmp_path / "archive.xapk")
    assert Path(result).read_bytes() == payload


def test_download_package_file_uses_multipart_range_requests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_multipart_for_tests(monkeypatch)
    payload = _build_zip_bytes(payload=b"a" * 64)
    package_url = "https://download.example.com/archive.xapk"
    client = MultipartRecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": str(len(payload))},
            content=b"",
            url=package_url,
        ),
        package_bytes=payload,
    )

    result = download_package_file(
        client,
        NullLogger(),
        package_url,
        str(tmp_path),
    )

    expected_ranges = _expected_ranges(len(payload), package_manager.MULTIPART_PART_BYTES)
    assert Path(result).read_bytes() == payload
    assert client.download_calls == 0
    assert client.range_calls[0] == (0, 0)
    assert sorted(client.range_calls[1:]) == expected_ranges
    assert not Path(result).with_name(f"{Path(result).name}.parts").exists()


def test_download_package_file_retries_only_failed_part(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_multipart_for_tests(monkeypatch)
    payload = _build_zip_bytes(payload=b"b" * 64)
    package_url = "https://download.example.com/archive.xapk"
    expected_ranges = _expected_ranges(len(payload), package_manager.MULTIPART_PART_BYTES)
    failed_range = expected_ranges[1]
    client = MultipartRecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": str(len(payload))},
            content=b"",
            url=package_url,
        ),
        package_bytes=payload,
        part_failures={
            failed_range: [
                {
                    "content": payload[failed_range[0] : failed_range[1]],
                }
            ]
        },
    )

    result = download_package_file(
        client,
        NullLogger(),
        package_url,
        str(tmp_path),
    )

    assert Path(result).read_bytes() == payload
    assert client.range_attempts[failed_range] == 2
    for byte_range in expected_ranges:
        if byte_range == failed_range:
            continue
        assert client.range_attempts[byte_range] == 1


def test_download_package_file_falls_back_when_range_probe_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_multipart_for_tests(monkeypatch)
    payload = _build_zip_bytes(payload=b"c" * 64)
    package_url = "https://download.example.com/archive.xapk"
    client = MultipartRecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": str(len(payload))},
            content=b"",
            url=package_url,
        ),
        package_bytes=payload,
        probe_content_range="bytes 0-1/999",
    )

    result = download_package_file(
        client,
        NullLogger(),
        package_url,
        str(tmp_path),
    )

    assert Path(result).read_bytes() == payload
    assert client.download_calls == 1
    assert client.range_calls == [(0, 0)]


def test_download_package_file_falls_back_when_package_size_is_unknown(
    tmp_path: Path,
) -> None:
    package_url = "https://download.example.com/archive.xapk"
    payload = _build_zip_bytes(payload=b"d" * 64)
    client = RecordingHttpClient(
        head_response=HttpResponse(
            status_code=405,
            headers={},
            content=b"",
            url=package_url,
        ),
        download_payload=payload,
    )

    result = download_package_file(
        client,
        NullLogger(),
        package_url,
        str(tmp_path),
    )

    assert Path(result).read_bytes() == payload
    assert client.download_calls == 1


def test_download_package_file_removes_invalid_multipart_package_and_cleans_parts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_multipart_for_tests(monkeypatch)
    package_url = "https://download.example.com/archive.xapk"
    payload = b"not a valid archive payload"
    client = MultipartRecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": str(len(payload))},
            content=b"",
            url=package_url,
        ),
        package_bytes=payload,
    )
    destination = tmp_path / "archive.xapk"

    with pytest.raises(PackageArchiveError, match="not a valid ZIP/XAPK archive"):
        download_package_file(
            client,
            NullLogger(),
            package_url,
            str(tmp_path),
        )

    assert not destination.exists()
    assert not destination.with_name(f"{destination.name}.parts").exists()


def test_download_package_file_replaces_invalid_cached_package(tmp_path: Path) -> None:
    package_url = "https://download.example.com/archive.xapk"
    payload = _build_zip_bytes(payload=b"good")
    destination = tmp_path / "archive.xapk"
    destination.write_bytes(b"x" * len(payload))
    client = RecordingHttpClient(
        head_response=HttpResponse(
            status_code=200,
            headers={"Content-Length": str(len(payload))},
            content=b"",
            url=package_url,
        ),
        download_payload=payload,
    )

    result = download_package_file(
        client,
        NullLogger(),
        package_url,
        str(tmp_path),
    )

    assert result == str(destination)
    assert client.download_calls == 1
    assert destination.read_bytes() == payload
