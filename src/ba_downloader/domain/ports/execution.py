from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ba_downloader.domain.exceptions import OperationCancelledError


class CancellationPort(Protocol):
    def is_cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...


class NeverCancelled:
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return None


class EventCancellation:
    def __init__(self, event: object) -> None:
        self._event = event

    def is_cancelled(self) -> bool:
        is_set = getattr(self._event, "is_set", None)
        return bool(is_set()) if callable(is_set) else False

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise OperationCancelledError("Operation cancelled.")


class ArtifactSinkPort(Protocol):
    def record(self, kind: str, path: Path) -> None: ...

    def snapshot(self) -> tuple[tuple[str, str], ...]: ...


class ArtifactCollector:
    def __init__(self) -> None:
        self._artifacts: list[tuple[str, str]] = []

    def record(self, kind: str, path: Path) -> None:
        artifact = (kind, str(path.resolve()))
        if artifact not in self._artifacts:
            self._artifacts.append(artifact)

    def snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._artifacts)
