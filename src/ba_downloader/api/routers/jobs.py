from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from ba_downloader.api.files import FileBoundaryError
from ba_downloader.api.jobs import JobQueueFullError, JobStateError
from ba_downloader.api.models import (
    JobCreateRequest,
    JobResponse,
    StorageCleanupRequest,
)
from ba_downloader.api.problems import ApiProblem, get_job, require_context
from ba_downloader.api.services import ApiServices
from ba_downloader.api.streams import job_event_stream
from ba_downloader.application.operations import (
    ApplicationOperation,
    ApplicationOperationCommand,
)
from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.asset_filter import AssetFilter

OPERATION_MAP = {
    "assets.sync": ApplicationOperation.sync,
    "assets.download": ApplicationOperation.download,
    "assets.extract": ApplicationOperation.extract,
    "index.build": ApplicationOperation.character_index,
}


def create_router(services: ApiServices) -> APIRouter:
    router = APIRouter(prefix="/api/v1/jobs")

    @router.post("", operation_id="createJob", response_model=JobResponse)
    def create_job(body: JobCreateRequest) -> JSONResponse:
        item = require_context(services, body.context_id)
        context = item.context
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
            command = ApplicationOperationCommand(
                ApplicationOperation.storage_cleanup, cleanup_targets=preview.targets
            )
        else:
            try:
                asset_filter = AssetFilter.parse(body.filters)
            except ConfigError as exc:
                raise ApiProblem(
                    422, "FILTER_INVALID", "Asset filter is invalid", str(exc)
                ) from exc
            context = context.with_updates(
                threads=body.concurrency,
                resource_type=tuple(body.resources) or ("table", "media", "bundle"),
                asset_filter=asset_filter,
            )
            command = ApplicationOperationCommand(OPERATION_MAP[body.operation])
        try:
            job = services.jobs.submit(command, context, body.context_id)
        except JobQueueFullError as exc:
            raise ApiProblem(429, "QUEUE_FULL", "Job queue is full", str(exc)) from exc
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
