from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from importlib import import_module
from pathlib import Path
from time import sleep
from typing import BinaryIO, cast


class InterprocessLockBusyError(RuntimeError):
    pass


class InterprocessFileLock(AbstractContextManager["InterprocessFileLock"]):
    """Hold a non-blocking OS lock for one operation."""

    def __init__(self, path: Path, *, operation: str) -> None:
        self._path = path
        self._operation = operation
        self._stream: BinaryIO | None = None

    def __enter__(self) -> InterprocessFileLock:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        stream = self._path.open("a+b")
        try:
            self._acquire(stream)
        except OSError as exc:
            stream.close()
            raise InterprocessLockBusyError(
                f"{self._operation} is already running."
            ) from exc
        self._stream = stream
        return self

    def __exit__(self, *_: object) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            self._release(stream)
        finally:
            stream.close()

    @staticmethod
    def _acquire(stream: BinaryIO) -> None:
        stream.seek(0)
        if stream.read(1) == b"":
            stream.write(b"\0")
            stream.flush()
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
