from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from typing import Protocol

DEFAULT_MEMORY_RESERVE_BYTES = 8 * 1024 * 1024 * 1024
MAX_ASSETRIPPER_WORKERS = 3


@dataclass(frozen=True, slots=True)
class SystemResourceSnapshot:
    cpu_count: int
    available_memory_bytes: int


class SystemResourceProbePort(Protocol):
    def snapshot(self) -> SystemResourceSnapshot: ...


@dataclass(frozen=True, slots=True)
class BundleBatchScheduleDecision:
    worker_count: int
    available_memory_bytes: int
    memory_reserve_bytes: int
    estimated_worker_bytes: int


class DefaultSystemResourceProbe:
    def snapshot(self) -> SystemResourceSnapshot:
        cpu_count = max(1, os.cpu_count() or 1)
        available_memory = self._available_memory_bytes()
        return SystemResourceSnapshot(cpu_count, available_memory)

    @staticmethod
    def _available_memory_bytes() -> int:
        if os.name == "nt":

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.length = ctypes.sizeof(status)
            windll = getattr(ctypes, "windll", None)
            if windll is None or not windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)
            ):
                raise OSError("Could not query available system memory.")
            return int(status.available_physical)

        sysconf = getattr(os, "sysconf", None)
        if not callable(sysconf):
            raise OSError("Could not query available system memory.")
        page_size = sysconf("SC_PAGE_SIZE")
        available_pages = sysconf("SC_AVPHYS_PAGES")
        return int(page_size * available_pages)


class BundleBatchScheduler:
    def __init__(
        self,
        resource_probe: SystemResourceProbePort | None = None,
        *,
        memory_reserve_bytes: int = DEFAULT_MEMORY_RESERVE_BYTES,
    ) -> None:
        if memory_reserve_bytes < 0:
            raise ValueError("AssetRipper memory reserve must not be negative.")
        self._resource_probe = resource_probe or DefaultSystemResourceProbe()
        self._memory_reserve_bytes = memory_reserve_bytes

    def decide(
        self,
        batch_estimates: list[int] | tuple[int, ...],
    ) -> BundleBatchScheduleDecision:
        if not batch_estimates or any(value <= 0 for value in batch_estimates):
            raise ValueError("AssetRipper batch memory estimates must be positive.")
        resources = self._resource_probe.snapshot()
        estimated_worker_bytes = max(batch_estimates)
        usable_memory = resources.available_memory_bytes - self._memory_reserve_bytes
        memory_workers = max(1, usable_memory // estimated_worker_bytes)
        cpu_workers = max(1, resources.cpu_count // 2)
        worker_count = min(
            MAX_ASSETRIPPER_WORKERS,
            cpu_workers,
            len(batch_estimates),
            memory_workers,
        )
        return BundleBatchScheduleDecision(
            worker_count=int(worker_count),
            available_memory_bytes=resources.available_memory_bytes,
            memory_reserve_bytes=self._memory_reserve_bytes,
            estimated_worker_bytes=estimated_worker_bytes,
        )

    @staticmethod
    def estimate_batch_memory(loaded_bytes: int, entry_count: int) -> int:
        if loaded_bytes < 0 or entry_count < 0:
            raise ValueError("AssetRipper batch size estimates must not be negative.")
        fixed_overhead = 512 * 1024 * 1024
        entry_overhead = entry_count * 64 * 1024
        return fixed_overhead + loaded_bytes * 11 // 2 + entry_overhead
