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
    ("error", "expected_message"),
    [
        (
            LookupError(
                "Downloaded JP package is invalid or incomplete. Retry may solve the issue."
            ),
            "Downloaded JP package is invalid or incomplete.",
        ),
        (NetworkError("temporary failure"), "temporary failure"),
        (
            DownloadError("Failed to download 2 files after retries."),
            "Failed to download 2 files after retries.",
        ),
    ],
)
def test_main_logs_operational_errors_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    expected_message: str,
) -> None:
    _install_executor(monkeypatch, RecordingExecutor(error))

    exit_code = main(["assets", "download", "--region", "jp"])
    captured = capsys.readouterr()

    assert exit_code == (2 if isinstance(error, (NetworkError, DownloadError)) else 1)
    assert expected_message in " ".join(captured.err.split())
    assert "Traceback" not in captured.err


def test_main_logs_extract_errors_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = LookupError(
        "JP table extract prerequisites were missing and auto-generation was attempted."
    )
    _install_executor(monkeypatch, RecordingExecutor(error))

    exit_code = main(["assets", "extract", "--region", "jp", "--platform", "windows"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "JP table extract prerequisites were missing" in captured.err
    assert "Traceback" not in captured.err


def test_download_command_uses_shared_operation_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = RecordingExecutor()
    _install_executor(monkeypatch, executor)

    assert main(["assets", "download", "--region", "jp"]) == 0
    assert len(executor.commands) == 1
    assert isinstance(executor.commands[0], AssetsDownloadCommand)
