from __future__ import annotations

import sqlite3
import struct
from contextlib import contextmanager
from pathlib import Path
from zipfile import BadZipFile

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
    def fake_install_interrupt_handler(
        stop_event,
        *,
        on_interrupt=None,
    ):  # type: ignore[no-untyped-def]
        stop_event.set()
        if on_interrupt is not None:
            on_interrupt()
        yield

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

    with pytest.raises(KeyboardInterrupt):
        workflow.extract_bundles(context)

    assert logger.warn_messages == ["Cancelling bundle extraction..."]
    assert all(process.killed for process in created_processes)


def test_extract_bundles_respects_context_threads(monkeypatch, tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(threads=3)
    bundle_dir = Path(context.raw_dir) / "Bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for index in range(5):
        (bundle_dir / f"test_{index}.bundle").write_bytes(b"bundle")

    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)
    created_processes: list[FakeProcess] = []

    class CountingQueue(FakeQueue):
        def qsize(self) -> int:
            return 0

    class CountingProcess(FakeProcess):
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            super().__init__(*args, **kwargs)
            created_processes.append(self)

    monkeypatch.setattr("ba_downloader.infrastructure.extract.asset_workflow.Queue", CountingQueue)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.multiprocessing.Process",
        CountingProcess,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.RichProgressReporter",
        DummyProgressReporter,
    )
    monkeypatch.setattr("ba_downloader.infrastructure.extract.asset_workflow.os.cpu_count", lambda: 8)

    workflow.extract_bundles(context)

    assert len(created_processes) == 3


def test_extract_media_can_be_interrupted(monkeypatch, tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(resource_type=("media",))
    media_dir = Path(context.raw_dir) / "Media"
    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / "test.zip").write_bytes(b"zip")
    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)

    class InterruptibleMediaExtractor:
        def __init__(self, active_context: RuntimeContext) -> None:
            _ = active_context

        def extract_zip(self, file_path: str, *, should_stop=None) -> None:  # type: ignore[no-untyped-def]
            _ = file_path
            if should_stop is not None and should_stop():
                raise RuntimeError("Extraction cancelled by user.")

    @contextmanager
    def fake_install_interrupt_handler(
        stop_event,
        *,
        on_interrupt=None,
    ):  # type: ignore[no-untyped-def]
        _ = on_interrupt
        stop_event.set()
        yield

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.MediaExtractor",
        InterruptibleMediaExtractor,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.RichProgressReporter",
        DummyProgressReporter,
    )
    monkeypatch.setattr(workflow, "_install_interrupt_handler", fake_install_interrupt_handler)

    with pytest.raises(KeyboardInterrupt):
        workflow.extract_media(context)


def test_extract_tables_can_be_interrupted(monkeypatch, tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(resource_type=("table",))
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / "Excel.zip").write_bytes(b"zip")
    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)

    class InterruptibleTableExtractor:
        table_file_folder = str(table_dir)
        extract_folder = str(Path(context.extract_dir) / "Table")

        @classmethod
        def from_context(cls, active_context: RuntimeContext, logger=None):  # type: ignore[no-untyped-def]
            _ = (active_context, logger)
            return cls()

        def extract_table(self, file_path: str, *, should_stop=None) -> None:  # type: ignore[no-untyped-def]
            _ = file_path
            if should_stop is not None and should_stop():
                raise RuntimeError("Extraction cancelled by user.")

    @contextmanager
    def fake_install_interrupt_handler(
        stop_event,
        *,
        on_interrupt=None,
    ):  # type: ignore[no-untyped-def]
        _ = on_interrupt
        stop_event.set()
        yield

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.TableExtractor",
        InterruptibleTableExtractor,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.RichProgressReporter",
        DummyProgressReporter,
    )
    monkeypatch.setattr(workflow, "_install_interrupt_handler", fake_install_interrupt_handler)

    with pytest.raises(KeyboardInterrupt):
        workflow.extract_tables(context)


def test_extract_tables_continues_after_single_file_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(resource_type=("table",), threads=1)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / "ExcelDB.db").write_bytes(b"not-a-db")
    (table_dir / "RhythmBeatmapData.zip").write_bytes(b"zip")
    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)
    processed: list[str] = []

    class ResilientTableExtractor:
        table_file_folder = str(table_dir)
        extract_folder = str(Path(context.extract_dir) / "Table")

        @classmethod
        def from_context(cls, active_context: RuntimeContext, logger=None):  # type: ignore[no-untyped-def]
            _ = (active_context, logger)
            return cls()

        def extract_table(self, file_path: str, *, should_stop=None) -> None:  # type: ignore[no-untyped-def]
            _ = should_stop
            processed.append(file_path)
            if file_path == "ExcelDB.db":
                raise sqlite3.DatabaseError("file is not a database")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.TableExtractor",
        ResilientTableExtractor,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.RichProgressReporter",
        DummyProgressReporter,
    )

    workflow.extract_tables(context)

    assert processed == ["ExcelDB.db", "RhythmBeatmapData.zip"]
    assert logger.error_messages == [
        "Failed to extract ExcelDB.db: file is not a database"
    ]


def test_extract_tables_continues_after_bad_zip_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(resource_type=("table",), threads=1)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / "HexaMap.zip").write_bytes(b"not-a-zip")
    (table_dir / "Valid.zip").write_bytes(b"zip")
    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)
    processed: list[str] = []

    class ResilientTableExtractor:
        table_file_folder = str(table_dir)
        extract_folder = str(Path(context.extract_dir) / "Table")

        @classmethod
        def from_context(cls, active_context: RuntimeContext, logger=None):  # type: ignore[no-untyped-def]
            _ = (active_context, logger)
            return cls()

        def extract_table(self, file_path: str, *, should_stop=None) -> None:  # type: ignore[no-untyped-def]
            _ = should_stop
            processed.append(file_path)
            if file_path == "HexaMap.zip":
                raise BadZipFile("File is not a zip file")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.TableExtractor",
        ResilientTableExtractor,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.RichProgressReporter",
        DummyProgressReporter,
    )

    workflow.extract_tables(context)

    assert processed == ["HexaMap.zip", "Valid.zip"]
    assert logger.error_messages == [
        "Failed to extract HexaMap.zip: File is not a zip file"
    ]


def test_extract_tables_continues_after_unexpected_worker_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(resource_type=("table",), threads=1)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / "HexaMap.zip").write_bytes(b"payload")
    (table_dir / "Valid.zip").write_bytes(b"payload")
    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)
    processed: list[str] = []

    class ResilientTableExtractor:
        table_file_folder = str(table_dir)
        extract_folder = str(Path(context.extract_dir) / "Table")

        @classmethod
        def from_context(cls, active_context: RuntimeContext, logger=None):  # type: ignore[no-untyped-def]
            _ = (active_context, logger)
            return cls()

        def extract_table(self, file_path: str, *, should_stop=None) -> None:  # type: ignore[no-untyped-def]
            _ = should_stop
            processed.append(file_path)
            if file_path == "HexaMap.zip":
                raise struct.error("unpack_from requires a buffer")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.TableExtractor",
        ResilientTableExtractor,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extract.asset_workflow.RichProgressReporter",
        DummyProgressReporter,
    )

    workflow.extract_tables(context)

    assert processed == ["HexaMap.zip", "Valid.zip"]
    assert logger.error_messages == [
        "Failed to extract HexaMap.zip: unpack_from requires a buffer"
    ]
