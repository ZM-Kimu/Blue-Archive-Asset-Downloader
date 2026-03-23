from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from threading import Event
from typing import Any

from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.download.resource_downloader import ResourceDownloader
from ba_downloader.infrastructure.logging.console_logger import NullLogger


class RecordingHttpClient:
    def __init__(self) -> None:
        self.download_calls: list[dict[str, Any]] = []
        self.closed = 0

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
    ) -> Any:
        _ = (headers, transport)
        self.download_calls.append(
            {
                "url": url,
                "destination": destination,
                "timeout": timeout,
                "should_stop": should_stop,
            }
        )
        if progress_callback is not None:
            progress_callback(4)
            progress_callback(6)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(b"x" * 10)
        return {"path": destination}

    def close(self) -> None:
        self.closed += 1


class RecordingProgressReporter:
    instances: list["RecordingProgressReporter"] = []

    def __init__(self, total: int, description: str, *, download_mode: bool = False) -> None:
        self.total = total
        self.description = description
        self.download_mode = download_mode
        self.advances: list[int] = []
        self.descriptions: list[str] = [description]
        RecordingProgressReporter.instances.append(self)

    def __enter__(self) -> "RecordingProgressReporter":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def advance(self, amount: int = 1) -> None:
        self.advances.append(amount)

    def set_total(self, total: int) -> None:
        self.total = total

    def set_description(self, description: str) -> None:
        self.description = description
        self.descriptions.append(description)

    def set_completed(self, completed: int) -> None:
        _ = completed

    def stop(self) -> None:
        return None


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=2,
        version="1.0.0",
        raw_dir=str(tmp_path / "raw"),
        extract_dir=str(tmp_path / "extract"),
        temp_dir=str(tmp_path / "temp"),
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def test_download_resources_tracks_aggregate_bytes(monkeypatch, tmp_path: Path) -> None:
    client = RecordingHttpClient()
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    RecordingProgressReporter.instances.clear()
    resources = AssetCollection()
    resources.add(
        "https://example.com/a.bundle",
        "Bundle/a.bundle",
        10,
        "crc-a",
        "crc",
        AssetType.bundle,
    )
    resources.add(
        "https://example.com/b.bundle",
        "Bundle/b.bundle",
        10,
        "crc-b",
        "crc",
        AssetType.bundle,
    )

    monkeypatch.setattr(
        "ba_downloader.infrastructure.download.resource_downloader.RichProgressReporter",
        RecordingProgressReporter,
    )
    monkeypatch.setattr(downloader, "_install_interrupt_handler", lambda stop_event: nullcontext())

    failed = downloader._download_resources(list(resources), context)

    progress = RecordingProgressReporter.instances[-1]
    assert failed == []
    assert progress.download_mode is True
    assert progress.total == 20
    assert sum(progress.advances) == 20
    assert progress.descriptions[-1] == "Downloading assets (2/2 files)"
    assert client.download_calls
    assert client.download_calls[0]["timeout"] == downloader.DOWNLOAD_TIMEOUT_SECONDS
    assert callable(client.download_calls[0]["should_stop"])


def test_handle_interrupt_closes_client_and_force_exits_on_second_interrupt(tmp_path: Path) -> None:
    client = RecordingHttpClient()
    exit_codes: list[int] = []
    downloader = ResourceDownloader(client, NullLogger(), force_exit=exit_codes.append)
    stop_event = Event()

    downloader._handle_interrupt(stop_event, 1)
    assert stop_event.is_set()
    assert client.closed == 1
    downloader._handle_interrupt(stop_event, 2)
    assert client.closed == 2
    assert exit_codes == [130]
