from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import (
    ProgressReporterFactoryPort,
    ProgressReporterPort,
    ProgressState,
    preserve_terminal_progress,
)
from ba_downloader.domain.services.progress_timing import ProgressTimingEstimator


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class QueueLogger(LoggerPort):
    def __init__(self, queue: Any, *, redactions: tuple[str, ...] = ()) -> None:
        self._queue = queue
        self._redactions = tuple(value for value in redactions if value)

    def info(self, message: str) -> None:
        self._emit("info", message)

    def warn(self, message: str) -> None:
        self._emit("warning", message)

    def error(self, message: str) -> None:
        self._emit("error", message)

    def _emit(self, level: str, message: str) -> None:
        self._queue.put(
            {
                "type": "log",
                "timestamp": utc_now(),
                "payload": {
                    "level": level,
                    "message": redact_text(message, self._redactions),
                },
            }
        )


def redact_text(value: str, redactions: tuple[str, ...]) -> str:
    redacted = value
    for secret in redactions:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


def build_secret_redactions(
    *,
    sqlcipher_key_hex: str = "",
    proxy_url: str = "",
) -> tuple[str, ...]:
    tokens = {sqlcipher_key_hex, proxy_url}
    if proxy_url:
        parsed = urlsplit(proxy_url)
        for credential in (parsed.username, parsed.password):
            if credential:
                decoded = unquote(credential)
                tokens.update(
                    {
                        credential,
                        decoded,
                        quote(decoded, safe=""),
                    }
                )
        if "@" in parsed.netloc:
            tokens.add(parsed.netloc.rsplit("@", 1)[0])
    return tuple(sorted((token for token in tokens if token), key=len, reverse=True))


class QueueProgressReporter(ProgressReporterPort):
    _MIN_EMIT_INTERVAL = 0.05

    def __init__(
        self,
        queue: Any,
        initial_state: ProgressState,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._queue = queue
        self._state = initial_state
        self._timing = ProgressTimingEstimator(clock=clock)
        self._last_emit = 0.0
        self._pending = False

    def __enter__(self) -> QueueProgressReporter:
        self._timing.start(self._state)
        self._emit()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def update(self, state: ProgressState) -> None:
        self._state = preserve_terminal_progress(self._state, state)
        self._timing.observe(self._state)
        self._emit()

    def stop(self) -> None:
        if self._pending:
            self._emit(force=True)

    def _emit(self, *, force: bool = False) -> None:
        payload = self._state.to_wire()
        payload["timing"] = self._timing.snapshot(self._state).to_wire()
        now = monotonic()
        if (
            not force
            and self._last_emit
            and now - self._last_emit < self._MIN_EMIT_INTERVAL
        ):
            self._pending = True
            return
        self._pending = False
        self._last_emit = now
        self._queue.put(
            {"type": "progress", "timestamp": utc_now(), "payload": payload}
        )


class QueueProgressReporterFactory(ProgressReporterFactoryPort):
    def __init__(self, queue: Any) -> None:
        self._queue = queue

    def create(
        self,
        initial_state: ProgressState,
    ) -> QueueProgressReporter:
        return QueueProgressReporter(self._queue, initial_state)
