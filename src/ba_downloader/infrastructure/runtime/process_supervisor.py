from __future__ import annotations

import multiprocessing
import signal
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any, Literal

WorkerTarget = Callable[..., None]


@dataclass(frozen=True, slots=True)
class WorkerCommand:
    name: str
    target: WorkerTarget
    arguments: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class WorkerTerminalResult:
    name: str
    status: Literal["succeeded", "failed"]
    error: str | None = None


@dataclass(slots=True)
class _WorkerHandle:
    command: WorkerCommand
    process: Any
    terminal: Any
    child_terminal: Any
    result: WorkerTerminalResult | None = None


def _run_worker(
    command: WorkerCommand,
    terminal: Any,
) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    sigbreak = getattr(signal, "SIGBREAK", None)
    if sigbreak is not None:
        signal.signal(sigbreak, signal.SIG_IGN)
    try:
        command.target(*command.arguments)
    except BaseException as exc:
        terminal.send(
            WorkerTerminalResult(
                command.name,
                "failed",
                f"{type(exc).__name__}: {exc}",
            )
        )
        raise
    else:
        terminal.send(WorkerTerminalResult(command.name, "succeeded"))
    finally:
        terminal.close()


class ProcessSupervisor:
    def __init__(
        self,
        commands: list[WorkerCommand],
        *,
        context: Any | None = None,
    ) -> None:
        process_context = context or multiprocessing.get_context("spawn")
        self._handles: list[_WorkerHandle] = []
        self._forced_workers: set[str] = set()
        self._stop_completed = False
        for command in commands:
            parent, child = process_context.Pipe(duplex=False)
            process = process_context.Process(
                name=command.name,
                target=_run_worker,
                args=(command, child),
            )
            self._handles.append(_WorkerHandle(command, process, parent, child))

    @property
    def is_alive(self) -> bool:
        return any(handle.process.is_alive() for handle in self._handles)

    def start(self) -> None:
        for handle in self._handles:
            handle.process.start()
            handle.child_terminal.close()

    def collect_terminal_results(self) -> tuple[WorkerTerminalResult, ...]:
        for handle in self._handles:
            if handle.result is not None or not handle.terminal.poll():
                continue
            try:
                handle.result = handle.terminal.recv()
            except EOFError:
                continue
        return tuple(
            handle.result for handle in self._handles if handle.result is not None
        )

    def stop(self, grace_seconds: float) -> None:
        if self._stop_completed:
            return

        self._wait_for_workers(max(grace_seconds, 0.0))
        live_handles = self._live_handles()
        for handle in live_handles:
            self._forced_workers.add(handle.command.name)
            handle.process.terminate()
        self._wait_for_workers(1.0, live_handles)

        surviving_handles = self._live_handles()
        for handle in surviving_handles:
            self._forced_workers.add(handle.command.name)
            handle.process.kill()
        self._wait_for_workers(1.0, surviving_handles)
        self._stop_completed = True

    def _live_handles(self) -> list[_WorkerHandle]:
        return [handle for handle in self._handles if handle.process.is_alive()]

    def _wait_for_workers(
        self,
        timeout: float,
        handles: list[_WorkerHandle] | None = None,
    ) -> None:
        deadline = monotonic() + max(timeout, 0.0)
        selected_handles = self._handles if handles is None else handles
        for handle in selected_handles:
            remaining = max(0.0, deadline - monotonic())
            handle.process.join(timeout=remaining)

    def close(self, grace_seconds: float = 1.0) -> tuple[WorkerTerminalResult, ...]:
        if not self._stop_completed:
            self.stop(grace_seconds)
        results = self.collect_terminal_results()
        normalized: list[WorkerTerminalResult] = []
        by_name = {result.name: result for result in results}
        for handle in self._handles:
            result = by_name.get(handle.command.name)
            if handle.command.name in self._forced_workers:
                result = WorkerTerminalResult(
                    handle.command.name,
                    "failed",
                    "Worker exceeded its shutdown grace period.",
                )
            elif result is None:
                exitcode = handle.process.exitcode
                detail = (
                    "Worker did not stop after forced termination."
                    if handle.process.is_alive()
                    else f"Worker exited with code {exitcode} without a terminal result."
                )
                result = WorkerTerminalResult(
                    handle.command.name,
                    "failed",
                    detail,
                )
            normalized.append(result)
            if not handle.process.is_alive():
                handle.terminal.close()
                handle.process.close()
        return tuple(normalized)
