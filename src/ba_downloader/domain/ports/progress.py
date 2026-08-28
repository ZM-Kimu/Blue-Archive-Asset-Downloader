from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from typing import Literal, Protocol

ProgressStage = Literal[
    "verifying",
    "downloading",
    "scanning",
    "cache_fill",
    "loading",
    "processing",
    "exporting",
    "extracting",
    "validating",
    "publishing",
    "complete",
    "failed",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class ProgressMeasure:
    completed: int
    total: int
    unit: str

    def __post_init__(self) -> None:
        if self.completed < 0 or self.total < 0 or self.completed > self.total:
            raise ValueError("Progress counts are invalid.")
        if not self.unit:
            raise ValueError("Progress unit must not be empty.")

    def to_wire(self) -> dict[str, object]:
        return {"completed": self.completed, "total": self.total, "unit": self.unit}


@dataclass(frozen=True, slots=True)
class ProgressGroup:
    id: str
    index: int
    total: int

    def __post_init__(self) -> None:
        if not self.id or self.index <= 0 or self.total <= 0 or self.index > self.total:
            raise ValueError("Progress group context is invalid.")

    def to_wire(self) -> dict[str, object]:
        return {"id": self.id, "index": self.index, "total": self.total}


@dataclass(frozen=True, slots=True)
class ProgressWorkers:
    active: int
    limit: int

    def __post_init__(self) -> None:
        if self.active < 0 or self.limit <= 0 or self.active > self.limit:
            raise ValueError("Progress worker counts are invalid.")

    def to_wire(self) -> dict[str, object]:
        return {"active": self.active, "limit": self.limit}


@dataclass(frozen=True, slots=True)
class ProgressState:
    label: str
    stage: ProgressStage
    overall: ProgressMeasure | None = None
    current: ProgressMeasure | None = None
    group: ProgressGroup | None = None
    item: str | None = None
    message: str | None = None
    workers: ProgressWorkers | None = None
    pending: int | None = None
    failures: int = 0
    eta_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("Progress label must not be empty.")
        if self.failures < 0:
            raise ValueError("Progress failure count must not be negative.")
        if self.pending is not None and self.pending < 0:
            raise ValueError("Progress pending count must not be negative.")
        if self.eta_seconds is not None and self.eta_seconds < 0:
            raise ValueError("Progress ETA must not be negative.")

    def to_wire(self) -> dict[str, object]:
        return {
            "schema_version": 0,
            "label": self.label,
            "stage": self.stage,
            "overall": self.overall.to_wire() if self.overall is not None else None,
            "current": self.current.to_wire() if self.current is not None else None,
            "group": self.group.to_wire() if self.group is not None else None,
            "item": self.item,
            "message": self.message,
            "workers": self.workers.to_wire() if self.workers is not None else None,
            "pending": self.pending,
            "failures": self.failures,
        }


class ProgressReporterPort(Protocol):
    def update(self, state: ProgressState) -> None: ...

    def stop(self) -> None: ...


class ProgressReporterFactoryPort(Protocol):
    def create(
        self,
        initial_state: ProgressState,
    ) -> AbstractContextManager[ProgressReporterPort]: ...


def preserve_terminal_progress(
    previous: ProgressState,
    current: ProgressState,
) -> ProgressState:
    """Keep the last trustworthy counters when a terminal transition omits them."""
    if current.stage not in {"complete", "failed", "cancelled"}:
        return current
    return replace(
        current,
        overall=current.overall or previous.overall,
        current=current.current or previous.current,
        group=current.group or previous.group,
        item=current.item or previous.item,
        message=current.message or previous.message,
        workers=current.workers or previous.workers,
        pending=current.pending if current.pending is not None else previous.pending,
        failures=max(current.failures, previous.failures),
    )
