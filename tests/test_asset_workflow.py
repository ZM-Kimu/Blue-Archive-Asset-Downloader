from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Any

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
            inputs: list[object],
            *,
            concurrency: int,
            filtered: bool = False,
        ) -> BundleExtractionReport:
            assert received_context == context
            assert [item.path for item in inputs] == [bundle_dir / "a.zip"]
            assert concurrency == 1
            assert filtered is False
            return BundleExtractionReport(
                warnings=(expected_warning,),
                total_batches=1,
                succeeded_batches=1,
            )

    report = AssetExtractionWorkflow(
        RecordingLogger(),
        bundle_workflow=ReportingBundleWorkflow(),  # type: ignore[arg-type]
    ).extract_bundles(context, concurrency=1)

    assert report.warnings == (expected_warning,)


def test_media_extraction_observes_operation_cancellation(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    (media_dir / "voice.zip").write_bytes(b"zip")
    cancellation_event = Event()

    class CancellingMediaExtractor:
        def extract(
            self,
            _context: ExecutionContext,
            _files: list[Path],
            *,
            concurrency: int,
        ) -> None:
            _ = concurrency
            cancellation_event.set()
            raise OperationCancelledError("Media extraction cancelled by user.")

    workflow = AssetExtractionWorkflow(
        RecordingLogger(),
        cancellation=EventCancellation(cancellation_event),
        media_extractor=CancellingMediaExtractor(),  # type: ignore[arg-type]
    )

    with pytest.raises(OperationCancelledError):
        workflow.extract_media(context, concurrency=1)


def test_media_extraction_uses_filtered_existing_resources(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    (media_dir / "voice.zip").write_bytes(b"zip")
    (media_dir / "other.zip").write_bytes(b"zip")
    calls: list[str] = []

    class FakeMediaExtractor:
        def extract(
            self,
            received_context: ExecutionContext,
            files: list[Path],
            *,
            concurrency: int,
        ) -> None:
            assert received_context == context
            assert concurrency == 1
            calls.extend(path.name for path in files)

    AssetExtractionWorkflow(
        RecordingLogger(),
        media_extractor=FakeMediaExtractor(),  # type: ignore[arg-type]
    ).extract_media(
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


def test_media_extraction_propagates_batch_failure_after_processing_files(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, ("media",))
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    (media_dir / "bad.zip").write_bytes(b"zip")
    (media_dir / "good.zip").write_bytes(b"zip")
    calls: list[str] = []

    class FakeMediaExtractor:
        def extract(
            self,
            received_context: ExecutionContext,
            files: list[Path],
            *,
            concurrency: int,
        ) -> None:
            assert received_context == context
            assert concurrency == 1
            calls.extend(path.name for path in files)
            raise ExtractError("bad archive")

    with pytest.raises(ExtractError):
        AssetExtractionWorkflow(
            RecordingLogger(),
            media_extractor=FakeMediaExtractor(),  # type: ignore[arg-type]
        ).extract_media(context, concurrency=1)

    assert sorted(calls) == ["bad.zip", "good.zip"]


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
    captured_bundles: list[object] = []

    class RecordingBundleWorkflow:
        def run(
            self,
            _context: ExecutionContext,
            inputs: list[object],
            *,
            concurrency: int,
            filtered: bool = False,
        ) -> BundleExtractionReport:
            assert concurrency == 1
            assert filtered is False
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

    assert [item.path for item in captured_bundles] == [bundle_dir / "target.bundle"]
    assert captured_bundles[0].checksum.value == "deadbeef"
