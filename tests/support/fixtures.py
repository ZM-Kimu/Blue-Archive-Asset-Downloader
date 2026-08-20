from __future__ import annotations

from pathlib import Path
from typing import Literal

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.character import CharacterIndex
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region import Platform, Region
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.workspace import WorkspaceLayout

LogLevel = Literal["info", "warn", "error"]


def _encode_protobuf_varint(value: int) -> bytes:
    encoded = bytearray()
    while value >= 0x80:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _encode_protobuf_bytes(field_number: int, value: bytes) -> bytes:
    return (
        _encode_protobuf_varint((field_number << 3) | 2)
        + _encode_protobuf_varint(len(value))
        + value
    )


def build_apkpure_version_list(
    package_name: str,
    *releases: tuple[str, str],
) -> bytes:
    records = bytearray()
    for index, (version, download_url) in enumerate(releases, start=1):
        download = b"".join(
            (
                _encode_protobuf_bytes(8, b"XAPK"),
                _encode_protobuf_bytes(9, download_url.encode("utf8")),
            )
        )
        record = b"".join(
            (
                _encode_protobuf_bytes(4, package_name.encode("utf8")),
                _encode_protobuf_bytes(5, str(index).encode("ascii")),
                _encode_protobuf_bytes(6, version.encode("ascii")),
                _encode_protobuf_bytes(24, download),
                _encode_protobuf_bytes(
                    36,
                    f"2026-01-{index:02d}T00:00:00".encode("ascii"),
                ),
            )
        )
        records.extend(_encode_protobuf_bytes(2, record))

    section = b"".join(
        (
            _encode_protobuf_bytes(1, b"version_list"),
            _encode_protobuf_bytes(3, bytes(records)),
        )
    )
    body = _encode_protobuf_bytes(2, section)
    response = _encode_protobuf_bytes(7, body)
    return _encode_protobuf_bytes(1, response)


class RecordingLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[LogLevel, str]] = []

    def info(self, message: str) -> None:
        self.messages.append(("info", message))

    def warn(self, message: str) -> None:
        self.messages.append(("warn", message))

    def error(self, message: str) -> None:
        self.messages.append(("error", message))

    def by_level(self, level: LogLevel) -> list[str]:
        return [
            message
            for message_level, message in self.messages
            if message_level == level
        ]

    def contains(self, text: str, *, level: LogLevel | None = None) -> bool:
        return any(
            text in message
            for message_level, message in self.messages
            if level is None or message_level == level
        )


def build_execution_context(
    tmp_path: Path,
    *,
    region: Region = "jp",
    version: str = "1.0.0",
    platform: Platform = "android",
    proxy_url: str = "",
    max_retries: int = 1,
    sqlcipher_key: str = "",
) -> ExecutionContext:
    return ExecutionContext(
        region=region,
        platform=platform,
        workspace=WorkspaceLayout.create(tmp_path, region, platform),
        proxy_url=proxy_url,
        max_retries=max_retries,
        sqlcipher_key=sqlcipher_key,
        resource_version=version or None,
    )


def build_asset_collection(
    *items: tuple[str, AssetType] | tuple[str, AssetType, int],
    base_url: str = "https://example.invalid/assets/",
) -> AssetCollection:
    resources = AssetCollection()
    for item in items:
        path, asset_type, *rest = item
        size = rest[0] if rest else 1
        resources.add(
            url=f"{base_url}{path}",
            path=path,
            size=size,
            checksum="0",
            algorithm="crc",
            asset_type=asset_type,
        )
    return resources


class StaticProvider:
    def __init__(
        self,
        result: RegionCatalogResult,
        capabilities: RegionCapabilities | None = None,
    ) -> None:
        self.result = result
        self.capabilities = capabilities or RegionCapabilities()
        self.calls: list[ExecutionContext] = []

    def get_capabilities(self) -> RegionCapabilities:
        return self.capabilities

    def load_catalog(self, context: ExecutionContext) -> RegionCatalogResult:
        self.calls.append(context)
        return self.result


class DummyCharacterIndexBuilder:
    def __init__(
        self,
        *,
        index_file_valid: bool = True,
        excel_resources: AssetCollection | None = None,
        index: CharacterIndex | None = None,
    ) -> None:
        self.index_file_valid = index_file_valid
        self.excel_resources = excel_resources
        self.index = index or CharacterIndex("", [])
        self.build_calls: list[ExecutionContext] = []
        self.verify_calls = 0

    def build(self, context: ExecutionContext, **_: object) -> None:
        self.build_calls.append(context)
        self.index_file_valid = True

    def get_excel_resources(self, resources: AssetCollection) -> AssetCollection:
        return self.excel_resources or resources

    def verify_index_file(self, context: ExecutionContext) -> bool:
        _ = context
        self.verify_calls += 1
        return self.index_file_valid

    def load(self, context: ExecutionContext) -> CharacterIndex:
        _ = context
        return self.index
