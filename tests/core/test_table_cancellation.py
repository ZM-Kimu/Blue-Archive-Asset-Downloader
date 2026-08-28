from __future__ import annotations

from contextlib import AbstractContextManager

import pytest

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.ports.progress import ProgressState
from ba_downloader.infrastructure.extraction.process_table_runner import (
    ProcessTableExtractionRunner,
)


class CancelDuringMonitor:
    def raise_if_cancelled(self) -> None:
        return None

    def is_cancelled(self) -> bool:
        return True


class RecordingProgress(AbstractContextManager["RecordingProgress"]):
    def __init__(self, initial: ProgressState) -> None:
        self.states = [initial]

    def __enter__(self) -> RecordingProgress:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def update(self, state: ProgressState) -> None:
        self.states.append(state)

    def stop(self) -> None:
        return None


class RecordingProgressFactory:
    def __init__(self) -> None:
        self.reporter: RecordingProgress | None = None

    def create(self, initial_state: ProgressState) -> RecordingProgress:
        self.reporter = RecordingProgress(initial_state)
        return self.reporter


class FakeSupervisor:
    def __init__(self) -> None:
        self.is_alive = True
        self.stop_calls: list[float] = []
        self.close_calls: list[float] = []

    def start(self) -> None:
        return None

    def stop(self, grace_seconds: float) -> None:
        self.stop_calls.append(grace_seconds)
        self.is_alive = False

    def close(self, grace_seconds: float = 1.0) -> tuple[object, ...]:
        self.close_calls.append(grace_seconds)
        self.is_alive = False
        return ()


def test_api_cancellation_immediately_stops_table_workers_once(
    context_factory: object,
    recording_logger: object,
) -> None:
    progress_factory = RecordingProgressFactory()
    supervisor = FakeSupervisor()
    runner = ProcessTableExtractionRunner(
        recording_logger,  # type: ignore[arg-type]
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
        progress_factory=progress_factory,
        cancellation=CancelDuringMonitor(),
    )
    runner._build_supervisor = lambda *args, **kwargs: supervisor  # type: ignore[method-assign]

    with pytest.raises(OperationCancelledError, match="cancelled by user"):
        runner.run(
            ["ExcelDB.db", "GroundStage.db"],
            context_factory(),  # type: ignore[operator]
            concurrency=2,
        )

    assert supervisor.stop_calls == [0.0]
    assert supervisor.close_calls == [0.0]
    assert progress_factory.reporter is not None
    terminal = [
        state
        for state in progress_factory.reporter.states
        if state.stage == "cancelled"
    ]
    assert len(terminal) == 1
