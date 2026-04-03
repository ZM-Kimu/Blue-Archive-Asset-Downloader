import pytest

from ba_downloader.application.services.download import DownloadService
from ba_downloader.application.services.relation import RelationService
from ba_downloader.application.services.sync import SyncService
from ba_downloader.domain.models.asset import AssetCollection, AssetType, RegionCapabilities
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.logging.console_logger import NullLogger


class FakeProvider:
    def __init__(
        self,
        result: RegionCatalogResult,
        capabilities: RegionCapabilities | None = None,
    ) -> None:
        self.result = result
        self.capabilities = capabilities or result.capabilities
        self.received_context: RuntimeContext | None = None

    def get_capabilities(self) -> RegionCapabilities:
        return self.capabilities

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        self.received_context = context
        return self.result


class FakeDownloader:
    def __init__(self, events: list[tuple[str, RuntimeContext]] | None = None) -> None:
        self.received_resources: AssetCollection | None = None
        self.received_context: RuntimeContext | None = None
        self.events = events if events is not None else []

    def verify_and_download(self, resources: AssetCollection, context: RuntimeContext) -> None:
        self.received_resources = resources
        self.received_context = context
        self.events.append(("download", context))


class FakeExtractService:
    def __init__(self, events: list[tuple[str, RuntimeContext]] | None = None) -> None:
        self.events = events if events is not None else []

    def run(self, context: RuntimeContext) -> None:
        self.events.append(("extract", context))

    def run_post_download(self, context: RuntimeContext) -> None:
        self.events.append(("extract_post_download", context))


class FakeFlatbufferWorkflow:
    def __init__(self, events: list[tuple[str, RuntimeContext]] | None = None) -> None:
        self.events = events if events is not None else []

    def dump(self, context: RuntimeContext) -> None:
        self.events.append(("dump", context))

    def compile(self, context: RuntimeContext) -> None:
        self.events.append(("compile", context))


class FakeRuntimeAssetPreparer:
    def __init__(self, events: list[tuple[str, RuntimeContext]] | None = None) -> None:
        self.events = events if events is not None else []
        self.received_contexts: list[RuntimeContext] = []

    def prepare(self, context: RuntimeContext) -> None:
        self.received_contexts.append(context)
        self.events.append(("prepare", context))


class FakeRelationBuilder:
    def __init__(self, events: list[tuple[str, RuntimeContext]] | None = None) -> None:
        self.events = events if events is not None else []
        self.built_context: RuntimeContext | None = None

    def build(self, context: RuntimeContext) -> None:
        self.built_context = context
        self.events.append(("build", context))

    def get_excel_resources(self, resources: AssetCollection) -> AssetCollection:
        return resources

    def search(self, context: RuntimeContext, search_terms: list[str]) -> list[str]:
        _ = (context, search_terms)
        return []

    def verify_relation_file(self, context: RuntimeContext) -> bool:
        _ = context
        return True


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


def _build_context(**changes: object) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=4,
        version="",
        raw_dir="Raw",
        extract_dir="Extracted",
        temp_dir="Temp",
        extract_while_download=False,
        resource_type=("media",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=".",
    ).with_updates(**changes)


def test_download_service_uses_explicit_context_and_filtered_resources() -> None:
    initial_context = _build_context()
    resolved_context = initial_context.with_updates(version="1.0.0")
    resources = AssetCollection()
    resources.add("https://example.invalid/a", "Media/a.zip", 1, "1", "md5", AssetType.media)
    resources.add("https://example.invalid/b", "Bundle/b.bundle", 1, "2", "md5", AssetType.bundle)

    provider = FakeProvider(
        RegionCatalogResult(
            resources=resources,
            context=resolved_context,
            capabilities=RegionCapabilities(),
        )
    )
    downloader = FakeDownloader()

    returned_context = DownloadService(provider, downloader).run(initial_context)

    assert provider.received_context is initial_context
    assert downloader.received_context == resolved_context
    assert downloader.received_resources is not None
    assert len(downloader.received_resources) == 1
    assert downloader.received_resources[0].asset_type == AssetType.media
    assert returned_context == resolved_context


def test_download_service_applies_plain_search() -> None:
    initial_context = _build_context(
        search=("shiroko",),
        resource_type=("media", "bundle"),
    )
    resolved_context = initial_context.with_updates(version="1.0.0")
    resources = AssetCollection()
    resources.add("https://example.invalid/a", "Media/other.zip", 1, "1", "md5", AssetType.media)
    resources.add(
        "https://example.invalid/b",
        "Bundle/characters.pack",
        1,
        "2",
        "md5",
        AssetType.bundle,
        {"bundle_files": ["shiroko.bundle"]},
    )

    provider = FakeProvider(
        RegionCatalogResult(
            resources=resources,
            context=resolved_context,
            capabilities=RegionCapabilities(
                supports_sync=False,
                supports_advanced_search=False,
                supports_relation_build=False,
            ),
        )
    )
    downloader = FakeDownloader()

    DownloadService(provider, downloader).run(initial_context)

    assert downloader.received_resources is not None
    assert [item.path for item in downloader.received_resources] == ["Bundle/characters.pack"]


def test_sync_service_rejects_region_without_sync_capability() -> None:
    context = _build_context()
    provider = FakeProvider(
        RegionCatalogResult(
            resources=AssetCollection(),
            context=context,
            capabilities=RegionCapabilities(
                supports_sync=False,
                supports_advanced_search=False,
                supports_relation_build=False,
            ),
        )
    )

    with pytest.raises(LookupError, match="temporarily unavailable for region 'jp'"):
        SyncService(
            provider,
            FakeDownloader(),
            FakeExtractService(),
            FakeFlatbufferWorkflow(),
            FakeRuntimeAssetPreparer(),
            lambda active_context: FakeRelationBuilder(),
            NullLogger(),
        ).run(context)


def test_relation_service_rejects_region_without_relation_capability() -> None:
    context = _build_context()
    provider = FakeProvider(
        RegionCatalogResult(
            resources=AssetCollection(),
            context=context,
            capabilities=RegionCapabilities(
                supports_sync=False,
                supports_advanced_search=False,
                supports_relation_build=False,
            ),
        )
    )

    with pytest.raises(LookupError, match="Relation build is temporarily unavailable"):
        RelationService(
            provider,
            FakeDownloader(),
            FakeFlatbufferWorkflow(),
            FakeRuntimeAssetPreparer(),
            lambda active_context: FakeRelationBuilder(),
        ).build(context)


def test_sync_service_prepares_runtime_assets_before_jp_download() -> None:
    initial_context = _build_context(region="jp")
    resolved_context = initial_context.with_updates(version="1.2.3")
    events: list[tuple[str, RuntimeContext]] = []
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/a",
        "Media/a.zip",
        1,
        "1",
        "md5",
        AssetType.media,
    )
    provider = FakeProvider(
        RegionCatalogResult(
            resources=resources,
            context=resolved_context,
            capabilities=RegionCapabilities(
                supports_sync=True,
                supports_advanced_search=False,
                supports_relation_build=True,
            ),
        )
    )
    downloader = FakeDownloader(events)
    extract_service = FakeExtractService(events)
    flatbuffer_workflow = FakeFlatbufferWorkflow(events)
    runtime_asset_preparer = FakeRuntimeAssetPreparer(events)

    returned_context = SyncService(
        provider,
        downloader,
        extract_service,
        flatbuffer_workflow,
        runtime_asset_preparer,
        lambda active_context: FakeRelationBuilder(events),
        NullLogger(),
    ).run(initial_context)

    assert returned_context == resolved_context
    assert runtime_asset_preparer.received_contexts == [resolved_context]
    assert events[:4] == [
        ("prepare", resolved_context),
        ("dump", resolved_context),
        ("compile", resolved_context),
        ("download", resolved_context),
    ]
    assert events[-1] == ("extract_post_download", resolved_context)


def test_sync_service_prepares_runtime_assets_before_gl_dump_and_compile() -> None:
    initial_context = _build_context(region="gl")
    resolved_context = initial_context.with_updates(version="1.2.3")
    events: list[tuple[str, RuntimeContext]] = []
    resources = AssetCollection()
    provider = FakeProvider(
        RegionCatalogResult(
            resources=resources,
            context=resolved_context,
            capabilities=RegionCapabilities(),
        )
    )
    downloader = FakeDownloader(events)
    extract_service = FakeExtractService(events)
    flatbuffer_workflow = FakeFlatbufferWorkflow(events)
    runtime_asset_preparer = FakeRuntimeAssetPreparer(events)

    returned_context = SyncService(
        provider,
        downloader,
        extract_service,
        flatbuffer_workflow,
        runtime_asset_preparer,
        lambda active_context: FakeRelationBuilder(events),
        NullLogger(),
    ).run(initial_context)

    assert returned_context == resolved_context
    assert runtime_asset_preparer.received_contexts == [resolved_context]
    assert events[:3] == [
        ("prepare", resolved_context),
        ("dump", resolved_context),
        ("compile", resolved_context),
    ]
    assert events[-1] == ("extract", resolved_context)


def test_relation_service_uses_resolved_context_for_runtime_preparation() -> None:
    initial_context = _build_context(region="gl")
    resolved_context = initial_context.with_updates(version="1.2.3")
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/Excel.zip",
        "Table/Excel.zip",
        1,
        "abc",
        "md5",
        AssetType.table,
    )
    events: list[tuple[str, RuntimeContext]] = []
    relation_builder = FakeRelationBuilder(events)
    provider = FakeProvider(
        RegionCatalogResult(
            resources=resources,
            context=resolved_context,
            capabilities=RegionCapabilities(),
        )
    )
    downloader = FakeDownloader(events)
    flatbuffer_workflow = FakeFlatbufferWorkflow(events)
    runtime_asset_preparer = FakeRuntimeAssetPreparer(events)

    returned_context = RelationService(
        provider,
        downloader,
        flatbuffer_workflow,
        runtime_asset_preparer,
        lambda active_context: relation_builder,
    ).build(initial_context)

    assert returned_context == resolved_context
    assert runtime_asset_preparer.received_contexts == [resolved_context]
    assert downloader.received_context == resolved_context
    assert relation_builder.built_context == resolved_context
    assert events[:4] == [
        ("prepare", resolved_context),
        ("dump", resolved_context),
        ("compile", resolved_context),
        ("download", resolved_context),
    ]


def test_sync_service_logs_advanced_search_preparation_at_info_level() -> None:
    initial_context = _build_context(
        region="cn",
        version="1.2.3",
        advanced_search=("shiroko",),
    )
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/a",
        "Media/a.zip",
        1,
        "1",
        "md5",
        AssetType.media,
    )
    logger = RecordingLogger()
    provider = FakeProvider(
        RegionCatalogResult(
            resources=resources,
            context=initial_context,
            capabilities=RegionCapabilities(
                supports_sync=True,
                supports_advanced_search=True,
                supports_relation_build=True,
            ),
        )
    )

    SyncService(
        provider,
        FakeDownloader(),
        FakeExtractService(),
        FakeFlatbufferWorkflow(),
        FakeRuntimeAssetPreparer(),
        lambda active_context: FakeRelationBuilder(),
        logger,
    ).run(initial_context)

    assert logger.info_messages == ["Preparing for advanced search..."]
    assert logger.warn_messages == []
