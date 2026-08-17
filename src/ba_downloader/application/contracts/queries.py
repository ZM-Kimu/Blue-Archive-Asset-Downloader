from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.application.contracts.commands import (
    AssetOperationKind,
    AssetOperationOptions,
)


@dataclass(frozen=True, slots=True)
class PreviewAssetsQuery:
    operation: AssetOperationKind
    options: AssetOperationOptions
