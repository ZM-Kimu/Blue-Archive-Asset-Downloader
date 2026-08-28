from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

import pytest

from ba_downloader.api.events import QueueProgressReporter
from ba_downloader.domain.ports.progress import ProgressMeasure, ProgressState
from ba_downloader.domain.services.progress_timing import ProgressTimingEstimator
from ba_downloader.infrastructure.runtime import interrupts
from ba_downloader.infrastructure.runtime.interrupts import install_interrupt_handler


class ManualClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class RecordingQueue:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    def put(self, item: dict[str, object]) -> None:
        self.items.append(item)


def test_timing_uses_only_overall_progress_and_preserves_elapsed_time() -> None:
    clock = ManualClock()
    estimator = ProgressTimingEstimator(clock=clock)
    initial = ProgressState(
        "Bundles", "exporting", overall=ProgressMeasure(0, 10, "groups")
    )
    estimator.start(initial)
    clock.value = 5.0
    estimator.observe(
        ProgressState(
            "Bundles",
            "exporting",
            overall=ProgressMeasure(0, 10, "groups"),
            current=ProgressMeasure(500, 1000, "assets"),
        )
    )
    assert estimator.snapshot(initial).rate_per_second is None

    clock.value = 10.0
    progressed = ProgressState(
        "Bundles", "exporting", overall=ProgressMeasure(2, 10, "groups")
    )
    estimator.observe(progressed)
    timing = estimator.snapshot(progressed)

    assert timing.elapsed_seconds == 10.0
    assert timing.rate_per_second == pytest.approx(0.2)
    assert timing.eta_seconds == pytest.approx(40.0)
    clock.value = 12.0
    validating = ProgressState(
        "Bundles", "validating", overall=ProgressMeasure(10, 10, "groups")
    )
    assert estimator.snapshot(validating).eta_seconds is None
    assert estimator.snapshot(validating).elapsed_seconds == 12.0


def test_queue_progress_emits_schema_zero_and_preserves_terminal_counts() -> None:
    clock = ManualClock()
    queue = RecordingQueue()
    initial = ProgressState(
        "Assets",
        "verifying",
        overall=ProgressMeasure(0, 3, "files"),
        pending=0,
    )
    with QueueProgressReporter(queue, initial, clock=clock) as reporter:
        clock.value = 2.0
        reporter.update(
            ProgressState(
                "Assets",
                "verifying",
                overall=ProgressMeasure(2, 3, "files"),
                pending=1,
            )
        )
        clock.value = 3.0
        reporter.update(ProgressState("Assets", "cancelled"))

    payload = queue.items[-1]["payload"]
    assert isinstance(payload, dict)
    assert payload["schema_version"] == 0
    assert payload["stage"] == "cancelled"
    assert payload["overall"] == {"completed": 2, "total": 3, "unit": "files"}
    assert payload["pending"] == 1
    assert payload["timing"] == {
        "elapsed_seconds": 3.0,
        "eta_seconds": None,
        "rate_per_second": 1.0,
    }


def test_repeated_interrupt_forces_exit_before_touching_state(
    recording_logger: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actions: list[str] = []

    class State:
        def set(self) -> None:
            actions.append("set")

    installed: dict[int, Any] = {}

    def set_signal(number: int, handler: Any) -> Any:
        installed[number] = handler
        return None

    monkeypatch.setattr(interrupts.signal, "getsignal", lambda number: "previous")
    monkeypatch.setattr(interrupts.signal, "signal", set_signal)
    manager: AbstractContextManager[None] = install_interrupt_handler(
        State(),  # type: ignore[arg-type]
        recording_logger,  # type: ignore[arg-type]
        force_exit=lambda code: actions.append(f"force:{code}"),
    )

    with manager:
        handler = installed[interrupts.signal.SIGINT]
        handler(interrupts.signal.SIGINT, None)
        handler(interrupts.signal.SIGINT, None)

    assert actions == ["set", "force:130"]
