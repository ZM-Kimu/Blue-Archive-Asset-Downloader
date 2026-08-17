from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StorageScope = Literal[
    "raw",
    "extracted",
    "indexes",
    "cache",
    "temp",
    "old-snapshots",
    "failed-staging",
    "logs",
]
StorageTargetType = Literal["file", "directory"]


@dataclass(frozen=True, slots=True)
class StorageCleanupTarget:
    scope: StorageScope
    relative_path: str
    expected_type: StorageTargetType

    def as_dict(self) -> dict[str, str]:
        return {
            "scope": self.scope,
            "relative_path": self.relative_path,
            "expected_type": self.expected_type,
        }
