from __future__ import annotations

import multiprocessing
import time
from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from queue import Empty
from threading import Event, RLock, Thread
from typing import Any, Literal
from uuid import uuid4

from ba_downloader.api.events import build_secret_redactions, redact_text
from ba_downloader.api.worker import run_application_job
from ba_downloader.application.contracts import (
    ApplicationCommand,
    AssetsDownloadCommand,
    AssetsExtractCommand,
    AssetsSyncCommand,
    BuildCharacterIndexCommand,
    CatalogRefreshCommand,
    StorageCleanupCommand,
)
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext

JobStatus = Literal[
    "queued",
    "running",
    "cancelling",
    "cancelled",
    "succeeded",
    "failed",
]
TERMINAL_STATUSES = frozenset({"cancelled", "succeeded", "failed"})


class JobQueueFullError(RuntimeError):
    pass


class JobStateError(RuntimeError):
    pass


class BundleJobConflictError(RuntimeError):
    pass


class MediaJobConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class JobEvent:
    id: int
    type: str
    timestamp: str
    payload: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "type": self.type,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


@dataclass(slots=True)
class JobRecord:
    id: str
    command: ApplicationCommand
    context_id: str
    context: ExecutionContext
    status: JobStatus = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    error: dict[str, object] | None = None
    artifacts: tuple[tuple[str, str], ...] = ()
    statistics: tuple[tuple[str, int], ...] = ()
    warnings: tuple[str, ...] = ()
    effective_context: ExecutionContext | None = None
    events: deque[JobEvent] = field(default_factory=lambda: deque(maxlen=2000))
    next_event_id: int = 1

    @property
    def operation(self) -> str:
        names = {
            AssetsSyncCommand: "sync",
            AssetsDownloadCommand: "download",
            AssetsExtractCommand: "extract",
            BuildCharacterIndexCommand: "character-index",
            CatalogRefreshCommand: "catalog-refresh",
            StorageCleanupCommand: "storage-cleanup",
        }
        return names[type(self.command)]

    def append_event(
        self,
        event_type: str,
        payload: dict[str, object],
        *,
        timestamp: str | None = None,
    ) -> JobEvent:
        event = JobEvent(
            self.next_event_id,
            event_type,
            timestamp or datetime.now(UTC).isoformat(),
            payload,
        )
        self.next_event_id += 1
        self.events.append(event)
        return event

    def view(self) -> dict[str, object]:
        progress = next(
            (
                event.payload
                for event in reversed(self.events)
                if event.type == "progress"
            ),
            None,
        )
        return {
            "id": self.id,
            "operation": self.operation,
            "context_id": self.context_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": progress,
            "error": self.error,
            "statistics": dict(self.statistics),
            "warnings": list(self.warnings),
        }


class JobManager:
    def __init__(
        self,
        *,
        queue_limit: int = 16,
        history_limit: int = 50,
        process_target: Callable[..., None] = run_application_job,
        result_callback: Callable[
            [JobRecord, ExecutionContext, AssetCollection | None], None
        ]
        | None = None,
    ) -> None:
        self._queue_limit = queue_limit
        self._pending: deque[str] = deque()
        self._history_limit = history_limit
        self._process_target = process_target
        self._result_callback = result_callback
        self._jobs: dict[str, JobRecord] = {}
        self._order: deque[str] = deque()
        self._lock = RLock()
        self._wake = Event()
        self._stopping = Event()
        self._thread: Thread | None = None
        self._running_job_id: str | None = None
        self._running_cancel_event: Any | None = None
        self._running_process: Any | None = None
        self._catalogs: dict[str, AssetCollection] = {}

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stopping.clear()
            self._thread = Thread(
                target=self._run, name="baad-job-manager", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        with self._lock:
            if self._running_cancel_event is not None:
                self._running_cancel_event.set()
            for job in self._jobs.values():
                if job.status == "queued":
                    self._finish(job, "cancelled")
            self._pending.clear()
            process = self._running_process
        if process is not None and process.is_alive():
            process.terminate()
            process.join(timeout=2.0)
        if process is not None and process.is_alive():
            process.kill()
            process.join(timeout=2.0)
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)

    def is_busy(self) -> bool:
        with self._lock:
            return self._running_job_id is not None or any(
                job.status == "queued" for job in self._jobs.values()
            )

    def submit(
        self,
        command: ApplicationCommand,
        context: ExecutionContext,
        context_id: str,
    ) -> JobRecord:
        with self._lock:
            if self._stopping.is_set():
                raise JobStateError("The job manager is shutting down.")
            if len(self._pending) >= self._queue_limit:
                raise JobQueueFullError("The in-memory job queue is full.")
            if self._is_bundle_command(command):
                key = (context.region, context.platform)
                if any(
                    job.status in {"queued", "running", "cancelling"}
                    and (job.context.region, job.context.platform) == key
                    and self._is_bundle_command(job.command)
                    for job in self._jobs.values()
                ):
                    raise BundleJobConflictError(
                        "Bundle extraction is already queued or running for this context."
                    )
                self._preflight_bundle_lock(context)
            if self._is_media_command(command):
                key = (context.region, context.platform)
                if any(
                    job.status in {"queued", "running", "cancelling"}
                    and (job.context.region, job.context.platform) == key
                    and self._is_media_command(job.command)
                    for job in self._jobs.values()
                ):
                    raise MediaJobConflictError(
                        "Media extraction is already queued or running for this context."
                    )
                self._preflight_media_lock(context)
            job = JobRecord(
                id=uuid4().hex,
                command=command,
                context_id=context_id,
                context=context,
            )
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._pending.append(job.id)
            self._append_job_event(job, "state", {"status": "queued"})
        self._wake.set()
        return job

    @staticmethod
    def _is_bundle_command(command: ApplicationCommand) -> bool:
        return isinstance(command, AssetsSyncCommand | AssetsExtractCommand) and (
            command.options.resources.contains("bundle")
        )

    @staticmethod
    def _is_media_command(command: ApplicationCommand) -> bool:
        return isinstance(command, AssetsSyncCommand | AssetsExtractCommand) and (
            command.options.resources.contains("media")
        )

    @staticmethod
    def _preflight_bundle_lock(context: ExecutionContext) -> None:
        from ba_downloader.infrastructure.extraction.assetripper.bundles import (
            bundle_extraction_lock_path,
        )
        from ba_downloader.infrastructure.files.lock import (
            InterprocessFileLock,
            InterprocessLockBusyError,
        )

        try:
            with InterprocessFileLock(
                bundle_extraction_lock_path(context),
                operation="bundle extraction preflight",
            ):
                pass
        except InterprocessLockBusyError as exc:
            raise BundleJobConflictError(str(exc)) from exc

    @staticmethod
    def _preflight_media_lock(context: ExecutionContext) -> None:
        from ba_downloader.infrastructure.extraction.media.exporter import (
            media_extraction_lock_path,
        )
        from ba_downloader.infrastructure.files.lock import (
            InterprocessFileLock,
            InterprocessLockBusyError,
        )

        try:
            with InterprocessFileLock(
                media_extraction_lock_path(context),
                operation="media extraction preflight",
            ):
                pass
        except InterprocessLockBusyError as exc:
            raise MediaJobConflictError(str(exc)) from exc

    def list_jobs(self) -> list[JobRecord]:
        with self._lock:
            return [self._jobs[job_id] for job_id in reversed(self._order)]

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError as exc:
                raise KeyError(f"Unknown job '{job_id}'.") from exc

    def cancel(self, job_id: str) -> JobRecord:
        with self._lock:
            job = self.get(job_id)
            if job.status == "queued":
                with suppress(ValueError):
                    self._pending.remove(job_id)
                self._finish(job, "cancelled")
            elif job.status == "running":
                job.status = "cancelling"
                self._append_job_event(job, "state", {"status": "cancelling"})
                if (
                    self._running_job_id == job_id
                    and self._running_cancel_event is not None
                ):
                    self._running_cancel_event.set()
            elif job.status not in TERMINAL_STATUSES:
                raise JobStateError(f"Job '{job_id}' cannot be cancelled.")
            return job

    def events_after(self, job_id: str, event_id: int) -> list[JobEvent]:
        with self._lock:
            job = self.get(job_id)
            return [event for event in job.events if event.id > event_id]

    def catalog(self, context_id: str) -> AssetCollection | None:
        with self._lock:
            return self._catalogs.get(context_id)

    def cache_catalog(self, catalog: AssetCollection, context_id: str) -> None:
        with self._lock:
            self._catalogs[context_id] = catalog

    def references_context(self, context_id: str) -> bool:
        with self._lock:
            return any(
                job.context_id == context_id
                and job.status in {"queued", "running", "cancelling"}
                for job in self._jobs.values()
            )

    def _run(self) -> None:
        while not self._stopping.is_set():
            with self._lock:
                job_id = self._pending.popleft() if self._pending else None
            if job_id is None:
                self._wake.wait(0.2)
                self._wake.clear()
                continue
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None or job.status != "queued":
                    continue
            self._execute_job(job)
            self._trim_history()

    def _execute_job(self, job: JobRecord) -> None:
        process_context = multiprocessing.get_context("spawn")
        event_queue = process_context.Queue()
        terminal_receiver, terminal_sender = process_context.Pipe(duplex=False)
        cancel_event = process_context.Event()
        process = process_context.Process(
            target=self._process_target,
            args=(
                job.command,
                job.context,
                event_queue,
                terminal_sender,
                cancel_event,
            ),
            daemon=False,
        )
        with self._lock:
            self._running_job_id = job.id
            self._running_cancel_event = cancel_event
            self._running_process = process
            job.status = "running"
            job.started_at = datetime.now(UTC).isoformat()
            self._append_job_event(job, "state", {"status": "running"})
        try:
            process.start()
            terminal_sender.close()
        except BaseException as exc:
            with self._lock:
                redactions = build_secret_redactions(
                    sqlcipher_key_hex=job.context.sqlcipher_key,
                    proxy_url=job.context.proxy_url,
                )
                job.error = {
                    "code": "WORKER_START_FAILED",
                    "message": redact_text(
                        str(exc) or exc.__class__.__name__, redactions
                    ),
                    "exception_type": exc.__class__.__name__,
                }
                self._append_job_event(job, "error", job.error)
                self._finish(job, "failed")
                self._running_job_id = None
                self._running_cancel_event = None
                self._running_process = None
            self._close_queue(event_queue)
            terminal_receiver.close()
            terminal_sender.close()
            return

        cancel_started: float | None = None
        while process.is_alive():
            self._drain_worker_events(job, event_queue)
            self._receive_terminal(job, terminal_receiver)
            with self._lock:
                cancelling = job.status == "cancelling"
            if cancelling:
                cancel_event.set()
                cancel_started = cancel_started or time.monotonic()
                elapsed = time.monotonic() - cancel_started
                if process.is_alive() and elapsed >= 5.0:
                    process.terminate()
                if process.is_alive() and elapsed >= 7.0:
                    process.kill()
            if not process.is_alive():
                break
            time.sleep(0.05)

        process.join(timeout=2.0)
        self._drain_worker_events(job, event_queue)
        terminal_deadline = time.monotonic() + 1.0
        while time.monotonic() < terminal_deadline:
            if self._receive_terminal(job, terminal_receiver, timeout=0.05):
                break
        terminal_receiver.close()
        self._close_queue(event_queue)
        with self._lock:
            if job.status == "cancelling":
                self._finish(job, "cancelled")
            elif job.status not in TERMINAL_STATUSES:
                message = f"Worker exited with code {process.exitcode}."
                job.error = {
                    "code": "WORKER_EXIT",
                    "message": message,
                    "exception_type": "WorkerExit",
                }
                self._append_job_event(job, "error", job.error)
                self._finish(job, "failed")
            self._running_job_id = None
            self._running_cancel_event = None
            self._running_process = None

    def _drain_worker_events(self, job: JobRecord, event_queue: Any) -> None:
        while True:
            try:
                message = event_queue.get_nowait()
            except Empty:
                return
            if not isinstance(message, dict):
                continue
            event_type = str(message.get("type", "event"))
            timestamp = str(message.get("timestamp", "")) or None
            payload = message.get("payload", {})
            if not isinstance(payload, dict):
                payload = {"value": payload}
            with self._lock:
                self._append_job_event(
                    job, event_type, dict(payload), timestamp=timestamp
                )

    def _receive_terminal(
        self,
        job: JobRecord,
        terminal_receiver: Any,
        *,
        timeout: float = 0.0,
    ) -> bool:
        try:
            has_message = terminal_receiver.poll(timeout)
        except OSError:
            return False
        if not has_message:
            return False
        try:
            message = terminal_receiver.recv()
        except (EOFError, OSError):
            return False
        if not isinstance(message, dict):
            return False

        event_type = str(message.get("type", ""))
        timestamp = str(message.get("timestamp", "")) or None
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            payload = {"value": payload}
        with self._lock:
            if event_type == "result":
                job.artifacts = tuple(payload.get("artifacts", ()))
                job.statistics = tuple(payload.get("statistics", ()))
                job.warnings = tuple(payload.get("warnings", ()))
                effective_context = payload.get("context")
                if isinstance(effective_context, ExecutionContext):
                    job.effective_context = effective_context
                catalog = payload.get("catalog")
                if isinstance(catalog, AssetCollection):
                    self.cache_catalog(catalog, job.context_id)
                if (
                    self._result_callback is not None
                    and job.effective_context is not None
                ):
                    self._result_callback(
                        job,
                        job.effective_context,
                        catalog if isinstance(catalog, AssetCollection) else None,
                    )
                self._finish(job, "succeeded")
            elif event_type == "cancelled":
                self._finish(job, "cancelled")
            elif event_type == "error":
                job.error = dict(payload)
                self._append_job_event(job, "error", dict(payload), timestamp=timestamp)
                self._finish(job, "failed")
            else:
                return False
        return True

    def _finish(self, job: JobRecord, status: JobStatus) -> None:
        if job.status in TERMINAL_STATUSES:
            return
        job.status = status
        job.finished_at = datetime.now(UTC).isoformat()
        self._append_job_event(job, "state", {"status": status})
        job.events = deque(
            (event for event in job.events if event.type != "log"),
            maxlen=2000,
        )
        self._trim_history()

    def _append_job_event(
        self,
        job: JobRecord,
        event_type: str,
        payload: dict[str, object],
        *,
        timestamp: str | None = None,
    ) -> JobEvent:
        event = job.append_event(event_type, payload, timestamp=timestamp)
        return event

    def _trim_history(self) -> None:
        with self._lock:
            terminal_ids = [
                job_id
                for job_id in self._order
                if self._jobs[job_id].status in TERMINAL_STATUSES
            ]
            while len(terminal_ids) > self._history_limit:
                job_id = terminal_ids.pop(0)
                self._jobs.pop(job_id, None)
                self._order.remove(job_id)

    @staticmethod
    def _close_queue(queue: Any) -> None:
        close = getattr(queue, "close", None)
        cancel_join_thread = getattr(queue, "cancel_join_thread", None)
        if callable(cancel_join_thread):
            cancel_join_thread()
        if callable(close):
            close()
