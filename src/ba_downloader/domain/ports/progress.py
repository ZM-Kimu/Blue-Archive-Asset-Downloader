from typing import Protocol


class ProgressReporterPort(Protocol):
    def advance(self, amount: int = 1) -> None:
        ...

    def set_total(self, total: int) -> None:
        ...

    def set_description(self, description: str) -> None:
        ...

    def set_completed(self, completed: int) -> None:
        ...

    def stop(self) -> None:
        ...
