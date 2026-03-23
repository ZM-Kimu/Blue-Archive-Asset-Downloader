from ba_downloader.domain.models.asset import AssetType, RegionCapabilities
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.resource import Resource, ResourceType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.regions.providers.legacy import (
    LegacyRegionPipelineAdapter,
    legacy_resource_to_assets,
)


class FakeLegacyProvider:
    def __init__(self, http_client: object, logger: object) -> None:
        _ = (http_client, logger)

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        resources = Resource()
        resources.add(
            "https://example.invalid/media.zip",
            "Media/media.zip",
            10,
            "abc",
            "md5",
            ResourceType.media,
        )
        return RegionCatalogResult(
            resources=resources,
            context=context.with_updates(version="1.0.0"),
            capabilities=RegionCapabilities(),
        )


def test_legacy_resource_to_assets_preserves_metadata() -> None:
    resources = Resource()
    resources.add(
        "https://example.invalid/pack",
        "Bundle/pack.bundle",
        10,
        "123",
        "crc",
        ResourceType.bundle,
        {"bundle_files": ["a.bundle"]},
    )

    assets = legacy_resource_to_assets(resources)

    assert len(assets) == 1
    assert assets[0].asset_type == AssetType.bundle
    assert assets[0].metadata["bundle_files"] == ["a.bundle"]


def test_legacy_region_adapter_converts_provider_result() -> None:
    adapter = LegacyRegionPipelineAdapter(
        FakeLegacyProvider,
        capabilities=RegionCapabilities(
            supports_sync=True,
            supports_advanced_search=False,
            supports_relation_build=False,
        ),
        http_client=object(),
        logger=object(),
    )
    context = RuntimeContext(
        region="cn",
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
    )

    result = adapter.load_catalog(context)

    assert result.context.version == "1.0.0"
    assert len(result.resources) == 1
    assert result.resources[0].asset_type == AssetType.media
    assert result.capabilities.supports_advanced_search is False
