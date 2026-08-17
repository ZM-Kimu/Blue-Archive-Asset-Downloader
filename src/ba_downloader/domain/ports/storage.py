from pathlib import Path
from typing import Protocol

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.storage import StorageCleanupTarget


class StorageCleanupPort(Protocol):
    def delete(
        self,
        context: RuntimeContext,
        target: StorageCleanupTarget,
    ) -> Path: ...
