from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.asset_type_selection import ResourceTypeSelection
from ba_downloader.domain.models.storage import StorageCleanupTarget


@dataclass(frozen=True, slots=True)
class AssetOperationOptions:
    concurrency: int = 30
    resources: ResourceTypeSelection = field(
        default_factory=lambda: ResourceTypeSelection.from_values(())
    )
    asset_filter: AssetFilter = field(default_factory=AssetFilter)

    def __post_init__(self) -> None:
        _validate_concurrency(self.concurrency)


@dataclass(frozen=True, slots=True)
class AssetsSyncCommand:
    options: AssetOperationOptions = field(default_factory=AssetOperationOptions)


@dataclass(frozen=True, slots=True)
class AssetsDownloadCommand:
    options: AssetOperationOptions = field(default_factory=AssetOperationOptions)


@dataclass(frozen=True, slots=True)
class AssetsExtractCommand:
    options: AssetOperationOptions = field(default_factory=AssetOperationOptions)


@dataclass(frozen=True, slots=True)
class BuildCharacterIndexCommand:
    concurrency: int = 30

    def __post_init__(self) -> None:
        _validate_concurrency(self.concurrency)


@dataclass(frozen=True, slots=True)
class CatalogRefreshCommand:
    pass


@dataclass(frozen=True, slots=True)
class StorageCleanupCommand:
    targets: tuple[StorageCleanupTarget, ...]

    def __post_init__(self) -> None:
        if not self.targets:
            raise ConfigError("Storage cleanup command requires at least one target.")


ApplicationCommand: TypeAlias = (
    AssetsSyncCommand
    | AssetsDownloadCommand
    | AssetsExtractCommand
    | BuildCharacterIndexCommand
    | CatalogRefreshCommand
    | StorageCleanupCommand
)


def _validate_concurrency(concurrency: int) -> None:
    if concurrency <= 0:
        raise ConfigError("Operation concurrency must be greater than zero.")
