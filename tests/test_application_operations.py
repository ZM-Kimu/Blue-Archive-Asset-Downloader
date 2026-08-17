from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ba_downloader.application.operations import (
    ApplicationOperation,
    ApplicationOperationCommand,
    ApplicationOperationExecutor,
    ApplicationOperationHandlerResult,
)
from ba_downloader.bootstrap.container import ExecutionScope
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.execution import ArtifactCollector, NeverCancelled


def _context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="cn",
        threads=2,
        version="1.0.0",
        raw_dir=str(tmp_path / "raw"),
        extract_dir=str(tmp_path / "extracted"),
        temp_dir=str(tmp_path / "temp"),
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def test_operation_executor_records_existing_output_artifacts(tmp_path: Path) -> None:
    context = _context(tmp_path)
    Path(context.raw_dir).mkdir()
    Path(context.extract_dir).mkdir()

    class Handler:
        def execute(
            self,
            command: ApplicationOperationCommand,
        ) -> ApplicationOperationHandlerResult:
            assert command.operation is ApplicationOperation.extract
            return ApplicationOperationHandlerResult(context)

    result = ApplicationOperationExecutor(
        Handler(), NeverCancelled(), ArtifactCollector(), context
    ).execute(ApplicationOperationCommand(ApplicationOperation.extract))

    assert result.context == context
    assert result.artifacts == (
        ("extracted", str(Path(context.extract_dir).resolve())),
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
        with pytest.raises(RuntimeError, match="provider failed"):
            scope.execute(
                ApplicationOperationCommand(ApplicationOperation.catalog_refresh),
            )
        with pytest.raises(RuntimeError, match="one operation only"):
            scope.execute(
                ApplicationOperationCommand(ApplicationOperation.catalog_refresh),
            )

    assert RecordingHttpClient.close_calls == 1
