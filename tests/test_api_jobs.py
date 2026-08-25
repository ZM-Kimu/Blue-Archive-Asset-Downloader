from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from ba_downloader.api.jobs import (
    BundleJobConflictError,
    JobManager,
    MediaJobConflictError,
)
from ba_downloader.application.contracts import (
    ApplicationCommand,
    AssetOperationOptions,
    AssetsExtractCommand,
)
from ba_downloader.domain.models.asset_type_selection import ResourceTypeSelection
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.assetripper.bundles import (
    bundle_extraction_lock_path,
)
from ba_downloader.infrastructure.extraction.media.exporter import (
    media_extraction_lock_path,
)
from ba_downloader.infrastructure.files.lock import InterprocessFileLock
from support.fixtures import build_execution_context


def successful_worker(
    command: ApplicationCommand,
    context: ExecutionContext,
    event_queue: Any,
    terminal_sender: Any,
    cancel_event: Any,
) -> None:
    _ = (command, cancel_event)
    terminal_sender.send(
        {
            "type": "result",
            "payload": {
                "context": context,
                "artifacts": (),
                "catalog": None,
                "warnings": ("partial bundle output",),
            },
        }
    )


def crashing_worker(
    command: ApplicationCommand,
    context: ExecutionContext,
    event_queue: Any,
    terminal_sender: Any,
    cancel_event: Any,
) -> None:
    _ = (command, context, event_queue, terminal_sender, cancel_event)
    os._exit(3)


def cooperative_worker(
    command: ApplicationCommand,
    context: ExecutionContext,
    event_queue: Any,
    terminal_sender: Any,
    cancel_event: Any,
) -> None:
    _ = (command, context, event_queue)
    while not cancel_event.wait(0.01):
        pass
    terminal_sender.send({"type": "cancelled", "payload": {}})
    terminal_sender.close()


def _context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="cn",
        version="",
        max_retries=1,
    )


def _command() -> ApplicationCommand:
    return AssetsExtractCommand()


def _media_command() -> ApplicationCommand:
    return AssetsExtractCommand(
        AssetOperationOptions(
            resources=ResourceTypeSelection.from_values(("media",)),
        )
    )


def test_job_manager_executes_spawned_job(tmp_path: Path) -> None:
    manager = JobManager(process_target=successful_worker)
    manager.start()
    try:
        job = manager.submit(_command(), _context(tmp_path), "context-1")
        deadline = time.monotonic() + 10
        while manager.get(job.id).status not in {"succeeded", "failed"}:
            assert time.monotonic() < deadline
            time.sleep(0.05)

        assert manager.get(job.id).status == "succeeded"
        assert manager.get(job.id).warnings == ("partial bundle output",)
        assert [
            event.payload["status"] for event in job.events if event.type == "state"
        ] == [
            "queued",
            "running",
            "succeeded",
        ]
    finally:
        manager.stop()


def test_queued_job_can_be_cancelled_before_start(tmp_path: Path) -> None:
    manager = JobManager(process_target=successful_worker)
    job = manager.submit(_command(), _context(tmp_path), "context-1")

    cancelled = manager.cancel(job.id)

    assert cancelled.status == "cancelled"


def test_cancelled_job_releases_queue_capacity(tmp_path: Path) -> None:
    manager = JobManager(queue_limit=1, process_target=successful_worker)
    first = manager.submit(_command(), _context(tmp_path), "context-1")

    manager.cancel(first.id)
    replacement = manager.submit(_command(), _context(tmp_path), "context-1")

    assert replacement.status == "queued"


def test_bundle_job_conflict_is_rejected_before_queueing(tmp_path: Path) -> None:
    manager = JobManager(process_target=successful_worker)
    context = _context(tmp_path)
    manager.submit(_command(), context, "context-1")

    with pytest.raises(BundleJobConflictError):
        manager.submit(_command(), context, "context-1")


def test_external_bundle_lock_is_left_to_worker_boundary(tmp_path: Path) -> None:
    manager = JobManager(process_target=successful_worker)
    context = _context(tmp_path)

    with InterprocessFileLock(
        bundle_extraction_lock_path(context), operation="external extraction"
    ):
        job = manager.submit(_command(), context, "context-1")

    assert job.status == "queued"


def test_queued_media_job_is_rejected_before_queueing(tmp_path: Path) -> None:
    manager = JobManager(process_target=successful_worker)
    context = _context(tmp_path)
    manager.submit(_media_command(), context, "context-1")

    with pytest.raises(MediaJobConflictError):
        manager.submit(_media_command(), context, "context-1")


def test_external_media_lock_is_left_to_worker_boundary(tmp_path: Path) -> None:
    manager = JobManager(process_target=successful_worker)
    context = _context(tmp_path)

    with InterprocessFileLock(
        media_extraction_lock_path(context), operation="external media extraction"
    ):
        job = manager.submit(_media_command(), context, "context-1")

    assert job.status == "queued"


def test_job_manager_reports_worker_exit_without_terminal_message(
    tmp_path: Path,
) -> None:
    manager = JobManager(process_target=crashing_worker)
    manager.start()
    try:
        job = manager.submit(_command(), _context(tmp_path), "context-1")
        deadline = time.monotonic() + 10
        while manager.get(job.id).status not in {"succeeded", "failed"}:
            assert time.monotonic() < deadline
            time.sleep(0.05)

        assert manager.get(job.id).status == "failed"
        assert manager.get(job.id).error == {
            "code": "WORKER_EXIT",
            "message": "Worker exited with code 3.",
            "exception_type": "WorkerExit",
        }
    finally:
        manager.stop()


def test_running_job_cancels_cooperatively_before_termination_timeout(
    tmp_path: Path,
) -> None:
    manager = JobManager(process_target=cooperative_worker)
    manager.start()
    try:
        job = manager.submit(_command(), _context(tmp_path), "context-1")
        deadline = time.monotonic() + 10
        while manager.get(job.id).status != "running":
            assert time.monotonic() < deadline
            time.sleep(0.01)

        started = time.monotonic()
        manager.cancel(job.id)
        while manager.get(job.id).status != "cancelled":
            assert time.monotonic() < deadline
            time.sleep(0.01)

        assert time.monotonic() - started < 5
    finally:
        manager.stop()
