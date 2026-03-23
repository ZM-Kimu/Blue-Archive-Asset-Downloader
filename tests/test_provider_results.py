from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.resource import Resource
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.regions.providers.gl import GLServer


def test_gl_provider_returns_updated_context_when_version_is_missing(monkeypatch) -> None:
    context = RuntimeContext(
        region="gl",
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
    provider = GLServer(http_client=object(), logger=NullLogger())
    resources = Resource()

    monkeypatch.setattr(provider, "get_latest_version", lambda: "1.2.3")
    monkeypatch.setattr(provider, "get_apk_url", lambda version: f"https://example.invalid/{version}.xapk")
    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.providers.gl.download_package_file",
        lambda *args, **kwargs: "archive.xapk",
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.providers.gl.extract_xapk_file",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(provider, "get_server_url", lambda version: "https://example.invalid/catalog.json")
    monkeypatch.setattr(provider, "get_resource_catalog", lambda server_url: resources)

    result = provider.load_catalog(context)

    assert isinstance(result, RegionCatalogResult)
    assert result.context.version == "1.2.3"
    assert result.resources is resources
