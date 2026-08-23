from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ba_downloader.application.contracts import AssetOperationOptions
from ba_downloader.application.profiles import RegionProfile
from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.application.use_cases.schema_preparation import (
    SchemaPreparationService,
)
from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
    build_application_region_profile,
)
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.asset_type_selection import ResourceTypeSelection
from ba_downloader.domain.models.character import CharacterIndex, CharacterIndexEntry
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.extraction import ExtractionReport
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.infrastructure.extraction.table.prerequisites import (
    TableExtractionPrerequisite,
)
from support import DummyCharacterIndexBuilder, RecordingLogger, StaticProvider
from support.fixtures import build_execution_context


class RecordingExtractionWorkflow:
    def __init__(self, warnings: tuple[str, ...] = ()) -> None:
        self.calls: list[str] = []
        self.resource_calls: list[list[str] | None] = []
        self.bundle_filter_modes: list[bool] = []
        self.warnings = warnings

    @staticmethod
    def _resource_paths(resources: AssetCollection | None) -> list[str] | None:
        if resources is None:
            return None
        return [item.path for item in resources]

    def extract_tables(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
    ) -> ExtractionReport:
        _ = (context, concurrency)
        self.calls.append("extract_tables")
        self.resource_calls.append(self._resource_paths(resources))
        return ExtractionReport(self.warnings)

    def extract_bundles(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
        filtered: bool = False,
    ) -> ExtractionReport:
        _ = (context, concurrency)
        self.calls.append("extract_bundles")
        self.resource_calls.append(self._resource_paths(resources))
        self.bundle_filter_modes.append(filtered)
        return ExtractionReport(self.warnings)

    def extract_media(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
    ) -> ExtractionReport:
        _ = (context, concurrency)
        self.calls.append("extract_media")
        self.resource_calls.append(self._resource_paths(resources))
        return ExtractionReport(self.warnings)


class FailingProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls: list[ExecutionContext] = []

    def get_capabilities(self) -> RegionCapabilities:
        return RegionCapabilities()

    def load_catalog(self, context: ExecutionContext) -> RegionCatalogResult:
        self.calls.append(context)
        raise self.error


class RecordingTableMetadataStore:
    def __init__(self, loaded: AssetCollection | None = None) -> None:
        self.loaded = loaded
        self.load_calls: list[ExecutionContext] = []
        self.write_calls: list[tuple[ExecutionContext, AssetCollection]] = []

    def load(self, context: ExecutionContext) -> AssetCollection | None:
        self.load_calls.append(context)
        return self.loaded

    def write(self, context: ExecutionContext, resources: AssetCollection) -> None:
        self.write_calls.append((context, resources))


class RecordingRuntimeAssetPreparer:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def prepare(self, context: ExecutionContext) -> PreparedRuntimeAssets:
        self.calls.append("prepare")
        root = context.workspace.temp_state / "test" / "Runtime"
        return PreparedRuntimeAssets(
            version=context.resource_version or "test",
            root_dir=root,
            binary_path=root / "libil2cpp.so",
            metadata_path=root / "global-metadata.dat",
        )


class RecordingSchemaWorkflow:
    def __init__(
        self,
        calls: list[str],
        *,
        fail_on: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls = calls
        self.fail_on = fail_on
        self.error = error

    def dump(
        self,
        context: ExecutionContext,
        runtime_assets: PreparedRuntimeAssets,
    ) -> None:
        _ = runtime_assets
        self.calls.append("dump")
        if self.fail_on == "dump" and self.error is not None:
            raise self.error
        dump_dir = context.workspace.dumps
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / "dump.cs").write_text("// generated", encoding="utf8")

    def compile(self, context: ExecutionContext) -> None:
        self.calls.append("compile")
        if self.fail_on == "compile" and self.error is not None:
            raise self.error
        _create_table_schema_directories(context)


def _build_context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="jp",
        version="",
        max_retries=1,
        platform="windows",
    )


def _options(
    *resources: str,
    filters: tuple[str, ...] = (),
) -> AssetOperationOptions:
    return AssetOperationOptions(
        concurrency=1,
        resources=ResourceTypeSelection.from_values(resources),
        asset_filter=AssetFilter.parse(filters),
    )


def _create_table_folder(context: ExecutionContext) -> None:
    table_dir = context.workspace.raw_tables
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / "Excel.zip").write_bytes(b"placeholder")


def _create_table_schema_directories(context: ExecutionContext) -> None:
    for schema_dir in (
        context.workspace.flatbuffer_schemas,
        context.workspace.memorypack_schemas,
    ):
        schema_dir.mkdir(parents=True, exist_ok=True)
        (schema_dir / "__init__.py").write_text("", encoding="utf8")
        (schema_dir / "_registry.py").write_text("", encoding="utf8")


def _create_dump_cs(context: ExecutionContext) -> None:
    dump_dir = context.workspace.dumps
    dump_dir.mkdir(parents=True, exist_ok=True)
    (dump_dir / "dump.cs").write_text("// generated", encoding="utf8")


def _build_filter_catalog(context: ExecutionContext) -> RegionCatalogResult:
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
        "https://example.invalid/Bundle/shiroko_missing.bundle",
        "Bundle/ShirokoMissing.bundle",
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


def _build_table_metadata_resources() -> AssetCollection:
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
    return resources


def _build_table_catalog(context: ExecutionContext) -> RegionCatalogResult:
    resources = _build_table_metadata_resources()
    resources.add(
        "https://example.invalid/Bundle/ignored.bundle",
        "Bundle/Ignored.bundle",
        10,
        "deadbeef",
        "md5",
        AssetType.bundle,
    )
    return RegionCatalogResult(resources=resources, context=context)


def _build_profile(
    context: ExecutionContext,
    provider: Any,
    logger: RecordingLogger,
    metadata_store: RecordingTableMetadataStore | None = None,
) -> RegionProfile:
    return build_application_region_profile(
        DEFAULT_REGION_GATEWAY_REGISTRY.resolve(context.region),
        logger=logger,
        table_metadata_store=metadata_store or RecordingTableMetadataStore(),
        provider=provider,
    )


def _build_noop_profile(context: ExecutionContext) -> RegionProfile:
    return _build_profile(
        context,
        StaticProvider(RegionCatalogResult(AssetCollection(), context)),
        RecordingLogger(),
    )


def _create_existing_bundle(context: ExecutionContext, name: str) -> None:
    bundle_dir = context.workspace.raw_bundles
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / name).write_bytes(b"bundle")


def _create_existing_table(context: ExecutionContext, name: str) -> None:
    table_dir = context.workspace.raw_tables
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / name).write_bytes(b"table")


def _build_jp_prerequisite_service(
    calls: list[str],
    *,
    fail_on: str | None = None,
    error: Exception | None = None,
) -> TableExtractionPrerequisite:
    return TableExtractionPrerequisite(
        SchemaPreparationService(
            RecordingSchemaWorkflow(calls, fail_on=fail_on, error=error),
            RecordingRuntimeAssetPreparer(calls),
        ),
        region="JP",
        logger=RecordingLogger(),
    )


def test_extract_service_skips_bootstrap_when_flatbufferdata_exists(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    _create_table_schema_directories(context)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        prerequisite_service=_build_jp_prerequisite_service(calls),
        workflow_profile=_build_noop_profile(context),
    )

    service.run(context, _options("table"), _build_table_metadata_resources())

    assert calls == []
    assert extraction_workflow.calls == ["extract_tables"]


def test_extract_service_compiles_when_dump_cs_exists_but_flatbufferdata_is_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    _create_dump_cs(context)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        prerequisite_service=_build_jp_prerequisite_service(calls),
        workflow_profile=_build_noop_profile(context),
    )

    service.run(context, _options("table"), _build_table_metadata_resources())

    assert calls == ["compile"]
    assert extraction_workflow.calls == ["extract_tables"]
    assert (context.workspace.flatbuffer_schemas / "_registry.py").is_file()


def test_extract_service_bootstraps_when_dump_cs_and_flatbufferdata_are_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        prerequisite_service=_build_jp_prerequisite_service(calls),
        workflow_profile=_build_noop_profile(context),
    )

    service.run(context, _options("table"), _build_table_metadata_resources())

    assert calls == ["prepare", "dump", "compile"]
    assert extraction_workflow.calls == ["extract_tables"]
    assert (context.workspace.dumps / "dump.cs").is_file()
    assert (context.workspace.flatbuffer_schemas / "__init__.py").is_file()


@pytest.mark.parametrize(
    ("fail_on", "error"),
    [
        (
            "dump",
            FileNotFoundError(
                "Cannot find binary file or global-metadata file for Cpp2IL backend."
            ),
        ),
        (
            "compile",
            LookupError("Failed to compile FlatBufferData from dump.cs."),
        ),
    ],
)
def test_extract_service_translates_jp_bootstrap_failures_to_lookup_error(
    tmp_path: Path,
    fail_on: str,
    error: Exception,
) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    if fail_on == "compile":
        _create_dump_cs(context)

    calls: list[str] = []
    service = ExtractAssetsUseCase(
        RecordingExtractionWorkflow(),
        prerequisite_service=_build_jp_prerequisite_service(
            calls,
            fail_on=fail_on,
            error=error,
        ),
        workflow_profile=_build_noop_profile(context),
    )

    with pytest.raises(LookupError) as exc_info:
        service.run(context, _options("table"), _build_table_metadata_resources())

    message = str(exc_info.value)
    if fail_on == "dump":
        assert str(context.workspace.temp_state) in message
        assert "global-metadata.dat" in message
        assert "GameAssembly.dll" in message
    else:
        assert str(context.workspace.extracted) in message


def test_extract_service_does_not_bootstrap_when_jp_table_folder_is_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        prerequisite_service=_build_jp_prerequisite_service(calls),
        workflow_profile=_build_noop_profile(context),
    )

    service.run(context, _options("table"))

    assert calls == []
    assert extraction_workflow.calls == []


def test_extract_service_plain_jp_table_uses_manifest_metadata_resources(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).resolve_resource_version("1.70.436321")
    _create_existing_table(context, "TablePatchPack_GroundStage_1.zip")
    extraction_workflow = RecordingExtractionWorkflow()
    metadata_store = RecordingTableMetadataStore(_build_table_metadata_resources())
    provider = StaticProvider(_build_table_catalog(context))
    logger = RecordingLogger()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        workflow_profile=_build_profile(context, provider, logger, metadata_store),
    )

    service.run(context, _options("table"))

    assert metadata_store.load_calls == [context]
    assert extraction_workflow.calls == ["extract_tables"]
    assert extraction_workflow.resource_calls == [
        ["Table/TablePatchPack_GroundStage_1.zip"]
    ]


def test_extract_service_plain_jp_table_rebuilds_missing_manifest_from_catalog(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).resolve_resource_version("1.70.436321")
    _create_existing_table(context, "TablePatchPack_GroundStage_1.zip")
    extraction_workflow = RecordingExtractionWorkflow()
    metadata_store = RecordingTableMetadataStore()
    provider = StaticProvider(_build_table_catalog(context))
    logger = RecordingLogger()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        provider=provider,
        logger=logger,
        workflow_profile=_build_profile(context, provider, logger, metadata_store),
    )

    service.run(context, _options("table"))

    assert provider.calls == [context]
    assert metadata_store.write_calls == [(context, provider.result.resources)]
    assert extraction_workflow.calls == ["extract_tables"]
    assert extraction_workflow.resource_calls == [
        ["Table/TablePatchPack_GroundStage_1.zip"]
    ]


def test_extract_service_plain_jp_table_requires_manifest_or_catalog_metadata(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).resolve_resource_version("1.70.436321")
    _create_existing_table(context, "Excel.zip")
    extraction_workflow = RecordingExtractionWorkflow()
    logger = RecordingLogger()
    provider = FailingProvider(LookupError("offline"))
    metadata_store = RecordingTableMetadataStore()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        provider=provider,
        logger=logger,
        workflow_profile=_build_profile(context, provider, logger, metadata_store),
    )

    with pytest.raises(LookupError):
        service.run(context, _options("table"))

    assert provider.calls == [context]
    assert extraction_workflow.calls == []


def test_extract_service_search_extracts_only_existing_filtered_resources(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _create_existing_bundle(context, "Shiroko.bundle")
    _create_existing_bundle(context, "Other.bundle")
    extraction_workflow = RecordingExtractionWorkflow()
    provider = StaticProvider(_build_filter_catalog(context))
    logger = RecordingLogger()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        provider=provider,
        character_index_builder_factory=lambda _context: DummyCharacterIndexBuilder(),
        logger=logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    service.run(context, _options("bundle", filters=("path~Shiroko",)))

    assert extraction_workflow.calls == ["extract_bundles"]
    assert extraction_workflow.resource_calls == [["Bundle/Shiroko.bundle"]]
    assert extraction_workflow.bundle_filter_modes == [True]


def test_extract_service_advanced_search_filters_existing_resources(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _create_existing_bundle(context, "Shiroko.bundle")
    character_index_builder = DummyCharacterIndexBuilder(
        index=CharacterIndex(
            "1.70.436321",
            [
                CharacterIndexEntry(
                    10000,
                    names=["シロコ"],
                    file_aliases={"Shiroko"},
                )
            ],
        )
    )
    extraction_workflow = RecordingExtractionWorkflow()
    provider = StaticProvider(_build_filter_catalog(context))
    logger = RecordingLogger()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        provider=provider,
        character_index_builder_factory=lambda _context: character_index_builder,
        logger=logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    service.run(context, _options("bundle", filters=("name~シロコ",)))

    assert character_index_builder.verify_calls == 1
    assert extraction_workflow.calls == ["extract_bundles"]
    assert extraction_workflow.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_extract_service_advanced_search_requires_current_index_file(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).resolve_resource_version("1.70.436321")
    character_index_builder = DummyCharacterIndexBuilder(index_file_valid=False)
    extraction_workflow = RecordingExtractionWorkflow()
    provider = StaticProvider(_build_filter_catalog(context))
    logger = RecordingLogger()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        provider=provider,
        character_index_builder_factory=lambda _context: character_index_builder,
        logger=logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    with pytest.raises(LookupError) as exc_info:
        service.run(context, _options("bundle", filters=("name~シロコ",)))

    message = str(exc_info.value)
    assert "Character index file is missing or does not match" in message
    assert "ba-downloader index build --region jp`" in message
    assert "ba-downloader assets sync --region jp --filter name~<keyword>`" in message
    assert "--version" not in message
    assert character_index_builder.verify_calls == 1
    assert extraction_workflow.calls == []


def test_extract_service_advanced_search_respects_region_capabilities(
    tmp_path: Path,
) -> None:
    context = build_execution_context(
        tmp_path,
        region="cn",
        platform="android",
        version="1.0.0",
    )
    catalog = _build_filter_catalog(context)
    provider = StaticProvider(
        RegionCatalogResult(
            resources=catalog.resources,
            context=context,
        ),
        capabilities=RegionCapabilities(supports_advanced_search=False),
    )
    extraction_workflow = RecordingExtractionWorkflow()
    logger = RecordingLogger()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        provider=provider,
        character_index_builder_factory=lambda _context: DummyCharacterIndexBuilder(),
        logger=logger,
        workflow_profile=_build_profile(context, provider, logger),
    )

    with pytest.raises(LookupError):
        service.run(context, _options("bundle", filters=("name~シロコ",)))

    assert extraction_workflow.calls == []


def test_extract_service_returns_combined_extraction_warnings(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    warnings = (
        "[BUNDLE_BATCH_FAILED] batch-1 failed",
        "[BUNDLE_EXTRACTION_PARTIAL] partial output",
    )
    extraction_workflow = RecordingExtractionWorkflow(warnings)
    service = ExtractAssetsUseCase(
        extraction_workflow,
        workflow_profile=_build_noop_profile(context),
    )

    report = service.run(context, _options("bundle", "media"))

    assert extraction_workflow.calls == ["extract_bundles", "extract_media"]
    assert report.warnings == warnings + warnings
