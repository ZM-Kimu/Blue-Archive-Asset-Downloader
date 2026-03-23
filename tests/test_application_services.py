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
    def __init__(self) -> None:
        self.received_resources: AssetCollection | None = None
        self.received_context: RuntimeContext | None = None

    def verify_and_download(self, resources: AssetCollection, context: RuntimeContext) -> None:
        self.received_resources = resources
        self.received_context = context


class FakeExtractService:
    def run(self, context: RuntimeContext) -> None:
        _ = context

    def run_post_download(self, context: RuntimeContext) -> None:
        _ = context


class FakeFlatbufferWorkflow:
    def dump(self, context: RuntimeContext) -> None:
        _ = context

    def compile(self, context: RuntimeContext) -> None:
        _ = context


class FakeRelationBuilder:
    def build(self, context: RuntimeContext) -> None:
        _ = context

    def get_excel_resources(self, resources: AssetCollection) -> AssetCollection:
        return resources

    def search(self, context: RuntimeContext, search_terms: list[str]) -> list[str]:
        _ = (context, search_terms)
        return []

    def verify_relation_file(self, context: RuntimeContext) -> bool:
        _ = context
        return True


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


def test_sync_service_rejects_jp_phase_one() -> None:
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

    with pytest.raises(LookupError, match="temporarily unavailable for JP"):
        SyncService(
            provider,
            FakeDownloader(),
            FakeExtractService(),
            FakeFlatbufferWorkflow(),
            lambda active_context: FakeRelationBuilder(),
            NullLogger(),
        ).run(context)


def test_relation_service_rejects_jp_phase_one() -> None:
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
            lambda active_context: FakeRelationBuilder(),
        ).build(context)
