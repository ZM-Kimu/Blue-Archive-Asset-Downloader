from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Any, ClassVar

import pytest

from ba_downloader.domain.exceptions import ExtractError, OperationCancelledError
from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import EventCancellation
from ba_downloader.infrastructure.extraction.assetripper.bundles import (
    BundleExtractionReport,
)
from ba_downloader.infrastructure.extraction.workflow import AssetExtractionWorkflow
from support.fixtures import build_execution_context


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


def _create_recording_progress(
    _factory: object,
    total: int,
    description: str,
    *,
    download_mode: bool = False,
    extract_mode: bool = False,
) -> RecordingProgressReporter:
    return RecordingProgressReporter(
        total,
        description,
        download_mode=download_mode,
        extract_mode=extract_mode,
    )


class FakeStopEvent:
    def is_set(self) -> bool:
        return False

    def wait(self, timeout: float) -> bool:
        _ = timeout
        return False


def _build_context(tmp_path: Path, resource_type: tuple[str, ...]) -> ExecutionContext:
    _ = resource_type
    return build_execution_context(
        tmp_path,
        region="jp",
        version="1.0.0",
        max_retries=1,
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
        "ba_downloader.infrastructure.progress.NullProgressReporterFactory.create",
        _create_recording_progress,
    )


def test_bundle_extraction_returns_workflow_warnings(tmp_path: Path) -> None:
    context = _build_context(tmp_path, ("bundle",))
    bundle_dir = context.workspace.raw_bundles
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "a.zip").write_bytes(b"bundle")
    expected_warning = "[BUNDLE_EXTRACTION_PARTIAL] partial output"

    class ReportingBundleWorkflow:
        def run(
            self,
            received_context: ExecutionContext,
            inputs: list[Path],
        ) -> BundleExtractionReport:
            assert received_context == context
            assert inputs == [bundle_dir / "a.zip"]
            return BundleExtractionReport(
                warnings=(expected_warning,),
                complete=False,
                total_batches=1,
                succeeded_batches=1,
            )

    report = AssetExtractionWorkflow(
        RecordingLogger(),
        bundle_workflow=ReportingBundleWorkflow(),  # type: ignore[arg-type]
    ).extract_bundles(context, concurrency=1)

    assert report.warnings == (expected_warning,)


def test_media_extraction_uses_extract_progress_mode(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    (media_dir / "voice.zip").write_bytes(b"zip")

    class FakeMediaExtractor:
        def __init__(self, received_context: ExecutionContext) -> None:
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

    AssetExtractionWorkflow(RecordingLogger()).extract_media(context, concurrency=1)

    progress = RecordingProgressReporter.instances[0]
    assert progress.extract_mode is True
    assert progress.statuses == ["0/1 files", "1/1 files"]
    assert progress.secondary_statuses == ["1/2 members", "2/2 members"]
    assert progress.advances == [1]


def test_media_extraction_observes_operation_cancellation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    (media_dir / "voice.zip").write_bytes(b"zip")
    cancellation_event = Event()

    class CancellingMediaExtractor:
        def __init__(self, _context: ExecutionContext) -> None:
            pass

        def extract_zip(self, _file_path: str, **kwargs: Any) -> None:
            cancellation_event.set()
            assert kwargs["should_stop"]()
            raise RuntimeError("Extraction cancelled by user.")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.MediaExtractor",
        CancellingMediaExtractor,
    )
    workflow = AssetExtractionWorkflow(
        RecordingLogger(),
        cancellation=EventCancellation(cancellation_event),
    )

    with pytest.raises(OperationCancelledError):
        workflow.extract_media(context, concurrency=1)


def test_media_extraction_uses_filtered_existing_resources(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    (media_dir / "voice.zip").write_bytes(b"zip")
    (media_dir / "other.zip").write_bytes(b"zip")
    calls: list[str] = []

    class FakeMediaExtractor:
        def __init__(self, received_context: ExecutionContext) -> None:
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
        concurrency=1,
    )

    assert calls == ["voice.zip"]


def test_media_extraction_aggregates_failures_after_processing_other_files(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    (media_dir / "bad.zip").write_bytes(b"zip")
    (media_dir / "good.zip").write_bytes(b"zip")
    calls: list[str] = []
    logger = RecordingLogger()

    class FakeMediaExtractor:
        def __init__(self, received_context: ExecutionContext) -> None:
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
        AssetExtractionWorkflow(logger).extract_media(context, concurrency=1)

    assert sorted(calls) == ["bad.zip", "good.zip"]
    assert any("bad.zip" in message for message in logger.error_messages)


def test_table_extraction_uses_process_runner_for_real_extractor(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("table",))
    table_dir = context.workspace.raw_tables
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
            received_context: ExecutionContext,
            *,
            concurrency: int,
            metadata_by_file: dict[str, dict[str, object]] | None = None,
        ) -> None:
            _ = metadata_by_file
            assert received_context == context
            assert concurrency == 1
            captured_files.append(files)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.ProcessTableExtractionRunner",
        FakeProcessTableExtractionRunner,
    )

    AssetExtractionWorkflow(RecordingLogger()).extract_tables(context, concurrency=1)

    assert len(captured_files) == 1
    assert sorted(captured_files[0]) == ["A.db", "B.db"]


def test_table_extraction_passes_resource_metadata_to_process_runner(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("table",))
    table_dir = context.workspace.raw_tables
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
            received_context: ExecutionContext,
            *,
            concurrency: int,
            metadata_by_file: dict[str, dict[str, object]],
        ) -> None:
            assert files == ["TablePatchPack_GroundStage_1.zip"]
            assert received_context == context
            assert concurrency == 1
            captured_metadata.append(metadata_by_file)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.workflow.ProcessTableExtractionRunner",
        FakeProcessTableExtractionRunner,
    )

    AssetExtractionWorkflow(RecordingLogger()).extract_tables(
        context, resources, concurrency=1
    )

    assert captured_metadata == [
        {"TablePatchPack_GroundStage_1.zip": {"includes": ["EN0010_VeryHard.zip"]}}
    ]


def test_table_extraction_uses_filtered_existing_resources(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("table",))
    table_dir = context.workspace.raw_tables
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
            received_context: ExecutionContext,
            *,
            concurrency: int,
            metadata_by_file: dict[str, dict[str, object]] | None = None,
        ) -> None:
            _ = metadata_by_file
            assert received_context == context
            assert concurrency == 1
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
        concurrency=1,
    )

    assert captured_files == [["ExcelDB.db"]]


def test_bundle_extraction_uses_filtered_existing_resources(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("bundle",))
    bundle_dir = context.workspace.raw_bundles
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "target.bundle").write_bytes(b"bundle")
    (bundle_dir / "other.bundle").write_bytes(b"bundle")
    captured_bundles: list[Path] = []

    class RecordingBundleWorkflow:
        def run(
            self,
            _context: ExecutionContext,
            inputs: list[Path],
        ) -> BundleExtractionReport:
            captured_bundles.extend(inputs)
            return BundleExtractionReport()

    workflow = AssetExtractionWorkflow(
        RecordingLogger(),
        bundle_workflow=RecordingBundleWorkflow(),  # type: ignore[arg-type]
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
        concurrency=1,
    )

    assert captured_bundles == [bundle_dir / "target.bundle"]
