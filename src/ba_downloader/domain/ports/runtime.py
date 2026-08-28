from typing import Protocol

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets


class RuntimeAssetPreparerPort(Protocol):
    def prepare(self, context: ExecutionContext) -> PreparedRuntimeAssets: ...
