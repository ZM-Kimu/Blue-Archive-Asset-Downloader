import json
from pathlib import Path

import pytest

from ba_downloader.domain.models.asset import AssetType, ResolvedRelease
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.http import DownloadResult, HttpResponse
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.packages import ZipEntry
from ba_downloader.infrastructure.packages.apkpure import ApkPureReleaseClient
from ba_downloader.infrastructure.regions.cn.provider import CNRegionProvider
from ba_downloader.infrastructure.regions.gl.provider import (
    GLRegionProvider,
)
from ba_downloader.infrastructure.regions.gl.runtime_assets import (
    GLRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.runtime import RuntimeSnapshotStore
from support import RecordingLogger, build_apkpure_version_list
from support.fixtures import build_execution_context


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
    return HttpResponse(
        status_code=200,
        headers={"Content-Type": "application/octet-stream"},
        content=build_apkpure_version_list(package_name, *releases),
        url=ApkPureReleaseClient.API_URL,
    )


def test_gl_provider_resolves_latest_apkpure_release() -> None:
    context = build_execution_context(
        Path.cwd(),
        region="gl",
        version="",
        max_retries=1,
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

    assert result.context.resource_version == "1.2.3"
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


def test_gl_provider_resolves_latest_release_into_unresolved_context() -> None:
    context = build_execution_context(
        Path.cwd(),
        region="gl",
        version="",
        max_retries=1,
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

    assert result.context.resource_version == "1.2.3"
    assert [call["url"] for call in client.request_calls] == [
        ApkPureReleaseClient.API_URL,
        GLRegionProvider.CATALOG_URL,
        server_url,
    ]
    assert client.download_calls == []


def test_gl_provider_leaves_non_jp_platform_warning_to_cli_boundary() -> None:
    context = build_execution_context(
        Path.cwd(),
        region="gl",
        version="",
        max_retries=1,
        platform="ios",
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

    assert logger.by_level("warn") == []


def test_cn_provider_builds_assets_without_downloading_apk(
    monkeypatch,
) -> None:
    context = build_execution_context(
        Path.cwd(),
        region="cn",
        version="",
        max_retries=1,
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

    assert result.context.resource_version == "1.2.3"
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


def test_cn_provider_leaves_non_jp_platform_warning_to_cli_boundary(
    monkeypatch,
) -> None:
    context = build_execution_context(
        Path.cwd(),
        region="cn",
        version="",
        max_retries=1,
        platform="ios",
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

    assert logger.by_level("warn") == []
    assert len(result.resources) == 8


def test_gl_runtime_asset_preparer_downloads_package_for_missing_runtime_assets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context = build_execution_context(
        tmp_path,
        region="gl",
        version="1.2.3",
        max_retries=1,
    )
    preparer = GLRuntimeAssetPreparer(http_client=object(), logger=NullLogger())
    calls: list[tuple[str, object]] = []

    class FakeReleaseResolver:
        def resolve_version(
            self,
            active_context: ExecutionContext,
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
        package_path: str,
        extract_dest: str,
        _temp_dir: str,
        **_kwargs: object,
    ) -> None:
        calls.append(("extract", package_path))
        extract_path = Path(extract_dest)
        metadata_path = (
            extract_path
            / "assets"
            / "bin"
            / "Data"
            / "Managed"
            / "Metadata"
            / "global-metadata.dat"
        )
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_bytes(b"metadata")
        binary_path = extract_path / "lib" / "arm64-v8a" / "libil2cpp.so"
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        binary_path.write_bytes(b"binary")
        managers_path = extract_path / "assets" / "bin" / "Data" / "globalgamemanagers"
        managers_path.parent.mkdir(parents=True, exist_ok=True)
        managers_path.write_bytes(b"unity")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.gl.runtime_assets.download_package_file",
        fake_download_package_file,
    )
    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.gl.runtime_assets.extract_xapk_file",
        fake_extract_xapk_file,
    )

    prepared = preparer.prepare(context)

    assert calls == [
        (
            "download",
            "https://download.pureapk.com/b/XAPK/package.xapk",
        ),
        ("extract", str(tmp_path / "package.xapk")),
    ]
    assert prepared.root_dir == context.workspace.runtime_state / "1.2.3" / "Runtime"
    assert prepared.binary_path.read_bytes() == b"binary"
    assert prepared.metadata_path.read_bytes() == b"metadata"
    assert prepared.globalgamemanagers_path is not None
    assert prepared.globalgamemanagers_path.read_bytes() == b"unity"
    assert (prepared.root_dir / "manifest.json").is_file()


def test_gl_runtime_asset_preparer_reuses_matching_release(
    tmp_path: Path,
) -> None:
    context = build_execution_context(
        tmp_path,
        region="gl",
        version="1.2.3",
        max_retries=1,
    )
    snapshot_store = RuntimeSnapshotStore()
    with snapshot_store.staging_runtime(context, "1.2.3") as runtime_dir:
        (runtime_dir / "libil2cpp.so").write_bytes(b"binary")
        (runtime_dir / "global-metadata.dat").write_bytes(b"metadata")
        (runtime_dir / "globalgamemanagers").write_bytes(b"unity")
        expected = snapshot_store.publish(
            context,
            "1.2.3",
            runtime_dir,
            binary_name="libil2cpp.so",
            metadata_name="global-metadata.dat",
            globalgamemanagers_name="globalgamemanagers",
        )
    preparer = GLRuntimeAssetPreparer(
        http_client=object(),
        logger=NullLogger(),
        snapshot_store=snapshot_store,
    )

    class FailingReleaseResolver:
        def resolve_version(self, *_args: object) -> ResolvedRelease:
            raise AssertionError("Matching runtime assets must not fetch APKPure.")

    preparer.release_resolver = FailingReleaseResolver()  # type: ignore[assignment]

    assert preparer.prepare(context) == expected


def test_gl_runtime_asset_preparer_does_not_publish_incomplete_new_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old_context = build_execution_context(
        tmp_path,
        region="gl",
        version="1.2.2",
        max_retries=1,
    )
    snapshot_store = RuntimeSnapshotStore()
    with snapshot_store.staging_runtime(old_context, "1.2.2") as runtime_dir:
        (runtime_dir / "libil2cpp.so").write_bytes(b"old binary")
        (runtime_dir / "global-metadata.dat").write_bytes(b"old metadata")
        (runtime_dir / "globalgamemanagers").write_bytes(b"old unity")
        old_snapshot = snapshot_store.publish(
            old_context,
            "1.2.2",
            runtime_dir,
            binary_name="libil2cpp.so",
            metadata_name="global-metadata.dat",
            globalgamemanagers_name="globalgamemanagers",
        )

    context = old_context.without_resource_version().resolve_resource_version("1.2.3")
    preparer = GLRuntimeAssetPreparer(
        http_client=object(),
        logger=NullLogger(),
        snapshot_store=snapshot_store,
    )

    class FakeReleaseResolver:
        def resolve_version(
            self,
            _context: ExecutionContext,
            version: str,
        ) -> ResolvedRelease:
            return ResolvedRelease(
                region="gl",
                version=version,
                package_url="https://download.pureapk.com/b/XAPK/package.xapk",
            )

    preparer.release_resolver = FakeReleaseResolver()  # type: ignore[assignment]
    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.gl.runtime_assets.download_package_file",
        lambda *_args, **_kwargs: str(tmp_path / "package.xapk"),
    )

    def extract_without_metadata(
        _package_path: str,
        extract_dest: str,
        _temp_dir: str,
        **_kwargs: object,
    ) -> None:
        binary_path = Path(extract_dest) / "lib" / "arm64-v8a" / "libil2cpp.so"
        binary_path.parent.mkdir(parents=True)
        binary_path.write_bytes(b"new binary")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.gl.runtime_assets.extract_xapk_file",
        extract_without_metadata,
    )

    with pytest.raises(FileNotFoundError, match="this extraction"):
        preparer.prepare(context)

    assert snapshot_store.load(old_context, "1.2.2") == old_snapshot
    assert snapshot_store.load(context, "1.2.3") is None
