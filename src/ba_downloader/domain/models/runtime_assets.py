from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PreparedRuntimeAssets:
    version: str
    root_dir: Path
    binary_path: Path
    metadata_path: Path
    globalgamemanagers_path: Path | None = None
    file_fingerprints: dict[str, dict[str, object]] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
