from dataclasses import dataclass
from pathlib import Path

from ba_downloader.domain.models.execution import ExecutionContext


def bundle_extraction_lock_path(context: ExecutionContext) -> Path:
    return (
        context.workspace.locks
        / context.region
        / context.platform
        / "bundle-extraction.lock"
    )


@dataclass(frozen=True, slots=True)
class BundleExtractionReport:
    warnings: tuple[str, ...] = ()
    total_batches: int = 0
    succeeded_batches: int = 0
    failed_batches: int = 0
    skipped_archives: int = 0
    skipped_components: int = 0
