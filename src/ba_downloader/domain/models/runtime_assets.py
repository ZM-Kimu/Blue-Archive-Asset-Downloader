from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PreparedRuntimeAssets:
    version: str
    root_dir: Path
    binary_path: Path
    metadata_path: Path
    globalgamemanagers_path: Path | None = None
