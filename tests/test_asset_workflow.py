from __future__ import annotations

from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from ba_downloader.domain.exceptions import ExtractError
from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.bundle.exporter import BundleLogEvent
from ba_downloader.infrastructure.extraction.workflow import AssetExtractionWorkflow


class RecordingLogger:
    def __init__(self) -> None:
        self.error_messages: list[str] = []
        self.info_messages: list[str] = []
        self.warn_messages: list[str] = []

    def error(self, message: str) -> None:
        self.error_messages.append(message)

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def warn(self, message: str) -> None:
        self.warn_messages.append(message)


class RecordingProgressReporter:
    instances: ClassVar[list[RecordingProgressReporter]] = []

    def __init__(
        self,
        total: int,
        description: str,
        *,
        download_mode: bool = False,
        extract_mode: bool = False,
    ) -> None:
        self.total = total
        self.description = description
        self.download_mode = download_mode
        self.extract_mode = extract_mode
        self.advances: list[int] = []
        self.descriptions: list[str] = []
        self.statuses: list[str] = []
        self.secondary_statuses: list[str] = []
        self.completed: list[int] = []
        self.instances.append(self)

    def __enter__(self) -> RecordingProgressReporter:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def advance(self, amount: int = 1) -> None:
        self.advances.append(amount)

    def set_total(self, total: int) -> None:
        self.total = total

    def set_description(self, description: str) -> None:
        self.descriptions.append(description)

    def set_status(self, status: str) -> None:
        self.statuses.append(status)

    def set_secondary_status(self, status: str) -> None:
        self.secondary_statuses.append(status)

    def set_failed_status(self, status: str) -> None:
        _ = status

    def set_completed(self, completed: int) -> None:
        self.completed.append(completed)

    def stop(self) -> None:
        return None


class FakeStopEvent:
    def is_set(self) -> bool:
        return False

    def wait(self, timeout: float) -> bool:
        _ = timeout
        return False


def _build_context(tmp_path: Path, resource_type: tuple[str, ...]) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=1,
        version="1.0.0",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=resource_type,
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _resources(items: list[tuple[str, AssetType]]) -> AssetCollection:
    resources = AssetCollection()
    for item_path, asset_type in items:
        resources.add(
            "https://example.invalid/" + item_path,
            item_path,
            1,
            "deadbeef",
            "md5",
            asset_type,
        )
    return resources


def _patch_progress_reporter(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.RichProgressReporter",
        RecordingProgressReporter,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.threaded_runner.RichProgressReporter",
        RecordingProgressReporter,
    )


def test_media_extraction_uses_extract_progress_mode(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = Path(context.raw_dir) / "Media"
    media_dir.mkdir(parents=True)
    (media_dir / "voice.zip").write_bytes(b"zip")

    class FakeMediaExtractor:
        def __init__(self, received_context: RuntimeContext) -> None:
            assert received_context == context

        def extract_zip(self, file_path: str, **kwargs: Any) -> None:
            assert Path(file_path).name == "voice.zip"
            progress_callback = kwargs["progress_callback"]
            progress_callback("1/2 members")
            progress_callback("2/2 members")

    RecordingProgressReporter.instances = []
    _patch_progress_reporter(monkeypatch)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.MediaExtractor",
        FakeMediaExtractor,
    )

    AssetExtractionWorkflow(RecordingLogger()).extract_media(context)

    progress = RecordingProgressReporter.instances[0]
    assert progress.extract_mode is True
    assert progress.statuses == ["0/1 files", "1/1 files"]
    assert progress.secondary_statuses == ["1/2 members", "2/2 members"]
    assert progress.advances == [1]


def test_media_extraction_uses_filtered_existing_resources(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = Path(context.raw_dir) / "Media"
    media_dir.mkdir(parents=True)
    (media_dir / "voice.zip").write_bytes(b"zip")
    (media_dir / "other.zip").write_bytes(b"zip")
    calls: list[str] = []

    class FakeMediaExtractor:
        def __init__(self, received_context: RuntimeContext) -> None:
            assert received_context == context

        def extract_zip(self, file_path: str, **kwargs: Any) -> None:
            _ = kwargs
            calls.append(Path(file_path).name)

    RecordingProgressReporter.instances = []
    _patch_progress_reporter(monkeypatch)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.MediaExtractor",
        FakeMediaExtractor,
    )

    AssetExtractionWorkflow(RecordingLogger()).extract_media(
        context,
        _resources(
            [
                ("Media/voice.zip", AssetType.media),
                ("Media/missing.zip", AssetType.media),
                ("Media/raw.dat", AssetType.media),
                ("Bundle/not-media.bundle", AssetType.bundle),
            ]
        ),
    )

    assert calls == ["voice.zip"]


def test_media_extraction_aggregates_failures_after_processing_other_files(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = Path(context.raw_dir) / "Media"
    media_dir.mkdir(parents=True)
    (media_dir / "bad.zip").write_bytes(b"zip")
    (media_dir / "good.zip").write_bytes(b"zip")
    calls: list[str] = []
    logger = RecordingLogger()

    class FakeMediaExtractor:
        def __init__(self, received_context: RuntimeContext) -> None:
            assert received_context == context

        def extract_zip(self, file_path: str, **kwargs: Any) -> None:
            _ = kwargs
            calls.append(Path(file_path).name)
            if Path(file_path).name == "bad.zip":
                raise LookupError("bad archive")

    RecordingProgressReporter.instances = []
    _patch_progress_reporter(monkeypatch)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.MediaExtractor",
        FakeMediaExtractor,
    )

    with pytest.raises(ExtractError, match="media extraction failed for 1 file"):
        AssetExtractionWorkflow(logger).extract_media(context)

    assert sorted(calls) == ["bad.zip", "good.zip"]
    assert any("bad.zip" in message for message in logger.error_messages)


def test_table_extraction_uses_process_runner_for_real_extractor(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("table",))
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True)
    (table_dir / "A.db").write_bytes(b"db")
    (table_dir / "B.db").write_bytes(b"db")
    captured_files: list[list[str]] = []

    class FakeProcessTableExtractionRunner:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _ = (args, kwargs)

        def run(
            self,
            files: list[str],
            received_context: RuntimeContext,
        ) -> None:
            assert received_context == context
            captured_files.append(files)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.ProcessTableExtractionRunner",
        FakeProcessTableExtractionRunner,
    )

    AssetExtractionWorkflow(RecordingLogger()).extract_tables(context)

    assert len(captured_files) == 1
    assert sorted(captured_files[0]) == ["A.db", "B.db"]


def test_table_extraction_passes_resource_metadata_to_process_runner(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("table",))
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True)
    (table_dir / "TablePatchPack_GroundStage_1.zip").write_bytes(b"zip")
    resources = AssetCollection()
    metadata = {"includes": ["EN0010_VeryHard.zip"]}
    resources.add(
        "https://example.invalid/Table/TablePatchPack_GroundStage_1.zip",
        "Table/TablePatchPack_GroundStage_1.zip",
        1,
        "deadbeef",
        "md5",
        AssetType.table,
        metadata,
    )
    captured_metadata: list[dict[str, dict[str, object]]] = []

    class FakeProcessTableExtractionRunner:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _ = (args, kwargs)

        def run(
            self,
            files: list[str],
            received_context: RuntimeContext,
            *,
            metadata_by_file: dict[str, dict[str, object]],
        ) -> None:
            assert files == ["TablePatchPack_GroundStage_1.zip"]
            assert received_context == context
            captured_metadata.append(metadata_by_file)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.ProcessTableExtractionRunner",
        FakeProcessTableExtractionRunner,
    )

    AssetExtractionWorkflow(RecordingLogger()).extract_tables(context, resources)

    assert captured_metadata == [
        {"TablePatchPack_GroundStage_1.zip": {"includes": ["EN0010_VeryHard.zip"]}}
    ]


def test_table_extraction_uses_filtered_existing_resources(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("table",))
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True)
    (table_dir / "ExcelDB.db").write_bytes(b"db")
    (table_dir / "Other.db").write_bytes(b"db")
    captured_files: list[list[str]] = []

    class FakeProcessTableExtractionRunner:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _ = (args, kwargs)

        def run(
            self,
            files: list[str],
            received_context: RuntimeContext,
        ) -> None:
            assert received_context == context
            captured_files.append(files)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.ProcessTableExtractionRunner",
        FakeProcessTableExtractionRunner,
    )

    AssetExtractionWorkflow(RecordingLogger()).extract_tables(
        context,
        _resources(
            [
                ("Table/ExcelDB.db", AssetType.table),
                ("Table/Missing.db", AssetType.table),
                ("Bundle/not-table.bundle", AssetType.bundle),
            ]
        ),
    )

    assert captured_files == [["ExcelDB.db"]]


def test_bundle_extraction_uses_filtered_existing_resources(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("bundle",))
    bundle_dir = Path(context.raw_dir) / "Bundle"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "target.bundle").write_bytes(b"bundle")
    (bundle_dir / "other.bundle").write_bytes(b"bundle")
    captured_bundles: list[str] = []
    workflow = AssetExtractionWorkflow(RecordingLogger())

    def build_processes(*args: Any, **kwargs: Any) -> list[Any]:
        _ = (args, kwargs)
        return []

    def monitor_bundle_extraction(**kwargs: Any) -> None:
        captured_bundles.extend(kwargs["bundles"])

    RecordingProgressReporter.instances = []
    _patch_progress_reporter(monkeypatch)
    monkeypatch.setattr(workflow, "_build_bundle_processes", build_processes)
    monkeypatch.setattr(
        workflow,
        "_monitor_bundle_extraction",
        monitor_bundle_extraction,
    )

    workflow.extract_bundles(
        context,
        _resources(
            [
                ("Bundle/target.bundle", AssetType.bundle),
                ("Bundle/missing.bundle", AssetType.bundle),
                ("Media/not-bundle.zip", AssetType.media),
            ]
        ),
    )

    assert captured_bundles == [str(bundle_dir / "target.bundle")]


def test_drain_bundle_log_events_routes_events_to_parent_logger() -> None:
    logger = RecordingLogger()
    events: Queue[BundleLogEvent] = Queue()
    events.put(BundleLogEvent("info", "info message"))
    events.put(BundleLogEvent("warn", "warn message"))
    events.put(BundleLogEvent("error", "error message"))

    AssetExtractionWorkflow(logger)._drain_bundle_log_events(events)

    assert logger.info_messages == ["info message"]
    assert logger.warn_messages == ["warn message"]
    assert logger.error_messages == ["error message"]


def test_bundle_monitor_drains_log_events_while_progress_is_active(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    workflow = AssetExtractionWorkflow(logger)
    task_queue: Queue[str] = Queue()
    log_events: Queue[BundleLogEvent] = Queue()
    log_events.put(BundleLogEvent("warn", "skipped mesh"))
    progress = RecordingProgressReporter(1, "Extracting bundles...", extract_mode=True)
    error_count = SimpleNamespace(value=0)

    workflow._monitor_bundle_extraction(
        queue=task_queue,
        bundles=[str(tmp_path / "sample.bundle")],
        processes=[],
        progress=progress,
        stop_event=FakeStopEvent(),
        error_count=error_count,
        log_events=log_events,
    )

    assert logger.warn_messages == ["skipped mesh"]
    assert logger.info_messages == ["Extracted bundles successfully."]
    assert progress.statuses[-1] == "1/1 bundles"
