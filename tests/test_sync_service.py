from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.application.profiles import RegionProfile
from ba_downloader.application.use_cases.sync_assets import SyncAssetsUseCase
from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
    build_application_region_profile,
)
from ba_downloader.domain.exceptions import DownloadError
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
)
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from support import DummyCharacterIndexBuilder, RecordingLogger, StaticProvider


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


class RecordingTableMetadataStore:
    def __init__(self) -> None:
        self.write_calls: list[tuple[RuntimeContext, AssetCollection]] = []

    def load(self, context: RuntimeContext) -> AssetCollection | None:
        _ = context
        return None

    def write(self, context: RuntimeContext, resources: AssetCollection) -> None:
        self.write_calls.append((context, resources))


class RecordingSchemaPreparation:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def prepare(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("prepare")

    def compile(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("compile")


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
    )


def _build_table_catalog(context: RuntimeContext) -> RegionCatalogResult:
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/Table/TablePatchPack_GroundStage_1.zip",
        "Table/TablePatchPack_GroundStage_1.zip",
        10,
        "deadbeef",
        "crc",
        AssetType.table,
        {"includes": ["EN0010_VeryHard.zip"]},
    )
    return RegionCatalogResult(resources=resources, context=context)


def _build_profile(
    context: RuntimeContext,
    provider: StaticProvider,
    logger: RecordingLogger,
    metadata_store: RecordingTableMetadataStore | None = None,
) -> RegionProfile:
    return build_application_region_profile(
        DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(context.region),
        context,
        http_client=object(),
        logger=logger,
        table_metadata_store=metadata_store or RecordingTableMetadataStore(),
        provider=provider,
    )


def test_sync_does_not_extract_after_download_failure(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    downloader = FailingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_preparation = RecordingSchemaPreparation()
    provider = StaticProvider(_build_catalog(context))
    logger = RecordingLogger()
    service = SyncAssetsUseCase(
        provider,
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_preparation,
        lambda _context: DummyCharacterIndexBuilder(),
        logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    with pytest.raises(DownloadError, match="download incomplete"):
        service.run(context)

    assert downloader.calls == ["verify_and_download"]
    assert schema_preparation.calls == ["prepare"]
    assert extract_service.calls == []


def test_jp_sync_passes_catalog_resources_to_post_download_extract(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(
        region="jp",
        resource_type=("table",),
    )
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_preparation = RecordingSchemaPreparation()
    metadata_store = RecordingTableMetadataStore()
    provider = StaticProvider(_build_table_catalog(context))
    logger = RecordingLogger()
    service = SyncAssetsUseCase(
        provider,
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_preparation,
        lambda _context: DummyCharacterIndexBuilder(),
        logger,
        workflow_profile=_build_profile(context, provider, logger, metadata_store),
    )

    service.run(context)

    assert metadata_store.write_calls == [(context, provider.result.resources)]
    assert downloader.calls == [["Table/TablePatchPack_GroundStage_1.zip"]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [
        ["Table/TablePatchPack_GroundStage_1.zip"]
    ]


def test_jp_sync_advanced_search_uses_relation_keywords(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(
        region="jp",
        advanced_search=("シロコ",),
    )
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_preparation = RecordingSchemaPreparation()
    character_index_builder = DummyCharacterIndexBuilder()
    provider = StaticProvider(_build_search_catalog(context))
    logger = RecordingLogger()
    service = SyncAssetsUseCase(
        provider,
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_preparation,
        lambda _context: character_index_builder,
        logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    service.run(context)

    assert schema_preparation.calls == ["prepare"]
    assert character_index_builder.search_calls == [["シロコ"]]
    assert downloader.calls == [["Bundle/Shiroko.bundle"]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_jp_sync_advanced_search_builds_missing_relation(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(
        region="jp",
        advanced_search=("シロコ",),
    )
    excel_resources = AssetCollection()
    excel_resources.add(
        "https://example.invalid/Table/Excel.zip",
        "Table/Excel.zip",
        10,
        "deadbeef",
        "md5",
        AssetType.table,
    )
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_preparation = RecordingSchemaPreparation()
    character_index_builder = DummyCharacterIndexBuilder(
        index_file_valid=False,
        excel_resources=excel_resources,
    )
    provider = StaticProvider(_build_search_catalog(context))
    logger = RecordingLogger()
    service = SyncAssetsUseCase(
        provider,
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_preparation,
        lambda _context: character_index_builder,
        logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    service.run(context)

    assert schema_preparation.calls == ["prepare"]
    assert character_index_builder.build_calls == [context]
    assert character_index_builder.search_calls == [["シロコ"]]
    assert downloader.calls == [["Table/Excel.zip"], ["Bundle/Shiroko.bundle"]]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_jp_sync_search_extracts_only_filtered_resources(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(
        region="jp",
        search=("Shiroko",),
    )
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_preparation = RecordingSchemaPreparation()
    provider = StaticProvider(_build_search_catalog(context))
    logger = RecordingLogger()
    service = SyncAssetsUseCase(
        provider,
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_preparation,
        lambda _context: DummyCharacterIndexBuilder(),
        logger,
        workflow_profile=_build_profile(context, provider, logger),
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
    schema_preparation = RecordingSchemaPreparation()
    character_index_builder = DummyCharacterIndexBuilder()
    character_index_builder.search_results = []
    logger = RecordingLogger()
    provider = StaticProvider(_build_search_catalog(context))
    service = SyncAssetsUseCase(
        provider,
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_preparation,
        lambda _context: character_index_builder,
        logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    service.run(context)

    assert character_index_builder.search_calls == [["thisnotavailidcharname"]]
    assert downloader.calls == [[]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [[]]
    assert logger.by_level("warn") == [
        "Advanced search found no matching character index entries."
    ]
