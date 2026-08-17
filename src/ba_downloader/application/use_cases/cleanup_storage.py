from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.storage import StorageCleanupTarget
from ba_downloader.domain.ports.execution import CancellationPort
from ba_downloader.domain.ports.storage import StorageCleanupPort


class CleanupStorageUseCase:
    def __init__(
        self,
        storage: StorageCleanupPort,
        cancellation: CancellationPort,
    ) -> None:
        self._storage = storage
        self._cancellation = cancellation

    def run(
        self,
        context: RuntimeContext,
        targets: tuple[StorageCleanupTarget, ...],
    ) -> int:
        deleted = 0
        for target in targets:
            self._cancellation.raise_if_cancelled()
            self._storage.delete(context, target)
            deleted += 1
        self._cancellation.raise_if_cancelled()
        return deleted
