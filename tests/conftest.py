from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.workspace import WorkspaceLayout


class RecordingLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)


@pytest.fixture
def context_factory(tmp_path: Path) -> Callable[..., ExecutionContext]:
    def create(
        *,
        region: str = "jp",
        platform: str = "android",
        resource_version: str | None = "test-version",
    ) -> ExecutionContext:
        workspace = WorkspaceLayout.create(tmp_path, region, platform)  # type: ignore[arg-type]
        return ExecutionContext(
            region,  # type: ignore[arg-type]
            platform,  # type: ignore[arg-type]
            workspace,
            max_retries=0,
            resource_version=resource_version,
        )

    return create


@pytest.fixture
def recording_logger() -> RecordingLogger:
    return RecordingLogger()
