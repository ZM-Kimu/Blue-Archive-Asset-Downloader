from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal, TypeAlias

from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.asset_type_selection import ResourceTypeSelection


class AssetOperationKind(StrEnum):
    sync = "assets.sync"
    download = "assets.download"
    extract = "assets.extract"


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


class CleanupScope(StrEnum):
    raw = "raw"
    extracted = "extracted"
    indexes = "indexes"
    cache = "cache"
    temp = "temp"
    old_snapshots = "old-snapshots"
    failed_staging = "failed-staging"
    logs = "logs"


CleanupTargetType = Literal["file", "directory"]


@dataclass(frozen=True, slots=True)
class CleanupTarget:
    scope: CleanupScope
    relative_path: PurePosixPath
    expected_type: CleanupTargetType

    def __post_init__(self) -> None:
        if (
            self.relative_path.is_absolute()
            or self.relative_path == PurePosixPath(".")
            or ".." in self.relative_path.parts
        ):
            raise ConfigError("Cleanup target path must be a safe relative path.")


@dataclass(frozen=True, slots=True)
class StorageCleanupCommand:
    targets: tuple[CleanupTarget, ...]

    def __post_init__(self) -> None:
        if not self.targets:
            raise ConfigError("Storage cleanup command requires at least one target.")


ApplicationCommand: TypeAlias = (
    AssetsSyncCommand
    | AssetsDownloadCommand
    | AssetsExtractCommand
    | BuildCharacterIndexCommand
    | StorageCleanupCommand
)


def _validate_concurrency(concurrency: int) -> None:
    if concurrency <= 0:
        raise ConfigError("Operation concurrency must be greater than zero.")
