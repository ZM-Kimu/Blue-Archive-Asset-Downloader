from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SyncExtractionMode(Enum):
    direct = "direct"
    post_download = "post_download"


@dataclass(frozen=True, slots=True)
class RegionWorkflowPolicy:
    prepares_schema_for_sync: bool
    sync_extraction_mode: SyncExtractionMode
    table_extraction_prerequisite: bool = False


@dataclass(frozen=True, slots=True)
class RegionSettingsPolicy:
    include_platform_in_default_dirs: bool = False
    retain_sqlcipher_key_hex: bool = False
    character_index_command_includes_version: bool = True
