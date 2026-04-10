from typing import Protocol

from ba_downloader.domain.models.runtime import RuntimeContext


class RuntimeAssetPreparerPort(Protocol):
    def prepare(self, context: RuntimeContext) -> None: ...
