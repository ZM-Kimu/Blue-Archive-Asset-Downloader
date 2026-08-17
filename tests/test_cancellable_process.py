from __future__ import annotations

import sys
import threading
import time

import pytest

from ba_downloader.domain.exceptions import (
    OperationCancelledError,
    ProcessExecutionError,
)
from ba_downloader.domain.ports.execution import EventCancellation
from ba_downloader.domain.ports.process import (
    ProcessCommand,
    ProcessOutputLine,
    ProcessResult,
)
from ba_downloader.infrastructure.runtime.process import CancellableProcessRunner


def test_process_runner_terminates_running_command_when_cancelled() -> None:
    cancellation_event = threading.Event()
    runner = CancellableProcessRunner(
        EventCancellation(cancellation_event),
        poll_interval_seconds=0.02,
        terminate_grace_seconds=0.5,
    )
    timer = threading.Timer(0.1, cancellation_event.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(OperationCancelledError):
            runner.run(
                ProcessCommand((sys.executable, "-c", "import time; time.sleep(30)"))
            )
    finally:
        timer.cancel()

    assert time.monotonic() - started < 5


def test_process_runner_preserves_failed_command_output() -> None:
    runner = CancellableProcessRunner()

    with pytest.raises(ProcessExecutionError) as error:
        runner.run(
            ProcessCommand(
                (
                    sys.executable,
                    "-c",
                    "import sys; print('failed', file=sys.stderr); raise SystemExit(7)",
                )
            )
        )

    assert error.value.returncode == 7
    assert error.value.stderr.strip() == "failed"


def test_process_runner_streams_output_before_command_exits() -> None:
    runner = CancellableProcessRunner(poll_interval_seconds=0.01)
    first_output = threading.Event()
    outputs: list[ProcessOutputLine] = []
    observer_threads: list[int] = []
    result: list[ProcessResult] = []

    class Observer:
        def on_output(self, output: ProcessOutputLine) -> None:
            outputs.append(output)
            observer_threads.append(threading.get_ident())
            first_output.set()

    def run_process() -> None:
        result.append(
            runner.run(
                ProcessCommand(
                    (
                        sys.executable,
                        "-c",
                        (
                            "import sys,time; "
                            "print('stdout-first', flush=True); "
                            "print('stderr-first', file=sys.stderr, flush=True); "
                            "time.sleep(0.5); "
                            "print('stdout-last', flush=True)"
                        ),
                    )
                ),
                output_observer=Observer(),
            )
        )

    worker = threading.Thread(target=run_process)
    worker.start()
    assert first_output.wait(timeout=2.0)
    assert worker.is_alive()
    worker.join(timeout=5.0)

    assert not worker.is_alive()
    assert {item.stream for item in outputs} == {"stdout", "stderr"}
    assert {item.text for item in outputs} == {
        "stdout-first",
        "stderr-first",
        "stdout-last",
    }
    assert observer_threads == [worker.ident] * len(observer_threads)
    completed = result[0]
    assert completed.stdout == "stdout-first\nstdout-last\n"
    assert completed.stderr == "stderr-first\n"


def test_process_runner_drains_large_stdout_and_stderr_without_deadlock() -> None:
    runner = CancellableProcessRunner(poll_interval_seconds=0.01)
    outputs: list[ProcessOutputLine] = []

    class Observer:
        def on_output(self, output: ProcessOutputLine) -> None:
            outputs.append(output)

    completed = runner.run(
        ProcessCommand(
            (
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "[(print(f'out-{i}'), print(f'err-{i}', file=sys.stderr)) "
                    "for i in range(2000)]"
                ),
            )
        ),
        output_observer=Observer(),
    )

    assert len(outputs) == 4000
    assert "out-1999" in completed.stdout
    assert "err-1999" in completed.stderr
