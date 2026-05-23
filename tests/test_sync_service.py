from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.application.services.sync import SyncService
from ba_downloader.domain.exceptions import DownloadError
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext


class StaticProvider:
    def __init__(self, result: RegionCatalogResult) -> None:
        self.result = result

    def get_capabilities(self) -> RegionCapabilities:
        return self.result.capabilities

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        _ = context
        return self.result


class FailingDownloader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def verify_and_download(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> None:
        _ = (resources, context)
        self.calls.append("verify_and_download")
        raise DownloadError("download incomplete")


class RecordingExtractService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("run")

    def run_post_download(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("run_post_download")


class RecordingSchemaWorkflow:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def dump(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("dump")

    def compile(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("compile")


class RecordingRuntimeAssetPreparer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def prepare(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("prepare")


class DummyRelationBuilder:
    def verify_relation_file(self, context: RuntimeContext) -> bool:
        _ = context
        return True

    def get_excel_resources(self, resources: AssetCollection) -> AssetCollection:
        return resources

    def build(self, context: RuntimeContext) -> None:
        _ = context

    def search(self, context: RuntimeContext, keywords: list[str]) -> list[str]:
        _ = context
        return keywords


class NullLogger:
    def info(self, message: str) -> None:
        _ = message

    def warn(self, message: str) -> None:
        _ = message

    def error(self, message: str) -> None:
        _ = message


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="gl",
        threads=1,
        version="1.0.0",
        raw_dir=str(tmp_path / "RawData"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _build_catalog(context: RuntimeContext) -> RegionCatalogResult:
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/Bundle/a.bundle",
        "Bundle/a.bundle",
        10,
        "deadbeef",
        "md5",
        AssetType.bundle,
    )
    return RegionCatalogResult(
        resources=resources,
        context=context,
        capabilities=RegionCapabilities(),
    )


def test_sync_does_not_extract_after_download_failure(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    downloader = FailingDownloader()
    extract_service = RecordingExtractService()
    schema_workflow = RecordingSchemaWorkflow()
    runtime_asset_preparer = RecordingRuntimeAssetPreparer()
    service = SyncService(
        StaticProvider(_build_catalog(context)),
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_workflow,
        runtime_asset_preparer,
        lambda _context: DummyRelationBuilder(),
        NullLogger(),
    )

    with pytest.raises(DownloadError, match="download incomplete"):
        service.run(context)

    assert downloader.calls == ["verify_and_download"]
    assert runtime_asset_preparer.calls == ["prepare"]
    assert schema_workflow.calls == ["dump", "compile"]
    assert extract_service.calls == []
