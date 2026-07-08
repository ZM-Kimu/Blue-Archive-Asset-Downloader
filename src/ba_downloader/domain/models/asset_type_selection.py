from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ba_downloader.domain.models.asset import AssetType

ALL_RESOURCE_TYPES: tuple[AssetType, ...] = (
    AssetType.table,
    AssetType.media,
    AssetType.bundle,
)


@dataclass(frozen=True, slots=True)
class ResourceTypeSelection:
    types: tuple[AssetType, ...]

    @classmethod
    def from_values(
        cls,
        values: Iterable[str | AssetType],
    ) -> ResourceTypeSelection:
        normalized: list[AssetType] = []
        seen: set[AssetType] = set()
        raw_values = tuple(values)
        if not raw_values or any(str(value).lower() == "all" for value in raw_values):
            return cls(ALL_RESOURCE_TYPES)

        for value in raw_values:
            asset_type = value if isinstance(value, AssetType) else AssetType(value)
            if asset_type in seen:
                continue
            normalized.append(asset_type)
            seen.add(asset_type)
        return cls(tuple(normalized))

    def contains(self, asset_type: AssetType | str) -> bool:
        normalized = (
            asset_type if isinstance(asset_type, AssetType) else AssetType(asset_type)
        )
        return normalized in self.types

    def as_strings(self) -> tuple[str, ...]:
        return tuple(asset_type.value for asset_type in self.types)
