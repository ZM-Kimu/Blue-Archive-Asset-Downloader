from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ba_downloader.domain.models.runtime import RuntimeContext


class SyncExtractionMode(Enum):
    direct = "direct"
    post_download = "post_download"


@dataclass(frozen=True, slots=True)
class SyncWorkflowPolicy:
    requires_schema_workflow: bool
    extraction_mode: SyncExtractionMode


def resolve_sync_workflow_policy(context: RuntimeContext) -> SyncWorkflowPolicy:
    if context.region == "gl":
        return SyncWorkflowPolicy(
            requires_schema_workflow=True,
            extraction_mode=SyncExtractionMode.direct,
        )
    if context.region in {"cn", "jp"}:
        return SyncWorkflowPolicy(
            requires_schema_workflow=True,
            extraction_mode=SyncExtractionMode.post_download,
        )
    return SyncWorkflowPolicy(
        requires_schema_workflow=False,
        extraction_mode=SyncExtractionMode.post_download,
    )
