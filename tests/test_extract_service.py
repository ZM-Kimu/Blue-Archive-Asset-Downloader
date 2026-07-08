from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ba_downloader.application.profiles import RegionProfile
from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.application.use_cases.schema_preparation import (
    SchemaPreparationService,
)
from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
    build_application_region_profile,
)
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.regions.jp.prerequisites import (
    JpTableExtractionPrerequisite,
)
from support import DummyCharacterIndexBuilder, RecordingLogger, StaticProvider


class RecordingExtractionWorkflow:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.resource_calls: list[list[str] | None] = []

    @staticmethod
    def _resource_paths(resources: AssetCollection | None) -> list[str] | None:
        if resources is None:
            return None
        return [item.path for item in resources]

    def extract_tables(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        _ = context
        self.calls.append("extract_tables")
        self.resource_calls.append(self._resource_paths(resources))

    def extract_bundles(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        _ = context
        self.calls.append("extract_bundles")
        self.resource_calls.append(self._resource_paths(resources))

    def extract_media(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        _ = context
        self.calls.append("extract_media")
        self.resource_calls.append(self._resource_paths(resources))


class FailingProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls: list[RuntimeContext] = []

    def get_capabilities(self) -> RegionCapabilities:
        return RegionCapabilities()

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        self.calls.append(context)
        raise self.error


class RecordingTableMetadataStore:
    def __init__(self, loaded: AssetCollection | None = None) -> None:
        self.loaded = loaded
        self.load_calls: list[RuntimeContext] = []
        self.write_calls: list[tuple[RuntimeContext, AssetCollection]] = []

    def load(self, context: RuntimeContext) -> AssetCollection | None:
        self.load_calls.append(context)
        return self.loaded

    def write(self, context: RuntimeContext, resources: AssetCollection) -> None:
        self.write_calls.append((context, resources))


class RecordingRuntimeAssetPreparer:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def prepare(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("prepare")


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

    def dump(self, context: RuntimeContext) -> None:
        self.calls.append("dump")
        if self.fail_on == "dump" and self.error is not None:
            raise self.error
        dump_dir = Path(context.extract_dir) / "Dumps"
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / "dump.cs").write_text("// generated", encoding="utf8")

    def compile(self, context: RuntimeContext) -> None:
        self.calls.append("compile")
        if self.fail_on == "compile" and self.error is not None:
            raise self.error
        flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
        flatbuffer_data_dir.mkdir(parents=True, exist_ok=True)
        (flatbuffer_data_dir / "__init__.py").write_text("", encoding="utf8")
        (flatbuffer_data_dir / "_registry.py").write_text("", encoding="utf8")


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=1,
        version="",
        raw_dir=str(tmp_path / "JP_Windows_RawData"),
        extract_dir=str(tmp_path / "JP_Windows_Extracted"),
        temp_dir=str(tmp_path / "JP_Windows_Temp"),
        extract_while_download=False,
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
        platform="windows",
    )


def _create_table_folder(context: RuntimeContext) -> None:
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / "Excel.zip").write_bytes(b"placeholder")


def _create_flat_buffer_data(context: RuntimeContext) -> None:
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    flatbuffer_data_dir.mkdir(parents=True, exist_ok=True)
    (flatbuffer_data_dir / "__init__.py").write_text("", encoding="utf8")
    (flatbuffer_data_dir / "_registry.py").write_text("", encoding="utf8")


def _create_dump_cs(context: RuntimeContext) -> None:
    dump_dir = Path(context.extract_dir) / "Dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    (dump_dir / "dump.cs").write_text("// generated", encoding="utf8")


def _build_filter_catalog(context: RuntimeContext) -> RegionCatalogResult:
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


def _build_table_catalog(context: RuntimeContext) -> RegionCatalogResult:
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
    context: RuntimeContext,
    provider: Any,
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


def _build_noop_profile(context: RuntimeContext) -> RegionProfile:
    return _build_profile(
        context,
        StaticProvider(RegionCatalogResult(AssetCollection(), context)),
        RecordingLogger(),
    )


def _create_existing_bundle(context: RuntimeContext, name: str) -> None:
    bundle_dir = Path(context.raw_dir) / "Bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / name).write_bytes(b"bundle")


def _create_existing_table(context: RuntimeContext, name: str) -> None:
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / name).write_bytes(b"table")


def _build_jp_prerequisite_service(
    calls: list[str],
    *,
    fail_on: str | None = None,
    error: Exception | None = None,
) -> JpTableExtractionPrerequisite:
    return JpTableExtractionPrerequisite(
        SchemaPreparationService(
            RecordingSchemaWorkflow(calls, fail_on=fail_on, error=error),
            RecordingRuntimeAssetPreparer(calls),
        ),
        RecordingLogger(),
    )


def test_extract_service_skips_bootstrap_when_flatbufferdata_exists(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    _create_flat_buffer_data(context)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        prerequisite_service=_build_jp_prerequisite_service(calls),
        workflow_profile=_build_noop_profile(context),
    )

    service.run(context, _build_table_metadata_resources())

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

    service.run(context, _build_table_metadata_resources())

    assert calls == ["compile"]
    assert extraction_workflow.calls == ["extract_tables"]
    assert (Path(context.extract_dir) / "FlatBufferData" / "_registry.py").is_file()


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

    service.run(context, _build_table_metadata_resources())

    assert calls == ["prepare", "dump", "compile"]
    assert extraction_workflow.calls == ["extract_tables"]
    assert (Path(context.extract_dir) / "Dumps" / "dump.cs").is_file()
    assert (Path(context.extract_dir) / "FlatBufferData" / "__init__.py").is_file()


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

    with pytest.raises(
        LookupError, match="JP table extract prerequisites were missing"
    ) as exc_info:
        service.run(context, _build_table_metadata_resources())

    message = str(exc_info.value)
    assert context.temp_dir in message
    assert "global-metadata.dat" in message
    assert "GameAssembly.dll" in message


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

    service.run(context)

    assert calls == []
    assert extraction_workflow.calls == []


def test_extract_service_plain_jp_table_uses_manifest_metadata_resources(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(version="1.70.436321")
    _create_existing_table(context, "TablePatchPack_GroundStage_1.zip")
    extraction_workflow = RecordingExtractionWorkflow()
    metadata_store = RecordingTableMetadataStore(_build_table_metadata_resources())
    provider = StaticProvider(_build_table_catalog(context))
    logger = RecordingLogger()
    service = ExtractAssetsUseCase(
        extraction_workflow,
        workflow_profile=_build_profile(context, provider, logger, metadata_store),
    )

    service.run(context)

    assert metadata_store.load_calls == [context]
    assert extraction_workflow.calls == ["extract_tables"]
    assert extraction_workflow.resource_calls == [
        ["Table/TablePatchPack_GroundStage_1.zip"]
    ]


def test_extract_service_plain_jp_table_rebuilds_missing_manifest_from_catalog(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(version="1.70.436321")
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

    service.run(context)

    assert provider.calls == [context]
    assert metadata_store.write_calls == [(context, provider.result.resources)]
    assert extraction_workflow.calls == ["extract_tables"]
    assert extraction_workflow.resource_calls == [
        ["Table/TablePatchPack_GroundStage_1.zip"]
    ]


def test_extract_service_plain_jp_table_requires_manifest_or_catalog_metadata(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(version="1.70.436321")
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

    with pytest.raises(
        LookupError,
        match="JP table metadata manifest is missing or stale",
    ):
        service.run(context)

    assert provider.calls == [context]
    assert extraction_workflow.calls == []


def test_extract_service_search_extracts_only_existing_filtered_resources(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(
        resource_type=("bundle",),
        search=("Shiroko",),
    )
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

    service.run(context)

    assert extraction_workflow.calls == ["extract_bundles"]
    assert extraction_workflow.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_extract_service_advanced_search_filters_existing_resources(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(
        resource_type=("bundle",),
        advanced_search=("シロコ",),
    )
    _create_existing_bundle(context, "Shiroko.bundle")
    character_index_builder = DummyCharacterIndexBuilder(search_results=["Shiroko"])
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

    service.run(context)

    assert character_index_builder.search_calls == [["シロコ"]]
    assert extraction_workflow.calls == ["extract_bundles"]
    assert extraction_workflow.resource_calls == [["Bundle/Shiroko.bundle"]]


def test_extract_service_advanced_search_requires_current_index_file(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(
        version="1.70.436321",
        resource_type=("bundle",),
        advanced_search=("シロコ",),
    )
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
        service.run(context)

    message = str(exc_info.value)
    assert "Character index file is missing or does not match" in message
    assert "ba-downloader character-index build --region jp`" in message
    assert "ba-downloader sync --region jp -as <keyword>`" in message
    assert "--version" not in message
    assert character_index_builder.search_calls == []
    assert extraction_workflow.calls == []


def test_extract_service_advanced_search_respects_region_capabilities(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(
        region="cn",
        resource_type=("bundle",),
        advanced_search=("シロコ",),
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

    with pytest.raises(
        LookupError,
        match="Advanced search is not supported for region 'cn'",
    ):
        service.run(context)

    assert extraction_workflow.calls == []
