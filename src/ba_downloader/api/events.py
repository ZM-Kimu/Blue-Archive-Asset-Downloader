from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import (
    ProgressReporterFactoryPort,
    ProgressReporterPort,
)


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

    def __init__(self, queue: Any, total: int, description: str) -> None:
        self._queue = queue
        self._total = total
        self._completed = 0
        self._description = description
        self._stage = "operation"
        self._unit = "items"
        self._status = ""
        self._secondary_status = ""
        self._last_emit = 0.0
        self._pending: dict[str, object] | None = None

    def __enter__(self) -> QueueProgressReporter:
        self._emit()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def advance(self, amount: int = 1) -> None:
        self._completed += amount
        self._emit()

    def set_total(self, total: int) -> None:
        self._total = total
        self._emit()

    def set_description(self, description: str) -> None:
        self._description = description
        self._emit()

    def set_status(self, status: str) -> None:
        self._status = status
        self._emit()

    def set_secondary_status(self, status: str) -> None:
        self._secondary_status = status
        self._emit()

    def set_progress(
        self,
        completed: int,
        total: int,
        *,
        stage: str,
        unit: str,
        status: str = "",
        secondary_status: str = "",
    ) -> None:
        self._completed = completed
        self._total = total
        self._stage = stage
        self._unit = unit
        self._status = status
        self._secondary_status = secondary_status
        self._emit()

    def set_failed_status(self, status: str) -> None:
        self._status = status
        self._emit(force=True)

    def set_completed(self, completed: int) -> None:
        self._completed = completed
        self._emit()

    def stop(self) -> None:
        if self._pending is not None:
            self._emit(force=True)

    def _emit(self, *, force: bool = False) -> None:
        payload: dict[str, object] = {
            "completed": self._completed,
            "total": self._total,
            "stage": self._stage,
            "unit": self._unit,
            "status": self._status,
            "secondary_status": self._secondary_status,
        }
        now = monotonic()
        if (
            not force
            and self._last_emit
            and now - self._last_emit < self._MIN_EMIT_INTERVAL
        ):
            self._pending = payload
            return
        if self._pending is not None:
            payload = self._pending | payload
            self._pending = None
        self._last_emit = now
        self._queue.put(
            {"type": "progress", "timestamp": utc_now(), "payload": payload}
        )


class QueueProgressReporterFactory(ProgressReporterFactoryPort):
    def __init__(self, queue: Any) -> None:
        self._queue = queue

    def create(
        self,
        total: int,
        description: str,
        *,
        download_mode: bool = False,
        extract_mode: bool = False,
    ) -> QueueProgressReporter:
        _ = (download_mode, extract_mode)
        return QueueProgressReporter(self._queue, total, description)
