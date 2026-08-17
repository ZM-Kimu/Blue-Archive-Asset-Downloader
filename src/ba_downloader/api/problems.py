from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from ba_downloader.api.jobs import JobManager, JobRecord
from ba_downloader.api.services import ApiServices
from ba_downloader.api.state import ApiContext
from ba_downloader.domain.models.asset import AssetCollection


class ApiProblem(Exception):
    def __init__(self, status: int, code: str, title: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail


def require_context(services: ApiServices, context_id: str) -> ApiContext:
    try:
        return services.contexts.get(context_id)
    except KeyError as exc:
        raise ApiProblem(
            404, "CONTEXT_NOT_FOUND", "Context not found", str(exc)
        ) from exc


def get_job(jobs: JobManager, job_id: str) -> JobRecord:
    try:
        return jobs.get(job_id)
    except KeyError as exc:
        raise ApiProblem(404, "JOB_NOT_FOUND", "Job not found", str(exc)) from exc


def require_catalog(services: ApiServices, context_id: str) -> AssetCollection:
    require_context(services, context_id)
    try:
        _, catalog = services.require_catalog(context_id)
    except RuntimeError as exc:
        raise ApiProblem(
            409,
            "CATALOG_REQUIRED",
            "Catalog is required",
            "Catalog loading is unavailable for this server.",
        ) from exc
    return catalog


def problem_response(
    request: Request,
    status: int,
    code: str,
    title: str,
    detail: str,
    *,
    errors: object | None = None,
) -> JSONResponse:
    payload: dict[str, object] = {
        "type": f"urn:baad:problem:{code.lower()}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": str(request.url.path),
        "code": code,
    }
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(
        payload, status_code=status, media_type="application/problem+json"
    )
