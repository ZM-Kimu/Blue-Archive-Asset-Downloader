from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from ba_downloader.api.files import FileBoundaryError
from ba_downloader.api.jobs import (
    BundleJobConflictError,
    JobQueueFullError,
    JobStateError,
)
from ba_downloader.api.models import (
    JobCreateRequest,
    JobResponse,
    StorageCleanupRequest,
)
from ba_downloader.api.problems import ApiProblem, get_job, require_context
from ba_downloader.api.services import ApiServices
from ba_downloader.api.streams import job_event_stream
from ba_downloader.application.contracts import (
    ApplicationCommand,
    AssetOperationOptions,
    AssetsDownloadCommand,
    AssetsExtractCommand,
    AssetsSyncCommand,
    BuildCharacterIndexCommand,
    StorageCleanupCommand,
)
from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.asset_type_selection import ResourceTypeSelection

COMMAND_TYPES = {
    "assets.sync": AssetsSyncCommand,
    "assets.download": AssetsDownloadCommand,
    "assets.extract": AssetsExtractCommand,
}


def create_router(services: ApiServices) -> APIRouter:
    router = APIRouter(prefix="/api/v1/jobs")

    @router.post("", operation_id="createJob", response_model=JobResponse)
    def create_job(body: JobCreateRequest) -> JSONResponse:
        item = require_context(services, body.context_id)
        context = item.context
        command: ApplicationCommand
        if isinstance(body, StorageCleanupRequest):
            try:
                preview = services.files.consume_preview(
                    body.preview_token, body.context_id
                )
            except (KeyError, FileBoundaryError) as exc:
                raise ApiProblem(
                    409,
                    "CLEANUP_PREVIEW_INVALID",
                    "Cleanup preview is invalid",
                    str(exc),
                ) from exc
            command = StorageCleanupCommand(preview.targets)
        else:
            try:
                asset_filter = AssetFilter.parse(body.filters)
            except ConfigError as exc:
                raise ApiProblem(
                    422, "FILTER_INVALID", "Asset filter is invalid", str(exc)
                ) from exc
            options = AssetOperationOptions(
                concurrency=body.concurrency,
                resources=ResourceTypeSelection.from_values(body.resources),
                asset_filter=asset_filter,
            )
            if body.operation == "index.build":
                command = BuildCharacterIndexCommand(body.concurrency)
            elif body.operation == "assets.sync":
                command = AssetsSyncCommand(options)
            elif body.operation == "assets.download":
                command = AssetsDownloadCommand(options)
            else:
                command = AssetsExtractCommand(options)
        try:
            job = services.jobs.submit(command, context, body.context_id)
        except JobQueueFullError as exc:
            raise ApiProblem(429, "QUEUE_FULL", "Job queue is full", str(exc)) from exc
        except BundleJobConflictError as exc:
            raise ApiProblem(
                409,
                "BUNDLE_EXTRACTION_CONFLICT",
                "Bundle extraction is already active",
                str(exc),
            ) from exc
        except JobStateError as exc:
            raise ApiProblem(
                503, "SERVER_SHUTTING_DOWN", "Server is shutting down", str(exc)
            ) from exc
        return JSONResponse(services.job_view(job), status_code=202)

    @router.get("", operation_id="listJobs", response_model=list[JobResponse])
    def list_jobs() -> list[dict[str, object]]:
        return [services.job_view(job) for job in services.jobs.list_jobs()]

    @router.get("/{job_id}", operation_id="getJob", response_model=JobResponse)
    def get_job_view(job_id: str) -> dict[str, object]:
        return services.job_view(get_job(services.jobs, job_id))

    @router.post(
        "/{job_id}/cancel", operation_id="cancelJob", response_model=JobResponse
    )
    def cancel_job(job_id: str) -> dict[str, object]:
        try:
            return services.job_view(services.jobs.cancel(job_id))
        except KeyError as exc:
            raise ApiProblem(404, "JOB_NOT_FOUND", "Job not found", str(exc)) from exc
        except JobStateError as exc:
            raise ApiProblem(
                409, "JOB_STATE_INVALID", "Invalid job state", str(exc)
            ) from exc

    @router.get("/{job_id}/events", operation_id="streamJobEvents")
    async def stream_job_events(job_id: str) -> StreamingResponse:
        get_job(services.jobs, job_id)
        return StreamingResponse(
            job_event_stream(services, job_id), media_type="text/event-stream"
        )

    return router
