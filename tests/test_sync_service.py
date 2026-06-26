from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.application.use_cases.sync_assets import SyncAssetsUseCase
from ba_downloader.domain.exceptions import DownloadError
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.regions.jp.provider import JPRegionProvider


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


class RecordingDownloader:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def verify_and_download(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> None:
        _ = context
        self.calls.append([item.path for item in resources])


class RecordingExtractAssetsUseCase:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.resource_calls: list[list[str] | None] = []

    @staticmethod
    def _resource_paths(resources: AssetCollection | None) -> list[str] | None:
        if resources is None:
            return None
        return [item.path for item in resources]

    def run(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        _ = context
        self.calls.append("run")
        self.resource_calls.append(self._resource_paths(resources))

    def run_post_download(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        _ = context
        self.calls.append("run_post_download")
        self.resource_calls.append(self._resource_paths(resources))


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
    def __init__(self) -> None:
        self.search_calls: list[list[str]] = []
        self.search_results = ["Shiroko"]

    def verify_relation_file(self, context: RuntimeContext) -> bool:
        _ = context
        return True

    def get_excel_resources(self, resources: AssetCollection) -> AssetCollection:
        return resources

    def build(self, context: RuntimeContext) -> None:
        _ = context

    def search(self, context: RuntimeContext, keywords: list[str]) -> list[str]:
        _ = context
        self.search_calls.append(keywords)
        return self.search_results


class NullLogger:
    def info(self, message: str) -> None:
        _ = message

    def warn(self, message: str) -> None:
        _ = message

    def error(self, message: str) -> None:
        _ = message


class RecordingLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warn_messages: list[str] = []
        self.error_messages: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def warn(self, message: str) -> None:
        self.warn_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)


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


def _build_search_catalog(context: RuntimeContext) -> RegionCatalogResult:
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/Bundle/shiroko.bundle",
        "Bundle/Shiroko.bundle",
        10,
        "deadbeef",
        "md5",
        AssetType.bundle,
    )
    resources.add(
        "https://example.invalid/Bundle/other.bundle",
        "Bundle/Other.bundle",
        10,
        "deadbeef",
        "md5",
        AssetType.bundle,
    )
    return RegionCatalogResult(
        resources=resources,
        context=context,
        capabilities=JPRegionProvider.CAPABILITIES,
    )


def test_sync_does_not_extract_after_download_failure(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    downloader = FailingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_workflow = RecordingSchemaWorkflow()
    runtime_asset_preparer = RecordingRuntimeAssetPreparer()
    service = SyncAssetsUseCase(
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


def test_jp_sync_advanced_search_uses_relation_keywords(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(
        region="jp",
        advanced_search=("シロコ",),
    )
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_workflow = RecordingSchemaWorkflow()
    runtime_asset_preparer = RecordingRuntimeAssetPreparer()
    relation_builder = DummyRelationBuilder()
    service = SyncAssetsUseCase(
        StaticProvider(_build_search_catalog(context)),
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_workflow,
        runtime_asset_preparer,
        lambda _context: relation_builder,
        NullLogger(),
    )

    service.run(context)

    assert runtime_asset_preparer.calls == ["prepare"]
    assert schema_workflow.calls == ["dump", "compile"]
    assert relation_builder.search_calls == [["シロコ"]]
    assert downloader.calls == [["Bundle/Shiroko.bundle"]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_jp_sync_search_extracts_only_filtered_resources(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(
        region="jp",
        search=("Shiroko",),
    )
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_workflow = RecordingSchemaWorkflow()
    runtime_asset_preparer = RecordingRuntimeAssetPreparer()
    service = SyncAssetsUseCase(
        StaticProvider(_build_search_catalog(context)),
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_workflow,
        runtime_asset_preparer,
        lambda _context: DummyRelationBuilder(),
        NullLogger(),
    )

    service.run(context)

    assert downloader.calls == [["Bundle/Shiroko.bundle"]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_jp_sync_advanced_search_with_no_relation_matches_downloads_nothing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(
        region="jp",
        advanced_search=("thisnotavailidcharname",),
    )
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_workflow = RecordingSchemaWorkflow()
    runtime_asset_preparer = RecordingRuntimeAssetPreparer()
    relation_builder = DummyRelationBuilder()
    relation_builder.search_results = []
    logger = RecordingLogger()
    service = SyncAssetsUseCase(
        StaticProvider(_build_search_catalog(context)),
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_workflow,
        runtime_asset_preparer,
        lambda _context: relation_builder,
        logger,
    )

    service.run(context)

    assert relation_builder.search_calls == [["thisnotavailidcharname"]]
    assert downloader.calls == [[]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [[]]
    assert logger.warn_messages == [
        "Advanced search found no matching character relation entries."
    ]
