from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext


class ResourceDownloaderPort(Protocol):
    def verify_and_download(
        self,
        resources: AssetCollection,
        context: ExecutionContext,
        *,
        concurrency: int,
    ) -> None: ...
