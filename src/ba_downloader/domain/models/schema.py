from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SchemaPurpose(StrEnum):
    FULL = "full"
    CHARACTER_INDEX = "character_index"


@dataclass(frozen=True, slots=True)
class PreparedSchemaSnapshot:
    purpose: SchemaPurpose
    root_dir: Path
    flatbuffer_path: Path
    memorypack_path: Path | None
    dumps_path: Path | None
    fingerprint: str
