from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extract.asset_workflow import AssetExtractionWorkflow


class RecordingLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warn_messages: list[str] = []
        self.error_messages: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def warn(self, message: str) -> None:
        self.warn_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)


class DummyProgressReporter:
    def __init__(self, total: int, description: str, *, download_mode: bool = False) -> None:
        _ = (total, description, download_mode)

    def __enter__(self) -> DummyProgressReporter:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def set_completed(self, completed: int) -> None:
        _ = completed

    def set_description(self, description: str) -> None:
        _ = description

    def set_status(self, status: str) -> None:
        _ = status

    def set_secondary_status(self, status: str) -> None:
        _ = status

    def set_failed_status(self, status: str) -> None:
        _ = status

    def advance(self, amount: int = 1) -> None:
        _ = amount

    def set_total(self, total: int) -> None:
        _ = total


class FakeQueue:
    def __init__(self) -> None:
        self._items: list[str] = []
        self._checked_once = False

    def put(self, item: str) -> None:
        self._items.append(item)

    def empty(self) -> bool:
        if self._items and not self._checked_once:
            self._checked_once = True
            return False
        return True

    def qsize(self) -> int:
        return 0


class FakeProcess:
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        self.killed = False

    def start(self) -> None:
        return None

    def join(self, timeout: float | None = None) -> None:
        _ = timeout

    def kill(self) -> None:
        self.killed = True

    def is_alive(self) -> bool:
        return False


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=4,
        version="1.0.0",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def test_extract_bundles_logs_success_at_info_level(monkeypatch, tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    bundle_dir = Path(context.raw_dir) / "Bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "test.bundle").write_bytes(b"bundle")
    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)

    monkeypatch.setattr("ba_downloader.infrastructure.extract.asset_workflow.Queue", FakeQueue)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.multiprocessing.Process",
        FakeProcess,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.RichProgressReporter",
        DummyProgressReporter,
    )
    monkeypatch.setattr("ba_downloader.infrastructure.extract.asset_workflow.time.sleep", lambda *_: None)

    workflow.extract_bundles(context)

    assert logger.info_messages == ["Extracted bundles successfully."]
    assert logger.warn_messages == []


def test_extract_bundles_can_be_interrupted(monkeypatch, tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    bundle_dir = Path(context.raw_dir) / "Bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "test.bundle").write_bytes(b"bundle")
    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)
    stop_event_holder: dict[str, object] = {}
    created_processes: list[InterruptibleProcess] = []

    class BlockingQueue:
        def __init__(self) -> None:
            self._items: list[str] = []

        def put(self, item: str) -> None:
            self._items.append(item)

        def qsize(self) -> int:
            return len(self._items)

    class InterruptibleProcess:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            _ = (args, kwargs)
            self.started = False
            self.killed = False
            created_processes.append(self)

        def start(self) -> None:
            self.started = True

        def join(self, timeout: float | None = None) -> None:
            _ = timeout

        def kill(self) -> None:
            self.killed = True
            self.started = False

        def is_alive(self) -> bool:
            return self.started and not self.killed

    @contextmanager
    def fake_install_interrupt_handler(stop_event):  # type: ignore[no-untyped-def]
        stop_event_holder["event"] = stop_event
        yield

    def trigger_interrupt(*_args) -> None:
        stop_event = stop_event_holder["event"]
        stop_event.set()

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.Queue",
        BlockingQueue,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.multiprocessing.Process",
        InterruptibleProcess,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.RichProgressReporter",
        DummyProgressReporter,
    )
    monkeypatch.setattr(
        workflow,
        "_install_interrupt_handler",
        fake_install_interrupt_handler,
    )
    monkeypatch.setattr("ba_downloader.infrastructure.extract.asset_workflow.time.sleep", trigger_interrupt)

    with pytest.raises(KeyboardInterrupt):
        workflow.extract_bundles(context)

    assert logger.warn_messages == ["Cancelling bundle extraction..."]
    assert all(process.killed for process in created_processes)
