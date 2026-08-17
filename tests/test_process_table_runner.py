from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.process_table_runner import (
    ProcessTableExtractionRunner,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.extraction.threaded_runner import (
    ExtractionFailureError,
)
from support import RecordingLogger, build_runtime_context


def _failing_table_profile(_context: RuntimeContext) -> TableExtractionProfile:
    raise RuntimeError("profile construction failed")


def _create_empty_flatbuffer_package(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "__init__.py").write_text(
        "from ._registry import FLATBUFFER_ENUMS, FLATBUFFER_TYPES\n",
        encoding="utf8",
    )
    (root / "_registry.py").write_text(
        "FLATBUFFER_TYPES = {}\nFLATBUFFER_ENUMS = {}\n",
        encoding="utf8",
    )


def test_process_table_runner_flushes_events_before_closing_workers(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = build_runtime_context(tmp_path, region="jp").with_updates(threads=2)
    _create_empty_flatbuffer_package(Path(context.extract_dir) / "FlatBufferData")
    files = [f"unsupported-{index}.bytes" for index in range(200)]
    runner = ProcessTableExtractionRunner(
        logger,
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
    )

    runner.run(files, context)

    assert len(logger.by_level("warn")) == len(files)
    assert logger.by_level("error") == []


def test_process_table_runner_preserves_business_failure_after_worker_cleanup(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = build_runtime_context(tmp_path, region="jp")
    runner = ProcessTableExtractionRunner(
        logger,
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
        table_profile_factory=_failing_table_profile,
    )

    with pytest.raises(ExtractionFailureError):
        runner.run(["broken.zip"], context)

    assert any(
        "profile construction failed" in message for message in logger.by_level("error")
    )
    assert not any(
        "Cannot close a process while it is still running" in message
        for message in logger.by_level("error")
    )
