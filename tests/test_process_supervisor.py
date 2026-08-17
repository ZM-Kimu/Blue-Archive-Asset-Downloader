from __future__ import annotations

import multiprocessing
from contextlib import suppress
from time import monotonic, sleep
from typing import Protocol

from ba_downloader.infrastructure.runtime.process_supervisor import (
    ProcessSupervisor,
    WorkerCommand,
)


def _complete_worker() -> None:
    return None


def _fail_worker() -> None:
    raise RuntimeError("worker failed")


class _StopEvent(Protocol):
    def is_set(self) -> bool: ...


def _wait_worker(stop_event: _StopEvent) -> None:
    while not stop_event.is_set():
        sleep(0.01)


def _delayed_worker() -> None:
    sleep(0.2)


def _wait_until_stopped(supervisor: ProcessSupervisor) -> None:
    deadline = monotonic() + 5.0
    while supervisor.is_alive and monotonic() < deadline:
        sleep(0.01)


def test_process_supervisor_receives_typed_terminal_results() -> None:
    context = multiprocessing.get_context("spawn")
    supervisor = ProcessSupervisor(
        [
            WorkerCommand("complete", _complete_worker, ()),
            WorkerCommand("failed", _fail_worker, ()),
        ],
        context=context,
    )

    supervisor.start()
    _wait_until_stopped(supervisor)
    results = supervisor.close()

    assert [(result.name, result.status) for result in results] == [
        ("complete", "succeeded"),
        ("failed", "failed"),
    ]
    assert results[1].error == "RuntimeError: worker failed"


def test_process_supervisor_stops_cooperative_worker() -> None:
    context = multiprocessing.get_context("spawn")
    stop_event = context.Event()
    supervisor = ProcessSupervisor(
        [WorkerCommand("waiting", _wait_worker, (stop_event,))],
        context=context,
    )
    supervisor.start()

    stop_event.set()
    supervisor.stop(1.0)
    results = supervisor.close()

    assert results[0].status == "succeeded"


def test_process_supervisor_close_waits_for_delayed_worker() -> None:
    context = multiprocessing.get_context("spawn")
    supervisor = ProcessSupervisor(
        [WorkerCommand("delayed", _delayed_worker, ())],
        context=context,
    )
    supervisor.start()

    results = supervisor.close(grace_seconds=1.0)

    assert len(results) == 1
    assert results[0].name == "delayed"
    assert results[0].status == "succeeded"


def test_process_supervisor_close_reaps_worker_after_grace_period() -> None:
    context = multiprocessing.get_context("spawn")
    stop_event = context.Event()
    supervisor = ProcessSupervisor(
        [WorkerCommand("waiting", _wait_worker, (stop_event,))],
        context=context,
    )
    supervisor.start()

    try:
        results = supervisor.close(grace_seconds=0.01)
    finally:
        stop_event.set()
        with suppress(ValueError):
            supervisor.stop(1.0)

    assert results[0].name == "waiting"
    assert results[0].status == "failed"
    assert results[0].error == "Worker exceeded its shutdown grace period."
