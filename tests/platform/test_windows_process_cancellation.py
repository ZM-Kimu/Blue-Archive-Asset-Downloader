from __future__ import annotations

import os
import time

import pytest

from ba_downloader.infrastructure.runtime.process_supervisor import (
    ProcessSupervisor,
    WorkerCommand,
)

pytestmark = [
    pytest.mark.windows,
    pytest.mark.skipif(os.name != "nt", reason="Windows process semantics required"),
]


def _non_cooperative_worker() -> None:
    time.sleep(60.0)


def test_spawned_workers_are_reaped_with_one_shared_shutdown_deadline() -> None:
    supervisor = ProcessSupervisor(
        [
            WorkerCommand(f"blocked-{index}", _non_cooperative_worker, ())
            for index in range(4)
        ]
    )
    supervisor.start()
    started = time.monotonic()
    stopped = False
    try:
        supervisor.stop(0.0)
        stopped = True
        elapsed = time.monotonic() - started
        assert not supervisor.is_alive
        assert elapsed < 4.0
        results = supervisor.close(0.0)
    finally:
        if not stopped:
            supervisor.stop(0.0)

    assert len(results) == 4
    assert all(result.status == "failed" for result in results)
