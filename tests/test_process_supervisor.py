from __future__ import annotations

import multiprocessing
import signal
from contextlib import suppress
from time import monotonic, sleep
from typing import Any, Protocol

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


def _report_signal_handlers(result_queue: Any) -> None:
    sigbreak = getattr(signal, "SIGBREAK", None)
    result_queue.put(
        (
            signal.getsignal(signal.SIGINT) == signal.SIG_IGN,
            sigbreak is None or signal.getsignal(sigbreak) == signal.SIG_IGN,
        )
    )


def _non_cooperative_worker() -> None:
    while True:
        sleep(1.0)


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


def test_process_supervisor_workers_ignore_terminal_interrupts() -> None:
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    supervisor = ProcessSupervisor(
        [WorkerCommand("signals", _report_signal_handlers, (result_queue,))],
        context=context,
    )

    supervisor.start()
    ignored_handlers = result_queue.get(timeout=5.0)
    results = supervisor.close()
    result_queue.close()
    result_queue.join_thread()

    assert ignored_handlers == (True, True)
    assert results[0].status == "succeeded"


def test_process_supervisor_forcibly_stops_workers_as_one_cohort() -> None:
    context = multiprocessing.get_context("spawn")
    supervisor = ProcessSupervisor(
        [
            WorkerCommand(f"blocked-{index}", _non_cooperative_worker, ())
            for index in range(4)
        ],
        context=context,
    )
    supervisor.start()

    started = monotonic()
    supervisor.stop(0.0)
    elapsed = monotonic() - started
    workers_alive = supervisor.is_alive
    results = supervisor.close()

    assert elapsed < 3.0
    assert not workers_alive
    assert len(results) == 4
    assert all(result.status == "failed" for result in results)
