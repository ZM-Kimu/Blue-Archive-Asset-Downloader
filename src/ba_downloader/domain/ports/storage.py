from pathlib import Path
from typing import Protocol

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.storage import StorageCleanupTarget


class StorageCleanupPort(Protocol):
    def delete(
        self,
        context: ExecutionContext,
        target: StorageCleanupTarget,
    ) -> Path: ...
