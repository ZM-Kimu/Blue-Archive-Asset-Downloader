from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ba_downloader.application.contracts import (
    AssetsExtractCommand,
    CatalogRefreshCommand,
)
from ba_downloader.bootstrap.container import ExecutionScope
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import ArtifactCollector, NeverCancelled
from support.fixtures import build_execution_context


def _context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="cn",
        version="1.0.0",
        max_retries=1,
    )


def test_execution_scope_records_existing_output_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context(tmp_path)
    context.workspace.raw.mkdir(parents=True)
    context.workspace.extracted.mkdir(parents=True)

    class ExtractService:
        @staticmethod
        def run(_context: ExecutionContext, _options: object) -> object:
            return SimpleNamespace(warnings=())

    monkeypatch.setattr(
        ExecutionScope, "extract_service", lambda _self: ExtractService()
    )
    with ExecutionScope(
        context,
        cancellation=NeverCancelled(),
        artifacts=ArtifactCollector(),
    ) as scope:
        result = scope.execute(AssetsExtractCommand())

    assert result.context == context
    assert result.artifacts == (
        ("extracted", str(context.workspace.extracted.resolve())),
    )


def test_runtime_scope_closes_http_client_when_provider_construction_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context(tmp_path)

    class RecordingHttpClient:
        close_calls = 0

        def __init__(self, **_: object) -> None:
            pass

        def close(self) -> None:
            type(self).close_calls += 1

    def fail_provider(*_: object) -> object:
        raise RuntimeError("provider failed")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.http.ResilientHttpClient",
        RecordingHttpClient,
    )
    monkeypatch.setattr(
        "ba_downloader.bootstrap.container.DEFAULT_REGION_GATEWAY_REGISTRY.resolve",
        lambda _region: SimpleNamespace(
            catalog=SimpleNamespace(provider=fail_provider)
        ),
    )

    scope = ExecutionScope(context)
    with scope:
        with pytest.raises(RuntimeError):
            scope.execute(
                CatalogRefreshCommand(),
            )
        with pytest.raises(RuntimeError):
            scope.execute(
                CatalogRefreshCommand(),
            )

    assert RecordingHttpClient.close_calls == 1
