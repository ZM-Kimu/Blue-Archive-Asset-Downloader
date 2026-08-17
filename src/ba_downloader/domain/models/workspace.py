from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ba_downloader.domain.models.region import Platform, Region


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    root: Path
    region: Region
    platform: Platform

    @classmethod
    def create(
        cls,
        root: str | Path,
        region: Region,
        platform: Platform,
    ) -> WorkspaceLayout:
        return cls(
            root=Path(root).expanduser().resolve(strict=False),
            region=region,
            platform=platform,
        )

    @property
    def base(self) -> Path:
        return self.root / self.region / self.platform

    @property
    def raw(self) -> Path:
        return self.base / "raw"

    @property
    def raw_tables(self) -> Path:
        return self.raw / "tables"

    @property
    def raw_media(self) -> Path:
        return self.raw / "media"

    @property
    def raw_bundles(self) -> Path:
        return self.raw / "bundles"

    @property
    def extracted(self) -> Path:
        return self.base / "extracted"

    @property
    def extracted_tables(self) -> Path:
        return self.extracted / "tables"

    @property
    def extracted_table_semantic(self) -> Path:
        return self.extracted_tables / "semantic"

    @property
    def extracted_table_raw(self) -> Path:
        return self.extracted_tables / "raw"

    @property
    def extracted_media(self) -> Path:
        return self.extracted / "media"

    @property
    def extracted_bundles(self) -> Path:
        return self.extracted / "bundles"

    @property
    def extracted_schemas(self) -> Path:
        return self.extracted / "schemas"

    @property
    def flatbuffer_schemas(self) -> Path:
        return self.extracted_schemas / "flatbuffers"

    @property
    def memorypack_schemas(self) -> Path:
        return self.extracted_schemas / "memorypack"

    @property
    def dumps(self) -> Path:
        return self.extracted / "dumps"

    @property
    def indexes(self) -> Path:
        return self.base / "indexes"

    @property
    def character_index(self) -> Path:
        return self.indexes / "characters.json"

    @property
    def state(self) -> Path:
        return self.base / ".state"

    @property
    def runtime_state(self) -> Path:
        return self.state / "runtime"

    @property
    def schema_state(self) -> Path:
        return self.state / "schema"

    @property
    def cache_state(self) -> Path:
        return self.state / "cache"

    @property
    def temp_state(self) -> Path:
        return self.state / "temp"

    @property
    def log_state(self) -> Path:
        return self.state / "logs"

    @property
    def manifest_state(self) -> Path:
        return self.state / "manifests"
