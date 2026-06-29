from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ba_downloader.domain.models.runtime import RuntimeContext


class SyncExtractionMode(Enum):
    direct = "direct"
    post_download = "post_download"


@dataclass(frozen=True, slots=True)
class SyncWorkflowPolicy:
    prepares_schema: bool
    extraction_mode: SyncExtractionMode

    @property
    def requires_schema_preparation(self) -> bool:
        return self.prepares_schema


def resolve_sync_workflow_policy(context: RuntimeContext) -> SyncWorkflowPolicy:
    if context.region == "gl":
        return SyncWorkflowPolicy(
            prepares_schema=True,
            extraction_mode=SyncExtractionMode.direct,
        )
    if context.region in {"cn", "jp"}:
        return SyncWorkflowPolicy(
            prepares_schema=True,
            extraction_mode=SyncExtractionMode.post_download,
        )
    return SyncWorkflowPolicy(
        prepares_schema=False,
        extraction_mode=SyncExtractionMode.post_download,
    )
