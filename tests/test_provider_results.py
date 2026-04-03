import json
from pathlib import Path

from ba_downloader.domain.models.asset import AssetType
from ba_downloader.domain.ports.http import DownloadResult, HttpResponse
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.regions.providers.cn import CNServer
from ba_downloader.infrastructure.regions.providers.gl import GLServer
from ba_downloader.infrastructure.regions.providers.gl import GLRuntimeAssetPreparer


class RecordingHttpClient:
    def __init__(self, responses: dict[tuple[str, str], HttpResponse]) -> None:
        self.responses = responses
        self.request_calls: list[dict[str, object]] = []
        self.download_calls: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: object | None = None,
        data: object | None = None,
        params: dict[str, object] | None = None,
        transport: str = "default",
        timeout: float = 10.0,
    ) -> HttpResponse:
        _ = (data, params, transport, timeout)
        self.request_calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
            }
        )
        return self.responses[(method, url)]

    def download_to_file(
        self,
        url: str,
        destination: str,
        *,
        headers: dict[str, str] | None = None,
        transport: str = "default",
        timeout: float = 300.0,
        progress_callback: object | None = None,
        should_stop: object | None = None,
    ) -> DownloadResult:
        _ = (headers, transport, timeout, progress_callback, should_stop)
        self.download_calls.append({"url": url, "destination": destination})
        return DownloadResult(
            path=destination,
            bytes_written=0,
            status_code=200,
            headers={},
            url=url,
        )

    def close(self) -> None:
        return None


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


def _json_response(url: str, payload: object) -> HttpResponse:
    return HttpResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        content=json.dumps(payload).encode("utf-8"),
        url=url,
    )


def _text_response(url: str, payload: str) -> HttpResponse:
    return HttpResponse(
        status_code=200,
        headers={"Content-Type": "text/plain"},
        content=payload.encode("utf-8"),
        url=url,
    )


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
    server_url = "https://example.invalid/catalog.json"
    client = RecordingHttpClient(
        {
            ("GET", GLServer.UPTODOWN_URL): _text_response(
                GLServer.UPTODOWN_URL,
                "Blue Archive Global 1.2.3",
            ),
            ("POST", GLServer.CATALOG_URL): _json_response(
                GLServer.CATALOG_URL,
                {"patch": {"resource_path": server_url}},
            ),
            ("GET", server_url): _json_response(
                server_url,
                {
                    "resources": [
                        {
                            "group": "table",
                            "resource_path": "TableBundles/Excel.zip",
                            "resource_size": 10,
                            "resource_hash": "aaa",
                        },
                        {
                            "group": "media",
                            "resource_path": "MediaResources/GameData/title_theme.zip",
                            "resource_size": 20,
                            "resource_hash": "bbb",
                        },
                        {
                            "group": "bundle",
                            "resource_path": "AssetBundles/Android/characters.bundle",
                            "resource_size": 30,
                            "resource_hash": "ccc",
                        },
                    ]
                },
            ),
        }
    )
    logger = RecordingLogger()
    provider = GLServer(http_client=client, logger=logger)

    result = provider.load_catalog(context)

    assert result.context.version == "1.2.3"
    assert [item.asset_type for item in result.resources] == [
        AssetType.table,
        AssetType.media,
        AssetType.bundle,
    ]
    assert [item.path for item in result.resources] == [
        "Table/Excel.zip",
        "Media/GameData/title_theme.zip",
        "Bundle/characters.bundle",
    ]
    assert result.capabilities.supports_sync is True
    assert client.download_calls == []
    assert logger.warn_messages == []
    assert logger.info_messages[:3] == [
        "Version not specified. Automatically fetching latest...",
        "Current resource version: 1.2.3",
        "Pulling catalog...",
    ]
    assert logger.info_messages[-1].startswith("Catalog: 3 items in the catalog")


def test_gl_provider_uses_explicit_version_without_fetching_latest() -> None:
    context = RuntimeContext(
        region="gl",
        threads=4,
        version="9.9.9",
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
    server_url = "https://example.invalid/catalog.json"
    client = RecordingHttpClient(
        {
            ("POST", GLServer.CATALOG_URL): _json_response(
                GLServer.CATALOG_URL,
                {"patch": {"resource_path": server_url}},
            ),
            ("GET", server_url): _json_response(server_url, {"resources": []}),
        }
    )
    provider = GLServer(http_client=client, logger=NullLogger())

    result = provider.load_catalog(context)

    assert result.context.version == "9.9.9"
    assert [call["url"] for call in client.request_calls] == [
        GLServer.CATALOG_URL,
        server_url,
    ]
    assert client.download_calls == []


def test_gl_provider_warns_when_platform_is_explicitly_ignored() -> None:
    context = RuntimeContext(
        region="gl",
        threads=4,
        version="9.9.9",
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
        platform="ios",
        platform_explicit=True,
    )
    server_url = "https://example.invalid/catalog.json"
    client = RecordingHttpClient(
        {
            ("POST", GLServer.CATALOG_URL): _json_response(
                GLServer.CATALOG_URL,
                {"patch": {"resource_path": server_url}},
            ),
            ("GET", server_url): _json_response(
                server_url,
                {
                    "resources": [
                        {
                            "group": "table",
                            "resource_path": "TableBundles/Excel.zip",
                            "resource_size": 10,
                            "resource_hash": "aaa",
                        },
                        {
                            "group": "media",
                            "resource_path": "MediaResources/GameData/title_theme.zip",
                            "resource_size": 20,
                            "resource_hash": "bbb",
                        },
                        {
                            "group": "bundle",
                            "resource_path": "AssetBundles/Android/characters.bundle",
                            "resource_size": 30,
                            "resource_hash": "ccc",
                        },
                    ]
                },
            ),
        }
    )
    logger = RecordingLogger()

    GLServer(http_client=client, logger=logger).load_catalog(context)

    assert logger.warn_messages == ["The --platform option only applies to JP and was ignored."]


def test_cn_provider_builds_assets_without_downloading_apk() -> None:
    context = RuntimeContext(
        region="cn",
        threads=4,
        version="",
        raw_dir="Raw",
        extract_dir="Extracted",
        temp_dir="Temp",
        extract_while_download=False,
        resource_type=("media", "table", "bundle"),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=".",
    )
    client = RecordingHttpClient(
        {
            ("GET", "https://bluearchive-cn.com/api/meta/setup"): _text_response(
                "https://bluearchive-cn.com/api/meta/setup",
                '{"version":"1.2.3"}',
            ),
            ("GET", "https://gs-api.bluearchive-cn.com/api/state"): _json_response(
                "https://gs-api.bluearchive-cn.com/api/state",
                {
                    "AddressablesCatalogUrlRoots": ["https://cdn.example.invalid"],
                    "TableVersion": "table-v1",
                    "MediaVersion": "media-v1",
                    "ResourceVersion": "bundle-v1",
                },
            ),
            (
                "GET",
                "https://cdn.example.invalid/Manifest/TableBundles/table-v1/TableManifest",
            ): _json_response(
                "https://cdn.example.invalid/Manifest/TableBundles/table-v1/TableManifest",
                {
                    "Table": {
                        "Excel": {
                            "Name": "Excel.zip",
                            "Crc": "aabbccdd",
                            "Size": 12,
                            "Includes": ["CharacterExcelTable"],
                        }
                    }
                },
            ),
            (
                "GET",
                "https://cdn.example.invalid/Manifest/MediaResources/media-v1/MediaManifest",
            ): _text_response(
                "https://cdn.example.invalid/Manifest/MediaResources/media-v1/MediaManifest",
                "Audio/BGM/title_theme,1122334455667788,2,15,0\n",
            ),
            (
                "GET",
                "https://cdn.example.invalid/AssetBundles/Catalog/bundle-v1/Android/bundleDownloadInfo.json",
            ): _json_response(
                "https://cdn.example.invalid/AssetBundles/Catalog/bundle-v1/Android/bundleDownloadInfo.json",
                {
                    "BundleFiles": [
                        {
                            "Name": "characters.bundle",
                            "Size": 20,
                            "Crc": "ffeeddcc",
                            "IsPrologue": False,
                            "IsSplitDownload": False,
                        }
                    ]
                },
            ),
        }
    )
    logger = RecordingLogger()
    provider = CNServer(http_client=client, logger=logger)

    result = provider.load_catalog(context)

    assert result.context.version == "1.2.3"
    assert [item.path for item in result.resources] == [
        "Table/Excel.zip",
        "Media/Audio/BGM/title_theme.mp4",
        "Bundle/characters.bundle",
    ]
    assert [item.asset_type for item in result.resources] == [
        AssetType.table,
        AssetType.media,
        AssetType.bundle,
    ]
    assert [item.checksum.algorithm for item in result.resources] == [
        "md5",
        "md5",
        "md5",
    ]
    assert result.resources[0].metadata["includes"] == ["CharacterExcelTable"]
    assert result.resources[1].metadata["media_type"] == "mp4"
    assert client.request_calls[1]["headers"] == {
        "APP-VER": "1.2.3",
        "PLATFORM-ID": "1",
        "CHANNEL-ID": "2",
    }
    assert client.download_calls == []
    assert logger.warn_messages == []
    assert logger.info_messages[:3] == [
        "Automatically fetching latest version...",
        "Current resource version: 1.2.3",
        "Pulling catalog...",
    ]
    assert logger.info_messages[-1].startswith("Catalog: 3 items in the catalog")


def test_cn_provider_warns_when_platform_is_explicitly_ignored() -> None:
    context = RuntimeContext(
        region="cn",
        threads=4,
        version="",
        raw_dir="Raw",
        extract_dir="Extracted",
        temp_dir="Temp",
        extract_while_download=False,
        resource_type=("media", "table", "bundle"),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=".",
        platform="ios",
        platform_explicit=True,
    )
    client = RecordingHttpClient(
        {
            ("GET", "https://bluearchive-cn.com/api/meta/setup"): _text_response(
                "https://bluearchive-cn.com/api/meta/setup",
                '{"version":"1.2.3"}',
            ),
            ("GET", "https://gs-api.bluearchive-cn.com/api/state"): _json_response(
                "https://gs-api.bluearchive-cn.com/api/state",
                {
                    "AddressablesCatalogUrlRoots": ["https://cdn.example.invalid"],
                    "TableVersion": "table-v1",
                    "MediaVersion": "media-v1",
                    "ResourceVersion": "bundle-v1",
                },
            ),
            (
                "GET",
                "https://cdn.example.invalid/Manifest/TableBundles/table-v1/TableManifest",
            ): _json_response(
                "https://cdn.example.invalid/Manifest/TableBundles/table-v1/TableManifest",
                {
                    "Table": {
                        "Excel": {
                            "Name": "Excel.zip",
                            "Crc": "aabbccdd",
                            "Size": 12,
                            "Includes": [],
                        }
                    }
                },
            ),
            (
                "GET",
                "https://cdn.example.invalid/Manifest/MediaResources/media-v1/MediaManifest",
            ): _text_response(
                "https://cdn.example.invalid/Manifest/MediaResources/media-v1/MediaManifest",
                "Audio/BGM/title_theme,1122334455667788,2,15,0\n",
            ),
            (
                "GET",
                "https://cdn.example.invalid/AssetBundles/Catalog/bundle-v1/Android/bundleDownloadInfo.json",
            ): _json_response(
                "https://cdn.example.invalid/AssetBundles/Catalog/bundle-v1/Android/bundleDownloadInfo.json",
                {
                    "BundleFiles": [
                        {
                            "Name": "characters.bundle",
                            "Size": 20,
                            "Crc": "ffeeddcc",
                        }
                    ]
                },
            ),
        }
    )
    logger = RecordingLogger()

    result = CNServer(http_client=client, logger=logger).load_catalog(context)

    assert logger.warn_messages == ["The --platform option only applies to JP and was ignored."]
    assert len(result.resources) == 3


def test_gl_runtime_asset_preparer_downloads_package_for_missing_runtime_assets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context = RuntimeContext(
        region="gl",
        threads=4,
        version="1.2.3",
        raw_dir="Raw",
        extract_dir="Extracted",
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("media",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )
    preparer = GLRuntimeAssetPreparer(http_client=object(), logger=NullLogger())
    calls: list[tuple[str, object]] = []

    def fake_download_package_file(*args, **kwargs) -> str:
        calls.append(("download", kwargs["transport"]))
        return str(tmp_path / "package.xapk")

    def fake_extract_xapk_file(package_path: str, extract_dest: str, temp_dir: str) -> None:
        calls.append(("extract", package_path))
        extract_path = Path(extract_dest)
        extract_path.mkdir(parents=True, exist_ok=True)
        (extract_path / "libil2cpp.so").write_bytes(b"binary")
        (extract_path / "global-metadata.dat").write_bytes(b"metadata")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.providers.gl.download_package_file",
        fake_download_package_file,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.providers.gl.extract_xapk_file",
        fake_extract_xapk_file,
    )

    preparer.prepare(context)

    assert calls == [
        ("download", "browser"),
        ("extract", str(tmp_path / "package.xapk")),
    ]
