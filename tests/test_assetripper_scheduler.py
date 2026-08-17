from __future__ import annotations

from ba_downloader.infrastructure.extraction.assetripper.scheduler import (
    BundleBatchScheduler,
    SystemResourceSnapshot,
)


class FakeResourceProbe:
    def __init__(self, *, cpu_count: int, available_memory: int) -> None:
        self._snapshot = SystemResourceSnapshot(cpu_count, available_memory)

    def snapshot(self) -> SystemResourceSnapshot:
        return self._snapshot


def test_scheduler_uses_at_most_three_memory_safe_workers() -> None:
    gib = 1024**3
    scheduler = BundleBatchScheduler(
        FakeResourceProbe(cpu_count=16, available_memory=24 * gib)
    )

    decision = scheduler.decide([2 * gib, 2 * gib, 2 * gib, 2 * gib])

    assert decision.worker_count == 3
    assert decision.memory_reserve_bytes == 8 * gib
    assert decision.estimated_worker_bytes == 2 * gib


def test_scheduler_downgrades_parallelism_to_preserve_memory() -> None:
    gib = 1024**3
    scheduler = BundleBatchScheduler(
        FakeResourceProbe(cpu_count=16, available_memory=12 * gib)
    )

    decision = scheduler.decide([2 * gib, 2 * gib])

    assert decision.worker_count == 2


def test_scheduler_uses_one_worker_when_parallel_memory_reserve_is_unavailable() -> (
    None
):
    available_memory = 10_171_887_616
    estimated_worker_memory = 12_468_409_027 - 8 * 1024**3
    scheduler = BundleBatchScheduler(
        FakeResourceProbe(cpu_count=8, available_memory=available_memory)
    )

    decision = scheduler.decide([estimated_worker_memory] * 3)

    assert decision.worker_count == 1
    assert decision.available_memory_bytes == available_memory
