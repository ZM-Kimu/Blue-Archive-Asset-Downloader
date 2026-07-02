from types import SimpleNamespace

import pytest

from ba_downloader.application.profiles import build_region_profile
from ba_downloader.bootstrap.container import (
    DownloadRuntimeServices,
    ExtractRuntimeServices,
)
from ba_downloader.cli.main import main
from ba_downloader.domain.exceptions import DownloadError, NetworkError
from ba_downloader.domain.models.asset import AssetCollection, RegionCapabilities
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger


class ClosableHttpClient:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FailingExtractAssetsUseCase:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def run(self, context) -> None:  # type: ignore[no-untyped-def]
        _ = context
        raise self.error


class DownloadProvider:
    def get_capabilities(self) -> RegionCapabilities:
        return RegionCapabilities()

    def load_catalog(self, context) -> RegionCatalogResult:  # type: ignore[no-untyped-def]
        return RegionCatalogResult(AssetCollection(), context)


class RecordingDownloader:
    def __init__(self) -> None:
        self.calls = 0

    def verify_and_download(self, resources, context) -> None:  # type: ignore[no-untyped-def]
        _ = (resources, context)
        self.calls += 1


class NoopTableMetadataStore:
    def load(self, context):  # type: ignore[no-untyped-def]
        _ = context
        return None

    def write(self, context, resources) -> None:  # type: ignore[no-untyped-def]
        _ = (context, resources)


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
    http_client = ClosableHttpClient()
    services = SimpleNamespace(
        logger=ConsoleLogger(),
        http_client=http_client,
    )

    monkeypatch.setattr(
        "ba_downloader.cli.main.build_download_runtime_services",
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
    provider = DownloadProvider()
    services = ExtractRuntimeServices(
        logger=ConsoleLogger(),
        http_client=http_client,
        provider=provider,
        extract_service=FailingExtractAssetsUseCase(error),
        workflow_profile=build_region_profile(
            context=SimpleNamespace(region="jp"),  # type: ignore[arg-type]
            provider=provider,
            logger=ConsoleLogger(),
            table_metadata_store=NoopTableMetadataStore(),
        ),
    )

    monkeypatch.setattr(
        "ba_downloader.cli.main.build_extract_runtime_services",
        lambda context: services,
    )

    exit_code = main(["extract", "--region", "jp", "--platform", "windows"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "JP table extract prerequisites were missing" in captured.err
    assert "Traceback" not in captured.err
    assert http_client.closed is True


def test_download_command_uses_download_only_runtime_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_client = ClosableHttpClient()
    downloader = RecordingDownloader()
    provider = DownloadProvider()
    services = DownloadRuntimeServices(
        logger=ConsoleLogger(),
        http_client=http_client,
        provider=provider,
        downloader=downloader,
        workflow_profile=build_region_profile(
            context=SimpleNamespace(region="jp"),  # type: ignore[arg-type]
            provider=provider,
            logger=ConsoleLogger(),
            table_metadata_store=NoopTableMetadataStore(),
        ),
    )

    monkeypatch.setattr(
        "ba_downloader.cli.main.build_download_runtime_services",
        lambda context: services,
    )

    assert main(["download", "--region", "jp"]) == 0
    assert downloader.calls == 1
    assert http_client.closed is True
