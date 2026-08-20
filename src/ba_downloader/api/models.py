from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, SecretStr

from ba_downloader.api.state import ApiContext
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region import Platform, Region


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContextCreateRequest(StrictModel):
    region: Region
    platform: Platform = "android"
    workspace: str = "."
    proxy: SecretStr = SecretStr("")
    retries: int = Field(default=5, ge=0, le=100)
    sqlcipher_key: SecretStr = SecretStr("")


class ContextView(StrictModel):
    id: str
    region: Region
    platform: Platform
    workspace: str
    proxy_configured: bool
    retries: int
    sqlcipher_key_configured: bool
    resource_version: str | None
    created_at: str
    last_used_at: str


class ContextListResponse(StrictModel):
    items: list[ContextView]
    capacity: int = 16


class AssetCommandRequest(StrictModel):
    context_id: str
    concurrency: int = Field(default=30, ge=1, le=512)
    resources: list[Literal["table", "media", "bundle"]] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)


class AssetsSyncRequest(AssetCommandRequest):
    operation: Literal["assets.sync"]


class AssetsDownloadRequest(AssetCommandRequest):
    operation: Literal["assets.download"]


class AssetsExtractRequest(AssetCommandRequest):
    operation: Literal["assets.extract"]


class IndexBuildRequest(AssetCommandRequest):
    operation: Literal["index.build"]


class StorageCleanupRequest(StrictModel):
    operation: Literal["storage.cleanup"]
    context_id: str
    preview_token: str = Field(min_length=1)


JobCreateRequest = Annotated[
    AssetsSyncRequest
    | AssetsDownloadRequest
    | AssetsExtractRequest
    | IndexBuildRequest
    | StorageCleanupRequest,
    Field(discriminator="operation"),
]


class CleanupPreviewRequest(StrictModel):
    categories: list[
        Literal[
            "raw",
            "extracted",
            "indexes",
            "cache",
            "temp",
            "old-snapshots",
            "failed-staging",
            "logs",
        ]
    ] = Field(min_length=1)


class CharacterIndexSearchRequest(StrictModel):
    terms: list[str] = Field(min_length=1)


class OperationPreviewRequest(StrictModel):
    concurrency: int = Field(default=30, ge=1, le=512)
    resources: list[Literal["table", "media", "bundle"]] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)


class ProblemValidationIssue(StrictModel):
    type: str
    loc: list[str]
    msg: str


class ProblemDetails(StrictModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    errors: list[ProblemValidationIssue] | None = None


class DiscoveryResponse(StrictModel):
    protocol: str
    api_version: str
    application_version: str
    instance_id: str
    port: int
    ready: bool


class HealthResponse(StrictModel):
    status: str


class SystemInfoResponse(StrictModel):
    application_version: str
    api_version: str
    instance_id: str
    python_version: str
    port: int
    context_count: int
    job_count: int
    busy: bool
    dotnet: str | None
    ffmpeg: str | None


class RegionCapabilitiesResponse(StrictModel):
    region: Region
    platform_specific_directories: bool
    accepts_sqlcipher_key: bool
    supports_sync: bool
    supports_advanced_search: bool
    supports_character_index_build: bool


class ShutdownResponse(StrictModel):
    status: str


class WorkerErrorResponse(StrictModel):
    code: str
    exception_type: str
    message: str


class JobResponse(StrictModel):
    id: str
    context_id: str
    operation: str
    status: Literal[
        "queued", "running", "cancelling", "cancelled", "succeeded", "failed"
    ]
    created_at: str
    started_at: str | None
    finished_at: str | None
    progress: dict[str, Any] | None
    error: WorkerErrorResponse | None
    statistics: dict[str, int]
    warnings: list[str]
    effective_context: ContextView | None = None


class CatalogSummaryResponse(StrictModel):
    resource_version: str
    items: int
    bytes: int


class ChecksumResponse(StrictModel):
    algorithm: str
    value: str


class AssetResponse(StrictModel):
    id: int
    path: str
    url: str
    size: int
    type: str
    checksum: ChecksumResponse
    metadata: dict[str, Any]


class AssetListResponse(StrictModel):
    items: list[AssetResponse]
    next_cursor: str | None


class OperationPreviewResponse(StrictModel):
    items: int
    bytes: int
    advanced_search_deferred: bool


class CharacterIndexEntryResponse(StrictModel):
    character_id: int
    dev_name: str = ""
    names: list[str] | None = None
    file_aliases: set[str] | None = None
    cv: str = ""
    age: int = 0
    height: int = 0
    birthday: str = ""
    illustrator: str = ""
    school_en: str = ""
    club_en: str = ""


class CharacterIndexSummaryResponse(StrictModel):
    version: str
    entry_count: int


class CharacterIndexEntriesResponse(StrictModel):
    items: list[CharacterIndexEntryResponse]
    next_cursor: str | None


class CharacterIndexSearchResponse(StrictModel):
    asset_keywords: list[str]


class StorageScopeUsageResponse(StrictModel):
    path: str
    bytes: int


class StorageUsageResponse(RootModel[dict[str, StorageScopeUsageResponse]]):
    pass


class FileEntryResponse(StrictModel):
    id: str
    scope: str
    relative_path: str
    name: str
    is_directory: bool
    size: int
    modified_at: str


class FileListResponse(StrictModel):
    items: list[FileEntryResponse]
    next_cursor: str | None


class CleanupPreviewResponse(StrictModel):
    token: str
    expires_at: str
    file_count: int
    bytes: int


def context_view(item: ApiContext) -> dict[str, object]:
    context = item.context
    return {
        "id": item.id,
        "region": context.region,
        "platform": context.platform,
        "workspace": str(context.workspace.root),
        "proxy_configured": bool(context.proxy_url),
        "retries": context.max_retries,
        "sqlcipher_key_configured": bool(context.sqlcipher_key),
        "resource_version": context.resource_version,
        "created_at": item.created_at.isoformat(),
        "last_used_at": item.last_used_at.isoformat(),
    }


def effective_context_view(
    context: ExecutionContext, context_id: str
) -> dict[str, object]:
    now = "1970-01-01T00:00:00+00:00"
    return context_view(ApiContext(context_id, context, _epoch(), _epoch(), "")) | {
        "created_at": now,
        "last_used_at": now,
    }


def _epoch() -> Any:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(0, UTC)
