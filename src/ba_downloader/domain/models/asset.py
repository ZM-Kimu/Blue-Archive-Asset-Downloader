from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, overload

ChecksumAlgorithm = Literal["crc", "md5"]


class AssetType(str, Enum):
    table = "table"
    media = "media"
    bundle = "bundle"


@dataclass(frozen=True, slots=True)
class ChecksumSpec:
    algorithm: ChecksumAlgorithm
    value: str


@dataclass(frozen=True, slots=True)
class AssetRecord:
    url: str
    path: str
    size: int
    checksum: ChecksumSpec
    asset_type: AssetType
    metadata: dict[str, Any] = field(default_factory=dict)


class AssetCollection:
    def __init__(self, assets: Iterable[AssetRecord] | None = None) -> None:
        self.assets: list[AssetRecord] = list(assets or [])

    def __bool__(self) -> bool:
        return bool(self.assets)

    @overload
    def __getitem__(self, index: slice) -> list[AssetRecord]: ...

    @overload
    def __getitem__(self, index: int) -> AssetRecord: ...

    def __getitem__(self, index: slice | int) -> list[AssetRecord] | AssetRecord:
        if isinstance(index, slice):
            return self.assets[index.start : index.stop : index.step]
        return self.assets[index]

    def __len__(self) -> int:
        return len(self.assets)

    def __iter__(self) -> Iterator[AssetRecord]:
        return iter(self.assets)

    def __repr__(self) -> str:
        size = sum(item.size for item in self.assets)
        return (
            f"{len(self)} items in the catalog, totaling {round(size / (1024**3), 2)}GB"
        )

    def add(
        self,
        url: str,
        path: str,
        size: int,
        checksum: str,
        algorithm: ChecksumAlgorithm,
        asset_type: AssetType,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.assets.append(
            AssetRecord(
                url=url,
                path=path,
                size=size,
                checksum=ChecksumSpec(algorithm=algorithm, value=str(checksum)),
                asset_type=asset_type,
                metadata=dict(metadata or {}),
            )
        )

    def add_item(self, item: AssetRecord) -> None:
        self.assets.append(item)

    def search(
        self, attr: str, value: Any, exact_match: bool = False
    ) -> AssetCollection:
        filtered = AssetCollection()

        def contains_comparator(left: Any, right: Any) -> bool:
            return str(left).lower() in str(right).lower()

        def exact_comparator(left: Any, right: Any) -> bool:
            return left == right

        comparator: Callable[[Any, Any], bool] = (
            exact_comparator if exact_match else contains_comparator
        )

        for item in self.assets:
            if comparator(value, getattr(item, attr)):
                filtered.add_item(item)
        return filtered

    def sorted_by_size(self, descending: bool = True) -> None:
        self.assets.sort(key=lambda item: item.size, reverse=descending)


@dataclass(frozen=True, slots=True)
class ResolvedRelease:
    region: str
    version: str
    package_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BootstrapSession:
    release: ResolvedRelease
    server_url: str
    catalog_root: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CatalogSource:
    name: str
    url: str
    content: bytes
    content_type: str = ""


@dataclass(frozen=True, slots=True)
class RegionCapabilities:
    supports_sync: bool = True
    supports_advanced_search: bool = True
    supports_relation_build: bool = True
