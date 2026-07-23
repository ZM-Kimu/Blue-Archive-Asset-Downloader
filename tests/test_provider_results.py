import json
from pathlib import Path

from ba_downloader.domain.models.asset import AssetType, ResolvedRelease
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import DownloadResult, HttpResponse
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.packages import ZipEntry
from ba_downloader.infrastructure.packages.apkpure import ApkPureReleaseClient
from ba_downloader.infrastructure.regions.cn.provider import CNRegionProvider
from ba_downloader.infrastructure.regions.gl.provider import (
    GLRegionProvider,
)
from ba_downloader.infrastructure.regions.gl.runtime_assets import (
    GL_RUNTIME_VERSION_FILE,
    GLRuntimeAssetPreparer,
    resolve_gl_runtime_dir,
)
from support import RecordingLogger


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


def _apkpure_response(
    package_name: str,
    *releases: tuple[str, str],
) -> HttpResponse:
    payload = b"".join(
        package_name.encode("ascii")
        + b"\x00"
        + version.encode("ascii")
        + b"\x00"
        + download_url.encode("ascii")
        + b"\x00"
        for version, download_url in releases
    )
    return HttpResponse(
        status_code=200,
        headers={"Content-Type": "application/octet-stream"},
        content=payload,
        url=ApkPureReleaseClient.API_URL,
    )


def test_gl_provider_resolves_latest_apkpure_release() -> None:
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
            ("GET", ApkPureReleaseClient.API_URL): _apkpure_response(
                "com.nexon.bluearchive",
                ("1.2.2", "https://download.pureapk.com/b/XAPK/old.xapk"),
                ("1.2.3", "https://download.pureapk.com/b/XAPK/latest.xapk"),
            ),
            ("POST", GLRegionProvider.CATALOG_URL): _json_response(
                GLRegionProvider.CATALOG_URL,
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
    provider = GLRegionProvider(http_client=client, logger=logger)

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
    assert provider.get_capabilities().supports_sync is True
    assert client.download_calls == []
    assert logger.by_level("warn") == []
    assert logger.by_level("info")[:3] == [
        "Automatically fetching latest package info...",
        "Current resource version: 1.2.3",
        "Pulling catalog...",
    ]
    assert logger.by_level("info")[-1].startswith("Catalog: 3 items in the catalog")


def test_gl_provider_replaces_stale_context_version_with_latest_release() -> None:
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
            ("GET", ApkPureReleaseClient.API_URL): _apkpure_response(
                "com.nexon.bluearchive",
                ("1.2.3", "https://download.pureapk.com/b/XAPK/latest.xapk"),
            ),
            ("POST", GLRegionProvider.CATALOG_URL): _json_response(
                GLRegionProvider.CATALOG_URL,
                {"patch": {"resource_path": server_url}},
            ),
            ("GET", server_url): _json_response(server_url, {"resources": []}),
        }
    )
    provider = GLRegionProvider(http_client=client, logger=NullLogger())

    result = provider.load_catalog(context)

    assert result.context.version == "1.2.3"
    assert [call["url"] for call in client.request_calls] == [
        ApkPureReleaseClient.API_URL,
        GLRegionProvider.CATALOG_URL,
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
            ("GET", ApkPureReleaseClient.API_URL): _apkpure_response(
                "com.nexon.bluearchive",
                ("1.2.3", "https://download.pureapk.com/b/XAPK/latest.xapk"),
            ),
            ("POST", GLRegionProvider.CATALOG_URL): _json_response(
                GLRegionProvider.CATALOG_URL,
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

    GLRegionProvider(http_client=client, logger=logger).load_catalog(context)

    assert logger.by_level("warn") == [
        "The --platform option only applies to JP and was ignored."
    ]


def test_cn_provider_builds_assets_without_downloading_apk(
    monkeypatch,
) -> None:
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
    provider = CNRegionProvider(http_client=client, logger=logger)
    monkeypatch.setattr(
        CNRegionProvider,
        "get_apk_url",
        lambda self, server="official": "https://example.invalid/BlueArchive.apk",
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.cn.provider.read_zip_entries",
        lambda url, http_client: [
            ZipEntry(
                path="assets/video/title.mp4",
                crc32=0,
                local_header_offset=0,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/video/title_4nd_1.mp4",
                crc32=0,
                local_header_offset=1,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/video/title_4nd_2.mp4",
                crc32=0,
                local_header_offset=2,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/video/title_4nd_Ep.mp4",
                crc32=0,
                local_header_offset=3,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/video/title_5th_1.mp4",
                crc32=0,
                local_header_offset=4,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/aa/catalog.json",
                crc32=0,
                local_header_offset=5,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
        ],
    )

    result = provider.load_catalog(context)

    assert result.context.version == "1.2.3"
    assert [item.path for item in result.resources] == [
        "Table/Excel.zip",
        "Media/Audio/BGM/title_theme.mp4",
        "Bundle/characters.bundle",
        "Media/video/title.mp4",
        "Media/video/title_4nd_1.mp4",
        "Media/video/title_4nd_2.mp4",
        "Media/video/title_4nd_Ep.mp4",
        "Media/video/title_5th_1.mp4",
    ]
    assert [item.asset_type for item in result.resources] == [
        AssetType.table,
        AssetType.media,
        AssetType.bundle,
        AssetType.media,
        AssetType.media,
        AssetType.media,
        AssetType.media,
        AssetType.media,
    ]
    assert provider.get_capabilities().supports_sync is True
    assert provider.get_capabilities().supports_advanced_search is True
    assert provider.get_capabilities().supports_character_index_build is True
    assert [item.checksum.algorithm for item in result.resources] == [
        "md5",
        "md5",
        "md5",
        "crc",
        "crc",
        "crc",
        "crc",
        "crc",
    ]
    assert result.resources[0].metadata["includes"] == ["CharacterExcelTable"]
    assert result.resources[1].metadata["media_type"] == "mp4"
    assert result.resources[3].metadata["source"] == CNRegionProvider.APK_MEDIA_SOURCE
    assert result.resources[3].metadata["apk_entry_path"] == "assets/video/title.mp4"
    assert result.resources[3].url == "https://example.invalid/BlueArchive.apk"
    assert client.request_calls[1]["headers"] == {
        "APP-VER": "1.2.3",
        "PLATFORM-ID": "1",
        "CHANNEL-ID": "2",
    }
    assert client.download_calls == []
    assert logger.by_level("warn") == []
    assert logger.by_level("info")[:3] == [
        "Automatically fetching latest version...",
        "Current resource version: 1.2.3",
        "Pulling catalog...",
    ]
    assert logger.by_level("info")[-1].startswith("Catalog: 8 items in the catalog")


def test_cn_provider_warns_when_platform_is_explicitly_ignored(
    monkeypatch,
) -> None:
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
    monkeypatch.setattr(
        CNRegionProvider,
        "get_apk_url",
        lambda self, server="official": "https://example.invalid/BlueArchive.apk",
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.cn.provider.read_zip_entries",
        lambda url, http_client: [
            ZipEntry(
                path="assets/video/title.mp4",
                crc32=0,
                local_header_offset=0,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/video/title_4nd_1.mp4",
                crc32=0,
                local_header_offset=1,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/video/title_4nd_2.mp4",
                crc32=0,
                local_header_offset=2,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/video/title_4nd_Ep.mp4",
                crc32=0,
                local_header_offset=3,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
            ZipEntry(
                path="assets/video/title_5th_1.mp4",
                crc32=0,
                local_header_offset=4,
                compressed_size=1,
                uncompressed_size=1,
                compression_method=0,
                file_name_length=1,
                extra_field_length=0,
            ),
        ],
    )

    result = CNRegionProvider(http_client=client, logger=logger).load_catalog(context)

    assert logger.by_level("warn") == [
        "The --platform option only applies to JP and was ignored."
    ]
    assert len(result.resources) == 8


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

    class FakeReleaseResolver:
        def resolve_version(
            self,
            active_context: RuntimeContext,
            version: str,
        ) -> ResolvedRelease:
            assert active_context is context
            assert version == "1.2.3"
            return ResolvedRelease(
                region="gl",
                version=version,
                package_url="https://download.pureapk.com/b/XAPK/package.xapk",
            )

    preparer.release_resolver = FakeReleaseResolver()  # type: ignore[assignment]

    def fake_download_package_file(*args: object, **_kwargs: object) -> str:
        calls.append(("download", args[2]))
        return str(tmp_path / "package.xapk")

    def fake_extract_xapk_file(
        package_path: str, extract_dest: str, _temp_dir: str
    ) -> None:
        calls.append(("extract", package_path))
        extract_path = Path(extract_dest)
        extract_path.mkdir(parents=True, exist_ok=True)
        (extract_path / "libil2cpp.so").write_bytes(b"binary")
        (extract_path / "global-metadata.dat").write_bytes(b"metadata")
        (extract_path / "globalgamemanagers").write_bytes(b"unity")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.gl.runtime_assets.download_package_file",
        fake_download_package_file,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.gl.runtime_assets.extract_xapk_file",
        fake_extract_xapk_file,
    )

    preparer.prepare(context)

    assert calls == [
        (
            "download",
            "https://download.pureapk.com/b/XAPK/package.xapk",
        ),
        ("extract", str(tmp_path / "package.xapk")),
    ]
    assert (resolve_gl_runtime_dir(context) / GL_RUNTIME_VERSION_FILE).read_text(
        encoding="utf8"
    ) == "1.2.3"


def test_gl_runtime_asset_preparer_reuses_matching_release(
    tmp_path: Path,
) -> None:
    context = RuntimeContext(
        region="gl",
        threads=1,
        version="1.2.3",
        raw_dir="Raw",
        extract_dir="Extracted",
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )
    runtime_dir = resolve_gl_runtime_dir(context)
    runtime_dir.mkdir(parents=True)
    for file_name in GLRuntimeAssetPreparer.RUNTIME_FILES:
        (runtime_dir / file_name).write_bytes(b"runtime")
    (runtime_dir / GL_RUNTIME_VERSION_FILE).write_text("1.2.3", encoding="utf8")
    preparer = GLRuntimeAssetPreparer(http_client=object(), logger=NullLogger())

    class FailingReleaseResolver:
        def resolve_version(self, *_args: object) -> ResolvedRelease:
            raise AssertionError("Matching runtime assets must not fetch APKPure.")

    preparer.release_resolver = FailingReleaseResolver()  # type: ignore[assignment]

    preparer.prepare(context)
