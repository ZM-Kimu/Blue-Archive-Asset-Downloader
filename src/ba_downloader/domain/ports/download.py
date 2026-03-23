from typing import Protocol

from ba_downloader.domain.models.resource import Resource
from ba_downloader.domain.models.runtime import RuntimeContext


class ResourceDownloaderPort(Protocol):
    def verify_and_download(self, resources: Resource, context: RuntimeContext) -> None:
        ...
