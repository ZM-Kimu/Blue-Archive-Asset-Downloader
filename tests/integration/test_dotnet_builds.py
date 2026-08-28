from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.infrastructure.extraction.assetripper.exporter import (
    AssetRipperBatchExporter,
    AssetRipperRuntimeMetadataInspector,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.extraction.media.exporter import (
    MediaArchiveExtractor,
)
from ba_downloader.infrastructure.extraction.media.source import (
    SharpZipLibSourceResolver,
)
from ba_downloader.infrastructure.runtime.process import CancellableProcessRunner

pytestmark = pytest.mark.dotnet


class OfflineHttpClient:
    def request(self, *args: object, **kwargs: object) -> object:
        raise AssertionError(".NET builds must use checked-out submodule sources.")

    def download_to_file(self, *args: object, **kwargs: object) -> object:
        raise AssertionError(".NET builds must not download fallback sources.")

    def close(self) -> None:
        return None


def test_production_dotnet_tools_build_from_checked_out_sources(
    context_factory: object,
    recording_logger: object,
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    assert (
        repository_root
        / "third_party"
        / "AssetRipper"
        / "Source"
        / "AssetRipper.Export.PrimaryContent"
        / "AssetRipper.Export.PrimaryContent.csproj"
    ).is_file(), "AssetRipper submodule must be checked out for the build job."
    assert (
        repository_root
        / "third_party"
        / "SharpZipLib"
        / "src"
        / "ICSharpCode.SharpZipLib"
        / "ICSharpCode.SharpZipLib.csproj"
    ).is_file(), "SharpZipLib submodule must be checked out for the build job."
    context = context_factory()  # type: ignore[operator]
    http = OfflineHttpClient()
    process_runner = CancellableProcessRunner()
    assetripper_source = AssetRipperSourceResolver(
        http,  # type: ignore[arg-type]
        recording_logger,  # type: ignore[arg-type]
        repository_root=repository_root,
    )
    exporter = AssetRipperBatchExporter(
        assetripper_source,
        process_runner,
        repository_root=repository_root,
        logger=recording_logger,  # type: ignore[arg-type]
    )
    inspector = AssetRipperRuntimeMetadataInspector(
        assetripper_source,
        process_runner,
        repository_root=repository_root,
        logger=recording_logger,  # type: ignore[arg-type]
    )
    media = MediaArchiveExtractor(
        process_runner,
        recording_logger,  # type: ignore[arg-type]
        source_resolver=SharpZipLibSourceResolver(
            http,  # type: ignore[arg-type]
            recording_logger,  # type: ignore[arg-type]
            repository_root=repository_root,
        ),
        repository_root=repository_root,
    )

    exporter.prepare(context)
    inspector.prepare(context)
    media_dll = media.prepare(context)
    exporter.prepare(context)
    inspector.prepare(context)
    assert media.prepare(context) == media_dll

    assert tuple(context.workspace.tools_cache.rglob("AssetRipperExporter.dll"))
    assert tuple(context.workspace.tools_cache.rglob("AssetRipperRuntimeInspector.dll"))
    assert media_dll.is_file()
