from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
    build_application_region_profile,
)
from ba_downloader.domain.models.asset import AssetCollection, RegionCapabilities
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.region_profile import SyncExtractionMode
from ba_downloader.domain.models.runtime import RuntimeContext


class DummyProvider:
    def get_capabilities(self) -> RegionCapabilities:
        return RegionCapabilities()

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        return RegionCatalogResult(AssetCollection(), context)


class DummyLogger:
    def info(self, message: str) -> None:
        _ = message

    def warn(self, message: str) -> None:
        _ = message

    def error(self, message: str) -> None:
        _ = message


class DummyTableMetadataStore:
    def load(self, context: RuntimeContext) -> AssetCollection | None:
        _ = context
        return None

    def write(self, context: RuntimeContext, resources: AssetCollection) -> None:
        _ = (context, resources)


def _context(region: str) -> RuntimeContext:
    return RuntimeContext(
        region=region,  # type: ignore[arg-type]
        threads=1,
        version="1.0.0",
        raw_dir="RawData",
        extract_dir="Extracted",
        temp_dir="Temp",
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=".",
    )


def _profile(region: str):
    service_profile = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(region)  # type: ignore[arg-type]
    return build_application_region_profile(
        service_profile,
        _context(region),
        http_client=object(),
        logger=DummyLogger(),
        table_metadata_store=DummyTableMetadataStore(),
        provider=DummyProvider(),
    )


def test_region_profile_uses_direct_extract_for_gl() -> None:
    profile = _profile("gl")

    assert profile.prepares_schema_for_sync is True
    assert profile.sync_extraction_mode is SyncExtractionMode.direct
    assert profile.table_extraction_prerequisite is False


def test_region_profile_uses_post_download_extract_for_cn_and_jp() -> None:
    for region in ("cn", "jp"):
        profile = _profile(region)

        assert profile.prepares_schema_for_sync is True
        assert profile.sync_extraction_mode is SyncExtractionMode.post_download


def test_region_profile_marks_only_jp_for_table_prerequisite() -> None:
    assert _profile("jp").table_extraction_prerequisite is True
    assert _profile("cn").table_extraction_prerequisite is False
    assert _profile("gl").table_extraction_prerequisite is False
