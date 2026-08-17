from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ba_downloader.api.models import (
    ContextCreateRequest,
    ContextListResponse,
    ContextView,
)
from ba_downloader.api.problems import ApiProblem, require_context
from ba_downloader.api.services import ApiServices
from ba_downloader.api.state import ContextCapacityError, ContextInUseError


def create_router(services: ApiServices) -> APIRouter:
    router = APIRouter(prefix="/api/v1/contexts")

    @router.post("", operation_id="createContext", response_model=ContextView)
    def create_context(body: ContextCreateRequest) -> JSONResponse:
        try:
            item, created = services.contexts.create(
                services.context_from_request(body)
            )
        except ContextCapacityError as exc:
            raise ApiProblem(
                429, "CONTEXT_LIMIT", "Context limit reached", str(exc)
            ) from exc
        return JSONResponse(
            services.context_view(item), status_code=201 if created else 200
        )

    @router.get("", operation_id="listContexts", response_model=ContextListResponse)
    def list_contexts() -> dict[str, object]:
        return {
            "items": [services.context_view(item) for item in services.contexts.list()]
        }

    @router.get("/{context_id}", operation_id="getContext", response_model=ContextView)
    def get_context(context_id: str) -> dict[str, object]:
        return services.context_view(require_context(services, context_id))

    @router.delete("/{context_id}", operation_id="deleteContext", status_code=204)
    def delete_context(context_id: str) -> None:
        require_context(services, context_id)
        try:
            services.contexts.delete(
                context_id, in_use=services.jobs.references_context(context_id)
            )
        except ContextInUseError as exc:
            raise ApiProblem(
                409, "CONTEXT_IN_USE", "Context is in use", str(exc)
            ) from exc

    @router.post(
        "/{context_id}/refresh",
        operation_id="refreshContext",
        response_model=ContextView,
    )
    def refresh_context(context_id: str) -> JSONResponse:
        require_context(services, context_id)
        try:
            refreshed = services.contexts.refresh(context_id)
        except ContextCapacityError as exc:
            raise ApiProblem(
                429, "CONTEXT_LIMIT", "Context limit reached", str(exc)
            ) from exc
        return JSONResponse(services.context_view(refreshed), status_code=201)

    return router
