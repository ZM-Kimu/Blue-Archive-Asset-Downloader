from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ProcessCommand:
    argv: tuple[str, ...]
    cwd: Path | None = None
    environment: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.argv or any(not argument for argument in self.argv):
            raise ValueError("Process command arguments must not be empty.")


@dataclass(frozen=True, slots=True)
class ProcessResult:
    command: ProcessCommand
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True, slots=True)
class ProcessOutputLine:
    stream: Literal["stdout", "stderr"]
    text: str


class ProcessOutputObserverPort(Protocol):
    def on_output(self, output: ProcessOutputLine) -> None: ...


class ProcessRunnerPort(Protocol):
    def run(
        self,
        command: ProcessCommand,
        *,
        output_observer: ProcessOutputObserverPort | None = None,
    ) -> ProcessResult: ...
