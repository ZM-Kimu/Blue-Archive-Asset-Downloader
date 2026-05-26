from __future__ import annotations

from typing import Protocol

from ba_downloader.domain.models.asset import AssetRecord
from ba_downloader.domain.models.runtime import RuntimeContext


class ImmediateExtractionHandler(Protocol):
    def __call__(
        self,
        resource: AssetRecord,
        context: RuntimeContext,
    ) -> None: ...
