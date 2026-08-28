from typing import Protocol


class SystemMemoryProbePort(Protocol):
    def total_physical_memory(self) -> int | None: ...
