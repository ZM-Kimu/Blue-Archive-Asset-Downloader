from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext


@dataclass(frozen=True, slots=True)
class OperationOutcome:
    context: ExecutionContext
    artifacts: tuple[tuple[str, str], ...] = ()
    catalog: AssetCollection | None = None
    statistics: tuple[tuple[str, int], ...] = ()
    warnings: tuple[str, ...] = ()
