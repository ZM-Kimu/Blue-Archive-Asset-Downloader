from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Generic, TypeVar

from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.execution import ExecutionContext

ResultData = TypeVar("ResultData")


@dataclass(frozen=True, slots=True)
class OperationWarning:
    code: str
    message: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ConfigError("Operation warning code and message must not be empty.")


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    scope: str
    relative_path: PurePosixPath

    def __post_init__(self) -> None:
        if not self.scope.strip():
            raise ConfigError("Artifact scope must not be empty.")
        if (
            self.relative_path.is_absolute()
            or self.relative_path == PurePosixPath(".")
            or ".." in self.relative_path.parts
        ):
            raise ConfigError("Artifact path must be a safe relative path.")


@dataclass(frozen=True, slots=True)
class AssetOperationStats:
    selected: int = 0
    downloaded: int = 0
    extracted: int = 0

    def __post_init__(self) -> None:
        _validate_counts(self.selected, self.downloaded, self.extracted)


@dataclass(frozen=True, slots=True)
class CharacterIndexOperationStats:
    entries: int = 0

    def __post_init__(self) -> None:
        _validate_counts(self.entries)


@dataclass(frozen=True, slots=True)
class StorageCleanupStats:
    files_removed: int = 0
    bytes_reclaimed: int = 0

    def __post_init__(self) -> None:
        _validate_counts(self.files_removed, self.bytes_reclaimed)


@dataclass(frozen=True, slots=True)
class OperationResult(Generic[ResultData]):
    context: ExecutionContext
    duration_seconds: float
    data: ResultData
    warnings: tuple[OperationWarning, ...] = ()
    artifacts: tuple[ArtifactReference, ...] = ()

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ConfigError("Operation duration must not be negative.")


def _validate_counts(*counts: int) -> None:
    if any(count < 0 for count in counts):
        raise ConfigError("Operation statistics must not contain negative counts.")
