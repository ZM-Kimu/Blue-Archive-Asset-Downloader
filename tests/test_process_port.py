from __future__ import annotations

import pytest

from ba_downloader.domain.ports.process import ProcessCommand, ProcessResult


def test_process_command_and_result_are_transport_neutral() -> None:
    command = ProcessCommand(("dotnet", "tool.dll", "--version"))
    result = ProcessResult(command, 0, "3.0.0\n", "")

    assert command.argv == ("dotnet", "tool.dll", "--version")
    assert result.stdout == "3.0.0\n"
    assert result.succeeded is True


@pytest.mark.parametrize("argv", [(), ("",), ("dotnet", "")])
def test_process_command_rejects_empty_arguments(argv: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="Process command arguments must not be empty"):
        ProcessCommand(argv)
