from typing import Protocol

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets


class RuntimeAssetPreparerPort(Protocol):
    def prepare(self, context: RuntimeContext) -> PreparedRuntimeAssets: ...
