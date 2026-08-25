from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHttpException

from ba_downloader.api.files import FileRegistry
from ba_downloader.api.jobs import JobManager
from ba_downloader.api.models import ProblemDetails
from ba_downloader.api.problems import ApiProblem, problem_response
from ba_downloader.api.routers import (
    catalog,
    character_index,
    contexts,
    jobs,
    storage,
    system,
)
from ba_downloader.api.services import ApiServices
from ba_downloader.api.state import ContextRegistry

API_VERSION = "v1"
LOGGER = logging.getLogger(__name__)


def create_app(
    *,
    port: int,
    shutdown_callback: Callable[[], None] | None = None,
    job_manager: JobManager | None = None,
    catalog_loader: Callable[[Any], tuple[Any, Any]] | None = None,
    character_index_loader: Callable[[Any], Any] | None = None,
    character_index_searcher: Callable[[Any, list[str]], list[str]] | None = None,
) -> FastAPI:
    context_registry = ContextRegistry()

    def record_result(job: Any, context: Any, catalog: Any) -> None:
        context_registry.freeze(job.context_id, context, catalog)

    jobs_service = job_manager or JobManager(result_callback=record_result)
    services = ApiServices(
        contexts=context_registry,
        jobs=jobs_service,
        files=FileRegistry(),
        instance_id=uuid4().hex,
        port=port,
        shutdown_callback=shutdown_callback,
        catalog_loader=catalog_loader,
        character_index_loader=character_index_loader,
        character_index_searcher=character_index_searcher,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        services.jobs.start()
        try:
            yield
        finally:
            services.jobs.stop()

    app = FastAPI(
        title="Blue Archive Asset Downloader Local API",
        version=API_VERSION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def reject_work_during_shutdown(request: Request, call_next: Any) -> Any:
        if (
            services.shutdown_event.is_set()
            and request.url.path != "/api/v1/system/shutdown"
        ):
            return problem_response(
                request,
                503,
                "SERVER_SHUTTING_DOWN",
                "Server is shutting down",
                "The server is not accepting new work.",
            )
        return await call_next(request)

    @app.exception_handler(ApiProblem)
    async def handle_problem(request: Request, exc: ApiProblem) -> JSONResponse:
        return problem_response(request, exc.status, exc.code, exc.title, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "type": str(error.get("type", "value_error")),
                "loc": [str(part) for part in error.get("loc", ())],
                "msg": str(error.get("msg", "Invalid value")),
            }
            for error in exc.errors()
        ]
        return problem_response(
            request,
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            "One or more request fields are invalid.",
            errors=errors,
        )

    @app.exception_handler(StarletteHttpException)
    async def handle_http_error(
        request: Request, exc: StarletteHttpException
    ) -> JSONResponse:
        return problem_response(
            request,
            exc.status_code,
            "HTTP_ERROR",
            "HTTP request failed",
            str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        LOGGER.exception("Unhandled HTTP API request error", exc_info=exc)
        return problem_response(
            request,
            500,
            "INTERNAL_ERROR",
            "Internal server error",
            "An unexpected server error occurred. Check the server logs for details.",
        )

    responses = {
        400: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
        429: {"model": ProblemDetails},
        500: {"model": ProblemDetails},
    }
    for router_factory in (
        system.create_router,
        contexts.create_router,
        jobs.create_router,
        catalog.create_router,
        character_index.create_router,
        storage.create_router,
    ):
        app.include_router(router_factory(services), responses=cast(Any, responses))
    return app
