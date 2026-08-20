from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

import pytest

from ba_downloader.application.contracts import (
    ApplicationCommand,
    AssetsDownloadCommand,
    OperationOutcome,
)
from ba_downloader.cli.main import main
from ba_downloader.domain.exceptions import DownloadError, NetworkError
from ba_downloader.domain.models.execution import ExecutionContext


class RecordingExecutor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.commands: list[ApplicationCommand] = []
        self.context: ExecutionContext | None = None

    def execute(
        self,
        command: ApplicationCommand,
    ) -> OperationOutcome:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        assert self.context is not None
        return OperationOutcome(self.context)


def _install_executor(
    monkeypatch: pytest.MonkeyPatch,
    executor: RecordingExecutor,
) -> None:
    @contextmanager
    def fake_scope(*args: object, **kwargs: object) -> Iterator[RecordingExecutor]:
        _ = (args, kwargs)
        executor.context = cast(ExecutionContext, args[0])
        yield executor

    monkeypatch.setattr(
        "ba_downloader.cli.main.ExecutionScope",
        fake_scope,
    )


@pytest.mark.parametrize(
    ("error", "expected_exit_code"),
    [
        (
            LookupError(
                "Downloaded JP package is invalid or incomplete. Retry may solve the issue."
            ),
            1,
        ),
        (NetworkError("temporary failure"), 2),
        (
            DownloadError("Failed to download 2 files after retries."),
            2,
        ),
    ],
)
def test_main_maps_operational_error_types_to_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_exit_code: int,
) -> None:
    _install_executor(monkeypatch, RecordingExecutor(error))

    exit_code = main(["assets", "download", "--region", "jp"])
    assert exit_code == expected_exit_code


def test_download_command_uses_shared_operation_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = RecordingExecutor()
    _install_executor(monkeypatch, executor)

    assert main(["assets", "download", "--region", "jp"]) == 0
    assert len(executor.commands) == 1
    assert isinstance(executor.commands[0], AssetsDownloadCommand)
