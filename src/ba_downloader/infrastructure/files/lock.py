from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from time import sleep
from typing import BinaryIO, cast

from ba_downloader.infrastructure.files.atomic import write_json_atomic


class InterprocessLockBusyError(RuntimeError):
    pass


class InterprocessFileLock(AbstractContextManager["InterprocessFileLock"]):
    """Hold a non-blocking OS lock while leaving diagnostic metadata on disk."""

    def __init__(self, path: Path, *, operation: str) -> None:
        self._path = path
        self._owner_path = path.with_name(f"{path.name}.owner.json")
        self._operation = operation
        self._stream: BinaryIO | None = None

    def __enter__(self) -> InterprocessFileLock:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        stream = self._path.open("a+b")
        try:
            self._acquire(stream)
        except OSError as exc:
            stream.close()
            owner = self._read_owner()
            detail = f" ({owner})" if owner else ""
            raise InterprocessLockBusyError(
                f"{self._operation} is already running{detail}."
            ) from exc
        self._stream = stream
        try:
            self._write_owner(stream)
        except BaseException:
            self._stream = None
            try:
                self._release(stream)
            finally:
                stream.close()
            raise
        return self

    def __exit__(self, *_: object) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            try:
                self._owner_path.unlink(missing_ok=True)
            finally:
                self._release(stream)
        finally:
            stream.close()

    @staticmethod
    def _acquire(stream: BinaryIO) -> None:
        stream.seek(0)
        if stream.read(1) == b"":
            stream.write(b"\0")
            stream.flush()
            os.fsync(stream.fileno())
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            return
        fcntl_module = import_module("fcntl")
        flock = cast(Callable[[int, int], None], fcntl_module.flock)
        lock_ex = int(fcntl_module.LOCK_EX)
        lock_nb = int(fcntl_module.LOCK_NB)
        flock(stream.fileno(), lock_ex | lock_nb)

    @staticmethod
    def _release(stream: BinaryIO) -> None:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            return
        fcntl_module = import_module("fcntl")
        flock = cast(Callable[[int, int], None], fcntl_module.flock)
        flock(stream.fileno(), int(fcntl_module.LOCK_UN))

    def _write_owner(self, stream: BinaryIO) -> None:
        _ = stream
        write_json_atomic(
            self._owner_path,
            {
                "operation": self._operation,
                "pid": os.getpid(),
                "started_at": datetime.now(UTC).isoformat(),
            },
            separators=(",", ":"),
        )

    def _read_owner(self) -> str:
        try:
            payload = json.loads(self._owner_path.read_text(encoding="utf8"))
        except (OSError, ValueError):
            return ""
        if not isinstance(payload, dict):
            return ""
        pid = payload.get("pid")
        operation = payload.get("operation")
        if not isinstance(pid, int) or not isinstance(operation, str):
            return ""
        return f"operation={operation}, pid={pid}"


@contextmanager
def wait_for_interprocess_lock(
    path: Path,
    *,
    operation: str,
    cancellation_check: Callable[[], None],
) -> Iterator[object]:
    lock = InterprocessFileLock(path, operation=operation)
    while True:
        cancellation_check()
        try:
            lock.__enter__()
        except InterprocessLockBusyError:
            sleep(0.1)
            continue
        break
    try:
        yield lock
    finally:
        lock.__exit__(None, None, None)
