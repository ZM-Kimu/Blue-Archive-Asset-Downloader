from ba_downloader.application.services.download import DownloadService
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.resource import Resource, ResourceType
from ba_downloader.domain.models.runtime import RuntimeContext


class FakeProvider:
    def __init__(self, result: RegionCatalogResult) -> None:
        self.result = result
        self.received_context: RuntimeContext | None = None

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        self.received_context = context
        return self.result


class FakeDownloader:
    def __init__(self) -> None:
        self.received_resources: Resource | None = None
        self.received_context: RuntimeContext | None = None

    def verify_and_download(self, resources: Resource, context: RuntimeContext) -> None:
        self.received_resources = resources
        self.received_context = context


def test_download_service_uses_explicit_context_and_filtered_resources() -> None:
    initial_context = RuntimeContext(
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
    )
    resolved_context = initial_context.with_updates(version="1.0.0")
    resources = Resource()
    resources.add("https://example.invalid/a", "Media/a.zip", 1, "1", "md5", ResourceType.media)
    resources.add("https://example.invalid/b", "Bundle/b.bundle", 1, "2", "md5", ResourceType.bundle)

    provider = FakeProvider(RegionCatalogResult(resources=resources, context=resolved_context))
    downloader = FakeDownloader()

    returned_context = DownloadService(provider, downloader).run(initial_context)

    assert provider.received_context is initial_context
    assert downloader.received_context == resolved_context
    assert downloader.received_resources is not None
    assert len(downloader.received_resources) == 1
    assert downloader.received_resources[0].resource_type == ResourceType.media
    assert returned_context == resolved_context
