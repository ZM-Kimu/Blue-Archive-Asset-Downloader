from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.application.contracts.commands import AssetOperationOptions
from ba_downloader.application.profiles import RegionProfile
from ba_downloader.application.use_cases.sync_assets import SyncAssetsUseCase
from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
    build_application_region_profile,
)
from ba_downloader.domain.exceptions import DownloadError
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
)
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.asset_type_selection import ResourceTypeSelection
from ba_downloader.domain.models.character import CharacterIndex, CharacterIndexEntry
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.extraction import ExtractionReport
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.workspace import WorkspaceLayout
from support import DummyCharacterIndexBuilder, RecordingLogger, StaticProvider


class FailingDownloader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def verify_and_download(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        *,
        concurrency: int,
    ) -> None:
        _ = (resources, context, concurrency)
        self.calls.append("verify_and_download")
        raise DownloadError("download incomplete")


class RecordingDownloader:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def verify_and_download(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        *,
        concurrency: int,
    ) -> None:
        _ = (context, concurrency)
        self.calls.append([item.path for item in resources])


class RecordingExtractAssetsUseCase:
    def __init__(self, warnings: tuple[str, ...] = ()) -> None:
        self.calls: list[str] = []
        self.resource_calls: list[list[str] | None] = []
        self.warnings = warnings

    @staticmethod
    def _resource_paths(resources: AssetCollection | None) -> list[str] | None:
        if resources is None:
            return None
        return [item.path for item in resources]

    def run(
        self,
        context: ExecutionContext,
        options: AssetOperationOptions,
        resources: AssetCollection | None = None,
    ) -> ExtractionReport:
        _ = (context, options)
        self.calls.append("run")
        self.resource_calls.append(self._resource_paths(resources))
        return ExtractionReport(self.warnings)

    def run_post_download(
        self,
        context: ExecutionContext,
        options: AssetOperationOptions,
        resources: AssetCollection | None = None,
    ) -> ExtractionReport:
        _ = (context, options)
        self.calls.append("run_post_download")
        self.resource_calls.append(self._resource_paths(resources))
        return ExtractionReport(self.warnings)


class RecordingTableMetadataStore:
    def __init__(self) -> None:
        self.write_calls: list[tuple[ExecutionContext, AssetCollection]] = []

    def load(self, context: ExecutionContext) -> AssetCollection | None:
        _ = context
        return None

    def write(self, context: ExecutionContext, resources: AssetCollection) -> None:
        self.write_calls.append((context, resources))


class RecordingSchemaPreparation:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def prepare(self, context: ExecutionContext) -> None:
        _ = context
        self.calls.append("prepare")

    def compile(self, context: ExecutionContext) -> None:
        _ = context
        self.calls.append("compile")


def _build_context(
    tmp_path: Path,
    *,
    region: str = "gl",
    version: str = "1.0.0",
) -> ExecutionContext:
    return ExecutionContext(
        region=region,  # type: ignore[arg-type]
        platform="android",
        workspace=WorkspaceLayout.create(tmp_path, region, "android"),  # type: ignore[arg-type]
        max_retries=1,
        resource_version=version,
    )


def _options(
    *,
    resources: tuple[str, ...] = ("bundle",),
    filters: tuple[str, ...] = (),
) -> AssetOperationOptions:
    return AssetOperationOptions(
        concurrency=1,
        resources=ResourceTypeSelection.from_values(resources),
        asset_filter=AssetFilter.parse(filters),
    )


def _build_catalog(context: ExecutionContext) -> RegionCatalogResult:
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


def _build_search_catalog(context: ExecutionContext) -> RegionCatalogResult:
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


def _build_table_catalog(context: ExecutionContext) -> RegionCatalogResult:
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
    context: ExecutionContext,
    provider: StaticProvider,
    logger: RecordingLogger,
    metadata_store: RecordingTableMetadataStore | None = None,
) -> RegionProfile:
    return build_application_region_profile(
        DEFAULT_REGION_GATEWAY_REGISTRY.resolve(context.region),
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
        service.run(context, _options())

    assert downloader.calls == ["verify_and_download"]
    assert schema_preparation.calls == ["prepare"]
    assert extract_service.calls == []


def test_jp_sync_passes_catalog_resources_to_post_download_extract(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="jp")
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

    service.run(context, _options(resources=("table",)))

    assert metadata_store.write_calls == [(context, provider.result.resources)]
    assert downloader.calls == [["Table/TablePatchPack_GroundStage_1.zip"]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [
        ["Table/TablePatchPack_GroundStage_1.zip"]
    ]


def test_sync_returns_active_context_and_extraction_warnings(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    active_context = _build_context(tmp_path, version="2.0.0")
    warning = "[BUNDLE_EXTRACTION_PARTIAL] partial output"
    extract_service = RecordingExtractAssetsUseCase((warning,))
    provider = StaticProvider(_build_catalog(active_context))
    logger = RecordingLogger()
    service = SyncAssetsUseCase(
        provider,
        RecordingDownloader(),
        extract_service,  # type: ignore[arg-type]
        RecordingSchemaPreparation(),
        lambda _context: DummyCharacterIndexBuilder(),
        logger,
        workflow_profile=_build_profile(active_context, provider, logger),
    )

    result = service.run(context, _options())

    assert result.context == active_context
    assert result.extraction.warnings == (warning,)


def test_jp_sync_advanced_search_uses_character_index_keywords(tmp_path: Path) -> None:
    context = _build_context(tmp_path, region="jp")
    character_index_builder = DummyCharacterIndexBuilder(
        index=CharacterIndex(
            "JP1.0.0",
            [
                CharacterIndexEntry(
                    10000,
                    dev_name="Shiroko",
                    names=["シロコ"],
                    file_aliases={"Shiroko"},
                )
            ],
        )
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
        lambda _context: character_index_builder,
        logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    service.run(context, _options(filters=("name~シロコ",)))

    assert schema_preparation.calls == ["prepare"]
    assert downloader.calls == [["Bundle/Shiroko.bundle"]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_cn_sync_advanced_search_uses_character_index_keywords(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    character_index_builder = DummyCharacterIndexBuilder(
        index=CharacterIndex(
            "CN1.0.0",
            [
                CharacterIndexEntry(
                    10000,
                    dev_name="Shiroko",
                    names=["伊吹"],
                    file_aliases={"Shiroko"},
                )
            ],
        )
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
        lambda _context: character_index_builder,
        logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    service.run(context, _options(filters=("name~伊吹",)))

    assert schema_preparation.calls == ["prepare"]
    assert downloader.calls == [["Bundle/Shiroko.bundle"]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_jp_sync_advanced_search_builds_missing_character_index(tmp_path: Path) -> None:
    context = _build_context(tmp_path, region="jp")
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
        index=CharacterIndex(
            "JP1.0.0",
            [
                CharacterIndexEntry(
                    10000,
                    dev_name="Shiroko",
                    names=["シロコ"],
                    file_aliases={"Shiroko"},
                )
            ],
        ),
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

    service.run(context, _options(filters=("name~シロコ",)))

    assert schema_preparation.calls == ["prepare"]
    assert character_index_builder.build_calls == [context]
    assert downloader.calls == [["Table/Excel.zip"], ["Bundle/Shiroko.bundle"]]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_jp_sync_path_filter_extracts_only_matching_resources(tmp_path: Path) -> None:
    context = _build_context(tmp_path, region="jp")
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

    service.run(context, _options(filters=("path~Shiroko",)))

    assert downloader.calls == [["Bundle/Shiroko.bundle"]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_sync_applies_typed_character_filters(tmp_path: Path) -> None:
    context = _build_context(tmp_path, region="jp")
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_preparation = RecordingSchemaPreparation()
    builder = DummyCharacterIndexBuilder(
        index=CharacterIndex(
            "JP1.0.0",
            [
                CharacterIndexEntry(
                    10000,
                    dev_name="Shiroko",
                    names=["Shiroko"],
                    file_aliases={"Shiroko"},
                    school_en="Abydos",
                )
            ],
        )
    )
    provider = StaticProvider(_build_search_catalog(context))
    logger = RecordingLogger()
    service = SyncAssetsUseCase(
        provider,
        downloader,
        extract_service,  # type: ignore[arg-type]
        schema_preparation,
        lambda _context: builder,
        logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    service.run(
        context,
        _options(filters=("name~Shiroko", "school=Abydos")),
    )

    assert downloader.calls == [["Bundle/Shiroko.bundle"]]
    assert extract_service.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_jp_sync_character_filter_with_no_matches_downloads_nothing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="jp")
    downloader = RecordingDownloader()
    extract_service = RecordingExtractAssetsUseCase()
    schema_preparation = RecordingSchemaPreparation()
    character_index_builder = DummyCharacterIndexBuilder()
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

    service.run(
        context,
        _options(filters=("name~thisnotavailidcharname",)),
    )

    assert downloader.calls == [[]]
    assert extract_service.calls == ["run_post_download"]
    assert extract_service.resource_calls == [[]]
    assert logger.by_level("warn") == []
