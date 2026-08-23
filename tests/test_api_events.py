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
from ba_downloader.application.contracts import AssetsExtractCommand
from ba_downloader.domain.models.execution import ExecutionContext
from support import build_execution_context


def _context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="cn",
        version="",
        max_retries=1,
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


def test_queue_progress_uses_the_unified_wire_contract() -> None:
    queue: Queue[dict[str, object]] = Queue()
    reporter = QueueProgressReporter(queue, 10, "Extracting bundles")
    reporter.set_progress(
        3,
        10,
        stage="processing",
        unit="entries",
        status="3/10 entries",
        secondary_status="Processor 2/17: Prefab",
    )
    reporter.stop()

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    payload = events[-1]["payload"]
    assert payload == {
        "completed": 3,
        "total": 10,
        "stage": "processing",
        "unit": "entries",
        "status": "3/10 entries",
        "secondary_status": "Processor 2/17: Prefab",
    }


def test_job_stream_starts_with_current_snapshot(tmp_path: Path) -> None:
    jobs = JobManager()
    job = jobs.submit(
        AssetsExtractCommand(),
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
        AssetsExtractCommand(),
        _context(tmp_path),
        "context-1",
    )
    services = ApiServices(ContextRegistry(), jobs, FileRegistry(), "test", 9230)
    services.shutdown_event.set()
    with pytest.raises(StopAsyncIteration):
        asyncio.run(anext(job_event_stream(services, job.id)))
