from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    RegionCapabilities,
)
from ba_downloader.domain.models.region import Platform, Region
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext

LogLevel = Literal["info", "warn", "error"]


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


def build_runtime_context(
    tmp_path: Path,
    *,
    region: Region = "jp",
    version: str = "1.0.0",
    platform: Platform = "android",
    resource_type: tuple[str, ...] = ("table", "media", "bundle"),
    search: tuple[str, ...] = (),
    advanced_search: tuple[str, ...] = (),
    **overrides: Any,
) -> RuntimeContext:
    values: dict[str, Any] = {
        "region": region,
        "threads": 1,
        "version": version,
        "raw_dir": str(tmp_path / "RawData"),
        "extract_dir": str(tmp_path / "Extracted"),
        "temp_dir": str(tmp_path / "Temp"),
        "extract_while_download": False,
        "resource_type": resource_type,
        "proxy_url": "",
        "max_retries": 1,
        "search": search,
        "advanced_search": advanced_search,
        "work_dir": str(tmp_path),
        "platform": platform,
        "platform_explicit": False,
        "sqlcipher_key_hex": "",
    }
    values.update(overrides)
    return RuntimeContext(**values)


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
        self.calls: list[RuntimeContext] = []

    def get_capabilities(self) -> RegionCapabilities:
        return self.capabilities

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        self.calls.append(context)
        return self.result


class DummyCharacterIndexBuilder:
    def __init__(
        self,
        *,
        index_file_valid: bool = True,
        search_results: list[str] | None = None,
        excel_resources: AssetCollection | None = None,
    ) -> None:
        self.index_file_valid = index_file_valid
        self.search_results = search_results or ["Shiroko"]
        self.excel_resources = excel_resources
        self.build_calls: list[RuntimeContext] = []
        self.search_calls: list[list[str]] = []
        self.verify_calls = 0

    def build(self, context: RuntimeContext) -> None:
        self.build_calls.append(context)
        self.index_file_valid = True

    def get_excel_resources(self, resources: AssetCollection) -> AssetCollection:
        return self.excel_resources or resources

    def search(self, context: RuntimeContext, search_terms: list[str]) -> list[str]:
        _ = context
        self.search_calls.append(list(search_terms))
        return self.search_results

    def verify_index_file(self, context: RuntimeContext) -> bool:
        _ = context
        self.verify_calls += 1
        return self.index_file_valid
