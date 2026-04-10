import json
import struct
from typing import Any

import pytest

from ba_downloader.domain.models.asset import (
    AssetCollection,
    BootstrapSession,
    ResolvedRelease,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpResponse
from ba_downloader.domain.services.resource_query import ResourceQueryService
from ba_downloader.infrastructure.apk.package_manager import (
    PackageArchiveError,
    _resolve_filename,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.regions.providers.jp import (
    DecodedJPCatalog,
    JPBootstrapper,
    JPServer,
)


class MemoryPackWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def to_bytes(self) -> bytes:
        return bytes(self.buffer)

    def write_object(self, member_count: int, field_writer: Any) -> None:
        self.write_uint8(member_count)
        field_writer(self)

    def write_collection_header(self, length: int | None) -> None:
        self.buffer.extend(struct.pack("<i", -1 if length is None else length))

    def write_uint8(self, value: int) -> None:
        self.buffer.extend(struct.pack("<B", value))

    def write_bool(self, value: bool) -> None:
        self.buffer.extend(struct.pack("<?", value))

    def write_int32(self, value: int) -> None:
        self.buffer.extend(struct.pack("<i", value))

    def write_int64(self, value: int) -> None:
        self.buffer.extend(struct.pack("<q", value))

    def write_string(self, value: str | None) -> None:
        if value is None:
            self.write_collection_header(None)
            return
        if value == "":
            self.write_collection_header(0)
            return

        encoded = value.encode("utf-8")
        self.write_int32(~len(encoded))
        self.write_int32(len(value))
        self.buffer.extend(encoded)

    def write_array(self, values: list[Any] | None, item_writer: Any) -> None:
        if values is None:
            self.write_collection_header(None)
            return

        self.write_collection_header(len(values))
        for value in values:
            item_writer(self, value)

    def write_string_map(self, values: dict[str, Any] | None, value_writer: Any) -> None:
        if values is None:
            self.write_collection_header(None)
            return

        self.write_collection_header(len(values))
        for key, value in values.items():
            self.write_string(key)
            value_writer(self, value)


class RecordingHttpClient:
    def __init__(self, responses: dict[tuple[str, str], HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: dict[str, Any] | None = None,
        transport: str = "default",
        timeout: float = 10.0,
    ) -> HttpResponse:
        _ = (headers, json, data, params, transport, timeout)
        key = (method, url)
        self.calls.append(key)
        return self.responses[key]

    def download_to_file(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("download_to_file should not be used in JP manifest tests.")

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


def _write_table_bundle(writer: MemoryPackWriter, bundle: dict[str, Any]) -> None:
    writer.write_object(
        8,
        lambda payload: (
            payload.write_string(bundle["name"]),
            payload.write_int64(bundle["size"]),
            payload.write_int64(bundle["crc"]),
            payload.write_bool(bundle["is_in_build"]),
            payload.write_bool(bundle["is_changed"]),
            payload.write_bool(bundle["is_prologue"]),
            payload.write_bool(bundle["is_split_download"]),
            payload.write_array(bundle["includes"], lambda nested, item: nested.write_string(item)),
        ),
    )


def _write_table_patch_pack(writer: MemoryPackWriter, pack: dict[str, Any]) -> None:
    writer.write_object(
        5,
        lambda payload: (
            payload.write_string(pack["name"]),
            payload.write_int64(pack["size"]),
            payload.write_int64(pack["crc"]),
            payload.write_bool(pack["is_prologue"]),
            payload.write_array(pack["bundle_files"], _write_table_bundle),
        ),
    )


def _write_media_entry(writer: MemoryPackWriter, media: dict[str, Any]) -> None:
    writer.write_object(
        7,
        lambda payload: (
            payload.write_string(media["path"]),
            payload.write_string(media["file_name"]),
            payload.write_int64(media["bytes"]),
            payload.write_int64(media["crc"]),
            payload.write_bool(media["is_prologue"]),
            payload.write_bool(media["is_split_download"]),
            payload.write_int32(media["type"]),
        ),
    )


def _build_table_catalog_bytes() -> bytes:
    writer = MemoryPackWriter()
    writer.write_object(
        2,
        lambda payload: (
            payload.write_string_map(
                {
                    "TableKey": {
                        "name": "MainTable.bytes",
                        "size": 123,
                        "crc": 456,
                        "is_in_build": False,
                        "is_changed": True,
                        "is_prologue": False,
                        "is_split_download": False,
                        "includes": ["Excel/CharacterExcel.bytes"],
                    }
                },
                _write_table_bundle,
            ),
            payload.write_string_map(
                {
                    "PackKey": {
                        "name": "PackTable.bytes",
                        "size": 789,
                        "crc": 101112,
                        "is_prologue": True,
                        "bundle_files": [
                            {
                                "name": "Nested.bytes",
                                "size": 12,
                                "crc": 34,
                                "is_in_build": True,
                                "is_changed": False,
                                "is_prologue": False,
                                "is_split_download": False,
                                "includes": [],
                            }
                        ],
                    }
                },
                _write_table_patch_pack,
            ),
        ),
    )
    return writer.to_bytes()


def _build_media_catalog_bytes() -> bytes:
    writer = MemoryPackWriter()
    writer.write_object(
        1,
        lambda payload: payload.write_string_map(
            {
                "MediaKey": {
                    "path": "GameData/Audio/BGM/title_theme.zip",
                    "file_name": "title_theme.zip",
                    "bytes": 55,
                    "crc": 66,
                    "is_prologue": False,
                    "is_split_download": False,
                    "type": 1,
                }
            },
            _write_media_entry,
        ),
    )
    return writer.to_bytes()


def test_parse_package_info_prefers_highest_version() -> None:
    payload = (
        b"com.YostarJP.BlueArchive\x00"
        b"1.64.123456\x00"
        b"https://download.pureapk.com/b/XAPK/old-build.xapk\x00"
        b"com.YostarJP.BlueArchive\x00"
        b"1.66.405117\x00"
        b"https://download.pureapk.com/b/XAPK/latest-build.xapk\x00"
    )

    package_info = JPServer.parse_package_info(payload)

    assert package_info.version == "1.66.405117"
    assert package_info.download_url == (
        "https://download.pureapk.com/b/XAPK/latest-build.xapk"
    )


def test_parse_package_info_raises_for_invalid_payload() -> None:
    with pytest.raises(LookupError, match="PureAPK"):
        JPServer.parse_package_info(b"invalid payload")


def test_resolve_filename_falls_back_to_url() -> None:
    file_name = _resolve_filename(
        "",
        "https://download.pureapk.com/b/XAPK/com.YostarJP.BlueArchive",
    )

    assert file_name == "com.YostarJP.BlueArchive.xapk"


def test_get_resource_manifest_uses_second_root_and_bundle_packing_info() -> None:
    server_url = "https://example.invalid/server-info.json"
    catalog_root = "https://cdn.example.invalid/catalog-root"
    responses = {
        (
            "GET",
            server_url,
        ): HttpResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            content=json.dumps(
                {
                    "ConnectionGroups": [
                        {
                            "OverrideConnectionGroups": [
                                {"AddressablesCatalogUrlRoot": "https://ignore.invalid/root"},
                                {"AddressablesCatalogUrlRoot": catalog_root},
                                {"AddressablesCatalogUrlRoot": "https://last.invalid/root"},
                            ]
                        }
                    ]
                }
            ).encode("utf-8"),
            url=server_url,
        ),
        (
            "GET",
            f"{catalog_root}/TableBundles/TableCatalog.bytes",
        ): HttpResponse(
            status_code=200,
            headers={"content-type": "application/octet-stream"},
            content=_build_table_catalog_bytes(),
            url=f"{catalog_root}/TableBundles/TableCatalog.bytes",
        ),
        (
            "GET",
            f"{catalog_root}/MediaResources/Catalog/MediaCatalog.bytes",
        ): HttpResponse(
            status_code=200,
            headers={"content-type": "application/octet-stream"},
            content=_build_media_catalog_bytes(),
            url=f"{catalog_root}/MediaResources/Catalog/MediaCatalog.bytes",
        ),
        (
            "GET",
            f"{catalog_root}/Android_PatchPack/BundlePackingInfo.json",
        ): HttpResponse(
            status_code=200,
            headers={"content-type": "application/json; charset=utf-8"},
            content=json.dumps(
                {
                    "FullPatchPacks": [
                        {
                            "PackName": "bundle/full.pack",
                            "PackSize": 99,
                            "Crc": 1234,
                            "IsPrologue": False,
                            "BundleFiles": [
                                {"Name": "character.bundle"},
                                {"Name": "ui.bundle"},
                            ],
                        }
                    ],
                    "UpdatePacks": [
                        {
                            "PackName": "bundle/update.pack",
                            "PackSize": 100,
                            "Crc": 5678,
                            "BundleFiles": [
                                {"Name": "raid.bundle"},
                            ],
                        }
                    ],
                }
            ).encode("utf-8"),
            url=f"{catalog_root}/Android_PatchPack/BundlePackingInfo.json",
        ),
    }
    client = RecordingHttpClient(responses)
    provider = JPServer(client, NullLogger())

    resources = provider.get_resource_manifest(server_url)

    assert len(resources) == 5
    assert (
        "GET",
        f"{catalog_root}/Android_PatchPack/BundlePackingInfo.json",
    ) in client.calls
    assert (
        "GET",
        f"{catalog_root}/Android/bundleDownloadInfo.json",
    ) not in client.calls
    assert any(item.path == "Table/MainTable.bytes" for item in resources)
    assert any(item.path == "Table/PackTable.bytes" for item in resources)
    assert any(item.path == "Media/GameData/Audio/BGM/title_theme.zip" for item in resources)
    bundle_items = [item for item in resources if item.path.startswith("Bundle/")]
    assert {item.path for item in bundle_items} == {
        "Bundle/bundle/full.pack",
        "Bundle/bundle/update.pack",
    }
    assert bundle_items[0].metadata["bundle_files"]


def test_search_name_matches_jp_bundle_files_from_patch_pack() -> None:
    server_url = "https://example.invalid/server-info.json"
    catalog_root = "https://cdn.example.invalid/catalog-root"
    client = RecordingHttpClient(
        {
            ("GET", server_url): HttpResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                content=json.dumps(
                    {
                        "ConnectionGroups": [
                            {
                                "OverrideConnectionGroups": [
                                    {"AddressablesCatalogUrlRoot": "https://ignore.invalid/root"},
                                    {"AddressablesCatalogUrlRoot": catalog_root},
                                ]
                            }
                        ]
                    }
                ).encode("utf-8"),
                url=server_url,
            ),
            ("GET", f"{catalog_root}/TableBundles/TableCatalog.bytes"): HttpResponse(
                status_code=200,
                headers={},
                content=_build_table_catalog_bytes(),
                url=f"{catalog_root}/TableBundles/TableCatalog.bytes",
            ),
            ("GET", f"{catalog_root}/MediaResources/Catalog/MediaCatalog.bytes"): HttpResponse(
                status_code=200,
                headers={},
                content=_build_media_catalog_bytes(),
                url=f"{catalog_root}/MediaResources/Catalog/MediaCatalog.bytes",
            ),
            ("GET", f"{catalog_root}/Android_PatchPack/BundlePackingInfo.json"): HttpResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                content=json.dumps(
                    {
                        "FullPatchPacks": [
                            {
                                "PackName": "bundle/full.pack",
                                "PackSize": 99,
                                "Crc": 1234,
                                "BundleFiles": [
                                    {"Name": "character.bundle"},
                                ],
                            }
                        ]
                    }
                ).encode("utf-8"),
                url=f"{catalog_root}/Android_PatchPack/BundlePackingInfo.json",
            ),
        }
    )
    provider = JPServer(client, NullLogger())

    resources = provider.get_resource_manifest(server_url)
    filtered = ResourceQueryService.search_name(resources, ["character.bundle"])

    assert len(filtered) == 1
    assert filtered[0].path == "Bundle/bundle/full.pack"


@pytest.mark.parametrize(
    ("platform", "patch_dir"),
    [
        ("windows", "Windows_PatchPack"),
        ("ios", "iOS_PatchPack"),
    ],
)
def test_jp_catalog_source_provider_uses_selected_platform_for_bundle_manifest(
    platform: str,
    patch_dir: str,
) -> None:
    catalog_root = "https://cdn.example.invalid/catalog-root"
    context = RuntimeContext(
        region="jp",
        threads=4,
        version="1.2.3",
        raw_dir="Raw",
        extract_dir="Extracted",
        temp_dir="Temp",
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=".",
        platform=platform,
        platform_explicit=True,
    )
    session = BootstrapSession(
        release=ResolvedRelease(region="jp", version="1.2.3"),
        server_url="https://example.invalid/server-info.json",
        catalog_root=catalog_root,
    )
    client = RecordingHttpClient(
        {
            ("GET", f"{catalog_root}/TableBundles/TableCatalog.bytes"): HttpResponse(
                status_code=200,
                headers={},
                content=_build_table_catalog_bytes(),
                url=f"{catalog_root}/TableBundles/TableCatalog.bytes",
            ),
            ("GET", f"{catalog_root}/MediaResources/Catalog/MediaCatalog.bytes"): HttpResponse(
                status_code=200,
                headers={},
                content=_build_media_catalog_bytes(),
                url=f"{catalog_root}/MediaResources/Catalog/MediaCatalog.bytes",
            ),
            ("GET", f"{catalog_root}/{patch_dir}/BundlePackingInfo.json"): HttpResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                content=json.dumps({"FullPatchPacks": [], "UpdatePacks": []}).encode("utf-8"),
                url=f"{catalog_root}/{patch_dir}/BundlePackingInfo.json",
            ),
        }
    )
    provider = JPServer(client, NullLogger())

    provider.catalog_source_provider.fetch(session, context)

    assert ("GET", f"{catalog_root}/{patch_dir}/BundlePackingInfo.json") in client.calls
    assert ("GET", f"{catalog_root}/Android_PatchPack/BundlePackingInfo.json") not in client.calls


@pytest.mark.parametrize(
    ("patch_dir", "expected_url"),
    [
        (
            "Windows_PatchPack",
            "https://cdn.example.invalid/catalog-root/Windows_PatchPack/bundle/full.pack",
        ),
        (
            "iOS_PatchPack",
            "https://cdn.example.invalid/catalog-root/iOS_PatchPack/bundle/full.pack",
        ),
    ],
)
def test_jp_asset_normalizer_uses_platform_specific_bundle_urls(
    patch_dir: str,
    expected_url: str,
) -> None:
    session = BootstrapSession(
        release=ResolvedRelease(region="jp", version="1.2.3"),
        server_url="https://example.invalid/server-info.json",
        catalog_root="https://cdn.example.invalid/catalog-root",
        metadata={"bundle_patch_dir": patch_dir},
    )
    payload = DecodedJPCatalog(
        tables=[],
        media=[],
        bundles=[
            {
                "name": "bundle/full.pack",
                "size": 99,
                "crc": 1234,
                "bundle_files": ["character.bundle"],
            }
        ],
    )
    provider = JPServer(RecordingHttpClient({}), NullLogger())

    assets = provider.asset_normalizer.normalize(payload, session)

    assert assets[0].url == expected_url
    assert assets[0].path == "Bundle/bundle/full.pack"


def test_load_catalog_logs_happy_path_at_info_level(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = RecordingLogger()
    provider = JPServer(RecordingHttpClient({}), logger)
    context = RuntimeContext(
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
    resolved_context = context.with_updates(version="1.2.3")
    resources = AssetCollection()

    monkeypatch.setattr(provider.pipeline, "load", lambda active_context: (resources, resolved_context))

    result = provider.load_catalog(context)

    assert result.context == resolved_context
    assert logger.warn_messages == []
    assert logger.info_messages == [
        "Automatically fetching latest package info...",
        "Current resource version: 1.2.3",
        "Catalog: 0 items in the catalog, totaling 0.0GB.",
    ]


def test_jp_bootstrap_translates_package_download_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    bootstrapper = JPBootstrapper(RecordingHttpClient({}), NullLogger())
    context = RuntimeContext(
        region="jp",
        threads=4,
        version="1.2.3",
        raw_dir="Raw",
        extract_dir="Extracted",
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )
    release = ResolvedRelease(
        region="jp",
        version="1.2.3",
        package_url="https://download.example.com/archive.xapk",
    )

    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.providers.jp.download_package_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            PackageArchiveError("Package archive validation failed for bad.xapk.")
        ),
    )

    with pytest.raises(LookupError, match="Downloaded JP package is invalid or incomplete"):
        bootstrapper.bootstrap(release, context)


def test_jp_bootstrap_translates_package_extraction_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package_path = tmp_path / "broken.xapk"
    package_path.write_bytes(b"not a zip archive")
    bootstrapper = JPBootstrapper(RecordingHttpClient({}), NullLogger())
    context = RuntimeContext(
        region="jp",
        threads=4,
        version="1.2.3",
        raw_dir="Raw",
        extract_dir="Extracted",
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )
    release = ResolvedRelease(
        region="jp",
        version="1.2.3",
        package_url="https://download.example.com/archive.xapk",
    )

    monkeypatch.setattr(
        "ba_downloader.infrastructure.regions.providers.jp.download_package_file",
        lambda *args, **kwargs: str(package_path),
    )

    with pytest.raises(LookupError, match="Downloaded JP package is invalid or incomplete"):
        bootstrapper.bootstrap(release, context)
