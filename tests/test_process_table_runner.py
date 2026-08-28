from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from queue import Queue
from threading import Event
from time import sleep

import pytest

import ba_downloader.infrastructure.extraction.process_table_runner as table_runner_module
from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.progress import ProgressState
from ba_downloader.infrastructure.extraction.errors import (
    ExtractionFailureError,
)
from ba_downloader.infrastructure.extraction.process_table_runner import (
    ProcessTableExtractionRunner,
    TableExtractionEvent,
    TableExtractionRunState,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.runtime.interrupts import (
    SignalInterruptState,
    install_interrupt_handler,
)
from support import RecordingLogger, RecordingProgressFactory, build_execution_context


class RecordingTableProgress:
    def __init__(self) -> None:
        self.states: list[ProgressState] = []

    def update(self, state: ProgressState) -> None:
        self.states.append(state)

    def stop(self) -> None:
        return None


def _failing_table_profile(
    _context: ExecutionContext,
    _database_source_identity: object | None = None,
) -> TableExtractionProfile:
    raise RuntimeError("profile construction failed")


def _blocking_table_profile(
    _context: ExecutionContext,
    _database_source_identity: object | None = None,
) -> TableExtractionProfile:
    while True:
        sleep(1.0)


class _CancelAfterStart:
    def is_cancelled(self) -> bool:
        return True

    def raise_if_cancelled(self) -> None:
        return None


def test_table_interrupt_policy_force_exits_on_repeated_signal() -> None:
    operations: list[str] = []

    class RecordingInterruptState(SignalInterruptState):
        def set(self) -> None:
            operations.append("set")
            super().set()

    interrupt_state = RecordingInterruptState()
    logger = RecordingLogger()

    with install_interrupt_handler(
        interrupt_state,
        logger,
        force_exit=lambda code: operations.append(f"exit:{code}"),
    ):
        signal.raise_signal(signal.SIGINT)
        signal.raise_signal(signal.SIGINT)

    assert interrupt_state.is_set()
    assert operations == ["set", "exit:130"]
    assert not logger.by_level("error")


def test_table_workers_do_not_receive_a_shared_cancellation_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_commands: list[object] = []

    class RecordingSupervisor:
        def __init__(self, commands: list[object], *, context: object) -> None:
            _ = context
            captured_commands.extend(commands)

    monkeypatch.setattr(table_runner_module, "ProcessSupervisor", RecordingSupervisor)
    runner = ProcessTableExtractionRunner(
        RecordingLogger(),
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
    )

    runner._build_supervisor(  # type: ignore[arg-type]
        Queue(),
        build_execution_context(tmp_path, region="jp"),
        Queue(),
        object(),
        2,
    )

    assert len(captured_commands) == 2
    assert all(command.arguments[-1] is None for command in captured_commands)  # type: ignore[attr-defined]


def _create_empty_flatbuffer_package(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "__init__.py").write_text(
        "from ._registry import FLATBUFFER_ENUMS, FLATBUFFER_TYPES\n",
        encoding="utf8",
    )
    (root / "_registry.py").write_text(
        "FLATBUFFER_TYPES = {}\nFLATBUFFER_ENUMS = {}\n",
        encoding="utf8",
    )


def test_process_table_runner_flushes_events_before_closing_workers(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = build_execution_context(tmp_path, region="jp")
    _create_empty_flatbuffer_package(context.workspace.flatbuffer_schemas)
    files = [f"unsupported-{index}.bytes" for index in range(200)]
    runner = ProcessTableExtractionRunner(
        logger,
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
    )

    runner.run(files, context, concurrency=2)

    assert logger.by_level("warn")


def test_process_table_runner_preserves_business_failure_after_worker_cleanup(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = build_execution_context(tmp_path, region="jp")
    runner = ProcessTableExtractionRunner(
        logger,
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
        table_profile_factory=_failing_table_profile,
    )

    with pytest.raises(ExtractionFailureError):
        runner.run(["broken.zip"], context, concurrency=2)

    assert logger.by_level("error")


def test_table_progress_tracks_the_oldest_active_file(tmp_path: Path) -> None:
    logger = RecordingLogger()
    runner = ProcessTableExtractionRunner(
        logger,
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
    )
    state = TableExtractionRunState([], set(), 2, {})
    progress = RecordingTableProgress()
    older = str(tmp_path / "older.zip")
    newer = str(tmp_path / "newer.zip")

    runner._handle_event(TableExtractionEvent("started", older), progress, state)
    runner._handle_event(TableExtractionEvent("started", newer), progress, state)
    runner._handle_event(
        TableExtractionEvent("progress", newer, "newer step"),
        progress,
        state,
    )

    assert progress.states[-1].item == "older.zip"

    runner._handle_event(TableExtractionEvent("done", older), progress, state)

    assert progress.states[-1].item == "newer.zip"
    assert progress.states[-1].message == "newer step"


def test_process_table_runner_immediately_reaps_workers_on_cancellation(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    progress_factory = RecordingProgressFactory()
    runner = ProcessTableExtractionRunner(
        logger,
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
        table_profile_factory=_blocking_table_profile,
        progress_factory=progress_factory,
        cancellation=_CancelAfterStart(),
    )

    with pytest.raises(OperationCancelledError):
        runner.run(
            ["ExcelDB.db", "GroundStage.bytes"],
            build_execution_context(tmp_path, region="jp"),
            concurrency=2,
        )

    states = progress_factory.reporters[0].states
    assert states[-1].stage == "cancelled"
    assert sum(state.stage == "cancelled" for state in states) == 1
    assert not logger.by_level("error")


@pytest.mark.skipif(os.name != "nt", reason="Windows process-signal regression")
def test_windows_spawn_workers_exit_after_parent_interrupt() -> None:
    probe = Path(__file__).parent / "support" / "table_interrupt_probe.py"
    process = subprocess.Popen(
        [sys.executable, str(probe)],
        cwd=Path(__file__).parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=10.0)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            text=True,
        )
        stdout, stderr = process.communicate(timeout=5.0)
        pytest.fail(f"Table interrupt probe timed out.\n{stdout}\n{stderr}")

    assert process.returncode == 0, f"{stdout}\n{stderr}"
    assert "Traceback" not in stderr


def test_table_event_drain_is_bounded_and_observes_cancellation() -> None:
    runner = ProcessTableExtractionRunner(
        RecordingLogger(),
        poll_interval_seconds=0.001,
        interrupt_grace_seconds=2.0,
    )
    events: Queue[TableExtractionEvent] = Queue()
    for index in range(5):
        events.put(TableExtractionEvent("started", f"table-{index}.db"))
    state = TableExtractionRunState([], set(), 5, {})
    stop_event = Event()

    runner._drain_events(  # type: ignore[arg-type]
        events,
        None,
        state,
        stop_event=stop_event,
        max_events=2,
    )
    assert len(state.active_files) == 2

    stop_event.set()
    runner._drain_events(  # type: ignore[arg-type]
        events,
        None,
        state,
        stop_event=stop_event,
        max_events=2,
    )
    assert len(state.active_files) == 2


def test_table_queue_finalization_never_waits_for_feeder_thread() -> None:
    calls: list[str] = []

    class QueueWithBlockedFeeder:
        def cancel_join_thread(self) -> None:
            calls.append("cancel")

        def close(self) -> None:
            calls.append("close")

        def join_thread(self) -> None:
            raise AssertionError("join_thread must not be called")

    ProcessTableExtractionRunner._finalize_queue(  # type: ignore[arg-type]
        QueueWithBlockedFeeder(),
        cancelled=False,
    )

    assert calls == ["cancel", "close"]
