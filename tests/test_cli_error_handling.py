from types import SimpleNamespace

import pytest

from ba_downloader.cli.main import main
from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger


class ClosableHttpClient:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FailingExtractService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def run(self, context) -> None:  # type: ignore[no-untyped-def]
        _ = context
        raise self.error


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (
            LookupError(
                "Downloaded JP package is invalid or incomplete. Retry may solve the issue."
            ),
            "Downloaded JP package is invalid or incomplete.",
        ),
        (
            NetworkError("temporary failure"),
            "temporary failure",
        ),
    ],
)
def test_main_logs_operational_errors_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    expected_message: str,
) -> None:
    http_client = ClosableHttpClient()
    services = SimpleNamespace(
        logger=ConsoleLogger(),
        http_client=http_client,
    )

    monkeypatch.setattr(
        "ba_downloader.cli.main._build_cli_runtime_services",
        lambda context: services,
    )
    monkeypatch.setattr(
        "ba_downloader.cli.main._run_command",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )

    exit_code = main(["download", "--region", "jp"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert expected_message in captured.err
    assert "Traceback" not in captured.err
    assert http_client.closed is True


def test_main_logs_extract_bootstrap_errors_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    http_client = ClosableHttpClient()
    error = LookupError(
        "JP table extract prerequisites were missing and auto-generation was attempted."
    )
    services = SimpleNamespace(
        logger=ConsoleLogger(),
        http_client=http_client,
        extract_service=FailingExtractService(error),
    )

    monkeypatch.setattr(
        "ba_downloader.cli.main._build_cli_runtime_services",
        lambda context: services,
    )

    exit_code = main(["extract", "--region", "jp", "--platform", "windows"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "JP table extract prerequisites were missing" in captured.err
    assert "Traceback" not in captured.err
    assert http_client.closed is True
