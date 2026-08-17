from __future__ import annotations

import asyncio
from pathlib import Path
from queue import Queue

import pytest

from ba_downloader.api.events import (
    QueueLogger,
    QueueProgressReporter,
    build_secret_redactions,
    redact_text,
)
from ba_downloader.api.files import FileRegistry
from ba_downloader.api.jobs import JobManager
from ba_downloader.api.services import ApiServices
from ba_downloader.api.state import ContextRegistry
from ba_downloader.api.streams import job_event_stream
from ba_downloader.application.operations import (
    ApplicationOperation,
    ApplicationOperationCommand,
)
from ba_downloader.domain.models.runtime import RuntimeContext


def _context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        "cn",
        1,
        "",
        str(tmp_path / "raw"),
        str(tmp_path / "extracted"),
        str(tmp_path / ".state/temp"),
        ("table",),
        "",
        1,
        (),
        (),
        str(tmp_path),
    )


def test_queue_logger_redacts_configured_secrets() -> None:
    queue: Queue[dict[str, object]] = Queue()
    logger = QueueLogger(queue, redactions=("secret-key", "proxy-password"))
    logger.error("secret-key failed through proxy-password")
    assert queue.get_nowait()["payload"] == {
        "level": "error",
        "message": "*** failed through ***",
    }


def test_proxy_redactions_cover_credentials_and_encoded_values() -> None:
    tokens = build_secret_redactions(
        sqlcipher_key_hex="a" * 64,
        proxy_url="https://secret-user:p%40ssword@example.test",
    )
    redacted = redact_text("secret-user p@ssword p%40ssword " + "a" * 64, tokens)
    assert all(
        value not in redacted
        for value in ("secret-user", "p@ssword", "p%40ssword", "a" * 64)
    )


def test_first_progress_secondary_status_is_emitted_immediately() -> None:
    queue: Queue[dict[str, object]] = Queue()
    reporter = QueueProgressReporter(queue, 1, "Extracting bundles...")
    reporter.__enter__()
    queue.get_nowait()

    reporter.set_secondary_status("Batch 1/1 (1 bundle): Loading")

    assert queue.get_nowait()["payload"] == {
        "completed": 0,
        "total": 1,
        "description": "Extracting bundles...",
        "secondary_status": "Batch 1/1 (1 bundle): Loading",
    }


def test_loading_progress_is_emitted_as_independent_fields() -> None:
    queue: Queue[dict[str, object]] = Queue()
    reporter = QueueProgressReporter(queue, 217, "Extracting bundles...")
    reporter.__enter__()
    queue.get_nowait()

    reporter.set_loading_progress(12, 217, "Loading files")

    assert queue.get_nowait()["payload"] == {
        "completed": 0,
        "total": 217,
        "description": "Extracting bundles...",
        "loading_completed": 12,
        "loading_total": 217,
        "loading_stage": "Loading files",
    }


def test_processing_status_is_emitted_as_independent_field() -> None:
    queue: Queue[dict[str, object]] = Queue()
    reporter = QueueProgressReporter(queue, 217, "Extracting bundles...")
    reporter.__enter__()
    queue.get_nowait()

    reporter.set_processing_status("Processing 00:12")

    assert queue.get_nowait()["payload"] == {
        "completed": 0,
        "total": 217,
        "description": "Extracting bundles...",
        "processing_status": "Processing 00:12",
    }


def test_job_stream_starts_with_current_snapshot(tmp_path: Path) -> None:
    jobs = JobManager()
    job = jobs.submit(
        ApplicationOperationCommand(ApplicationOperation.extract),
        _context(tmp_path),
        "context-1",
    )
    services = ApiServices(ContextRegistry(), jobs, FileRegistry(), "test", 9230)
    first = asyncio.run(anext(job_event_stream(services, job.id)))
    assert "event: snapshot" in first
    assert '"status": "queued"' in first


def test_shutdown_signal_closes_job_stream(tmp_path: Path) -> None:
    jobs = JobManager()
    job = jobs.submit(
        ApplicationOperationCommand(ApplicationOperation.extract),
        _context(tmp_path),
        "context-1",
    )
    services = ApiServices(ContextRegistry(), jobs, FileRegistry(), "test", 9230)
    services.shutdown_event.set()
    with pytest.raises(StopAsyncIteration):
        asyncio.run(anext(job_event_stream(services, job.id)))
