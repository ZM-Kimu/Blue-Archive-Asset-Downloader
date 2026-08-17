from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.region import Platform, Region


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    region: Region
    threads: int
    version: str
    raw_dir: str
    extract_dir: str
    temp_dir: str
    resource_type: tuple[str, ...]
    proxy_url: str
    max_retries: int
    search: tuple[str, ...]
    advanced_search: tuple[str, ...]
    work_dir: str
    platform: Platform = "android"
    platform_explicit: bool = False
    sqlcipher_key_hex: str = ""
    workspace_mode: Literal["legacy", "v3"] = "legacy"
    asset_filter: AssetFilter = field(default_factory=AssetFilter)
    database_source_identity: DatabaseSourceIdentity | None = None
    schema_snapshot_root: str = ""

    @property
    def proxy(self) -> dict[str, str] | None:
        if not self.proxy_url:
            return None
        return {"http": self.proxy_url, "https": self.proxy_url}

    def with_updates(self, **changes: Any) -> RuntimeContext:
        return replace(self, **changes)
