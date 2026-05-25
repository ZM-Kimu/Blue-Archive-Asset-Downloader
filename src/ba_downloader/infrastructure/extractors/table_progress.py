from __future__ import annotations

from collections.abc import Callable

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.table_models import (
    CANCELLED_EXTRACTION_MESSAGE,
    ProgressCallback,
)


class TableExtractionProgress:
    def __init__(self, logger: LoggerPort) -> None:
        self.logger = logger

    @staticmethod
    def ensure_not_cancelled(should_stop: Callable[[], bool] | None) -> None:
        if should_stop is not None and should_stop():
            raise RuntimeError(CANCELLED_EXTRACTION_MESSAGE)

    @staticmethod
    def is_cancelled(exc: RuntimeError) -> bool:
        return str(exc) == CANCELLED_EXTRACTION_MESSAGE

    @staticmethod
    def is_generated_stop_iteration(exc: RuntimeError) -> bool:
        return str(exc) == "generator raised StopIteration"

    @staticmethod
    def notify_progress(
        progress_callback: ProgressCallback | None,
        current: int,
        total: int,
        unit: str,
    ) -> None:
        if progress_callback is not None:
            progress_callback(f"{current}/{total} {unit}")

    def warn_skipped_entry(
        self,
        archive_name: str,
        entry_name: str,
        warnings: list[str],
        error: str,
    ) -> None:
        warning = f"Skipping {entry_name} in {archive_name}: {error}"
        self.logger.warn(warning)
        warnings.append(warning)
