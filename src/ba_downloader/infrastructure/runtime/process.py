from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Callable
from queue import Empty, Queue
from threading import Thread
from typing import IO, cast

from ba_downloader.domain.exceptions import ProcessExecutionError
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.process import (
    ProcessCommand,
    ProcessOutputLine,
    ProcessOutputObserverPort,
    ProcessResult,
)


class CancellableProcessRunner:
    def __init__(
        self,
        cancellation: CancellationPort | None = None,
        *,
        poll_interval_seconds: float = 0.1,
        terminate_grace_seconds: float = 1.0,
    ) -> None:
        self._cancellation = cancellation or NeverCancelled()
        self._poll_interval_seconds = poll_interval_seconds
        self._terminate_grace_seconds = terminate_grace_seconds

    def run(
        self,
        command: ProcessCommand,
        *,
        output_observer: ProcessOutputObserverPort | None = None,
    ) -> ProcessResult:
        self._cancellation.raise_if_cancelled()
        process = subprocess.Popen(
            list(command.argv),
            cwd=command.cwd,
            env=dict(command.environment) if command.environment is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf8",
            creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                if os.name == "nt"
                else 0
            ),
            start_new_session=os.name != "nt",
        )
        assert process.stdout is not None
        assert process.stderr is not None
        output_queue: Queue[tuple[str, str]] = Queue()
        readers = (
            self._start_reader("stdout", process.stdout, output_queue),
            self._start_reader("stderr", process.stderr, output_queue),
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        try:
            while process.poll() is None:
                self._cancellation.raise_if_cancelled()
                self._drain_output(
                    output_queue,
                    stdout_lines,
                    stderr_lines,
                    output_observer,
                )
                try:
                    process.wait(timeout=self._poll_interval_seconds)
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            self._terminate_process_tree(process)
            process.wait()
            for reader in readers:
                reader.join()
            raise

        for reader in readers:
            reader.join()
        self._drain_output(
            output_queue,
            stdout_lines,
            stderr_lines,
            output_observer,
        )

        completed = ProcessResult(
            command,
            process.returncode,
            "".join(stdout_lines),
            "".join(stderr_lines),
        )
        if completed.returncode:
            raise ProcessExecutionError(
                command.argv,
                completed.returncode,
                completed.stdout,
                completed.stderr,
            )
        self._cancellation.raise_if_cancelled()
        return completed

    @staticmethod
    def _start_reader(
        stream_name: str,
        stream: IO[str],
        output_queue: Queue[tuple[str, str]],
    ) -> Thread:
        def read_stream() -> None:
            for line in stream:
                output_queue.put((stream_name, line))

        reader = Thread(target=read_stream, daemon=True)
        reader.start()
        return reader

    @staticmethod
    def _drain_output(
        output_queue: Queue[tuple[str, str]],
        stdout_lines: list[str],
        stderr_lines: list[str],
        output_observer: ProcessOutputObserverPort | None,
    ) -> None:
        while True:
            try:
                stream, raw_line = output_queue.get_nowait()
            except Empty:
                return
            if stream == "stdout":
                stdout_lines.append(raw_line)
                output = ProcessOutputLine("stdout", raw_line.rstrip("\r\n"))
            else:
                stderr_lines.append(raw_line)
                output = ProcessOutputLine("stderr", raw_line.rstrip("\r\n"))
            if output_observer is not None:
                output_observer.on_output(output)

    def _terminate_process_tree(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            try:
                process.send_signal(int(vars(signal)["CTRL_BREAK_EVENT"]))
                process.wait(timeout=self._terminate_grace_seconds)
                return
            except (OSError, subprocess.TimeoutExpired):
                taskkill = subprocess.Popen(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    taskkill.wait(timeout=self._terminate_grace_seconds)
                except subprocess.TimeoutExpired:
                    taskkill.kill()
                    taskkill.wait()
                if process.poll() is None:
                    process.kill()
                return

        try:
            kill_process_group = cast(
                Callable[[int, int], None],
                vars(os)["killpg"],
            )
            kill_process_group(process.pid, signal.SIGTERM)
            process.wait(timeout=self._terminate_grace_seconds)
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            try:
                kill_process_group(
                    process.pid,
                    int(vars(signal).get("SIGKILL", signal.SIGTERM)),
                )
            except ProcessLookupError:
                return
            process.wait(timeout=self._terminate_grace_seconds)
