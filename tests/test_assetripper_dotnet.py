from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import NoReturn

import pytest

from ba_downloader.infrastructure.extraction.assetripper.exporter import (
    AssetRipperBatchExporter,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.runtime.process import CancellableProcessRunner
from support.fixtures import build_execution_context


class _OfflineHttpClient:
    def download_to_file(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError(
            "AssetRipper integration build must use the checked-out submodule"
        )


@pytest.mark.skipif(
    os.environ.get("BAAD_RUN_DOTNET_BUILD") != "1",
    reason="Set BAAD_RUN_DOTNET_BUILD=1 to run the AssetRipper .NET build.",
)
def test_assetripper_exporter_builds_against_validated_overlay(tmp_path: Path) -> None:
    assert shutil.which("dotnet") is not None, ".NET 10 SDK is required"
    repository = Path(__file__).parents[1]
    context = build_execution_context(tmp_path, region="jp", version="1")
    resolver = AssetRipperSourceResolver(
        _OfflineHttpClient(),  # type: ignore[arg-type]
        NullLogger(),
        repository_root=repository,
    )
    exporter = AssetRipperBatchExporter(
        resolver,
        CancellableProcessRunner(),
        repository_root=repository,
    )

    exporter.prepare(context)

    patched_source = resolver.resolve_patched(context)
    output = (
        context.workspace.tools_cache
        / "assetripper"
        / "exporter"
        / "AssetRipperExporter.dll"
    )
    assert (patched_source / "overlay.json").is_file()
    assert output.is_file()
    assert output.stat().st_size > 0
