from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from ba_downloader.api.files import CleanupPreviewLimitError, FileBoundaryError
from ba_downloader.api.models import (
    CleanupPreviewRequest,
    CleanupPreviewResponse,
    FileEntryResponse,
    FileListResponse,
    StorageUsageResponse,
)
from ba_downloader.api.problems import ApiProblem, require_context
from ba_downloader.api.services import ApiServices


def create_router(services: ApiServices) -> APIRouter:
    router = APIRouter(prefix="/api/v1/contexts/{context_id}")

    @router.get(
        "/storage/usage",
        operation_id="getStorageUsage",
        response_model=StorageUsageResponse,
    )
    def get_storage_usage(context_id: str) -> dict[str, object]:
        return services.files.usage(require_context(services, context_id).context)

    @router.get("/files", operation_id="listFiles", response_model=FileListResponse)
    def list_files(
        context_id: str,
        scope: str,
        path: str = "",
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, object]:
        context = require_context(services, context_id).context
        try:
            entries = services.files.list_entries(context, scope, path)
        except (FileBoundaryError, OSError) as exc:
            raise ApiProblem(
                400, "FILE_PATH_INVALID", "Invalid file path", str(exc)
            ) from exc
        return {
            "items": [entry.as_dict() for entry in entries[cursor : cursor + limit]],
            "next_cursor": str(cursor + limit)
            if cursor + limit < len(entries)
            else None,
        }

    @router.get(
        "/files/{file_id}", operation_id="getFile", response_model=FileEntryResponse
    )
    def get_file(context_id: str, file_id: str) -> dict[str, object]:
        context = require_context(services, context_id).context
        try:
            return services.files.metadata(file_id, context).as_dict()
        except (KeyError, FileNotFoundError) as exc:
            raise ApiProblem(404, "FILE_NOT_FOUND", "File not found", str(exc)) from exc

    @router.get("/files/{file_id}/content", operation_id="downloadFile")
    def download_file(context_id: str, file_id: str) -> FileResponse:
        context = require_context(services, context_id).context
        try:
            path = services.files.resolve(file_id, context)
        except (KeyError, FileNotFoundError) as exc:
            raise ApiProblem(404, "FILE_NOT_FOUND", "File not found", str(exc)) from exc
        if not path.is_file():
            raise ApiProblem(400, "FILE_REQUIRED", "File required", str(path))
        return FileResponse(path)

    @router.post(
        "/storage/cleanup/preview",
        operation_id="previewStorageCleanup",
        response_model=CleanupPreviewResponse,
    )
    def preview_storage_cleanup(
        context_id: str, body: CleanupPreviewRequest
    ) -> dict[str, object]:
        context = require_context(services, context_id).context
        try:
            preview = services.files.preview_cleanup(
                context, context_id, body.categories
            )
        except CleanupPreviewLimitError as exc:
            raise ApiProblem(
                429, "CLEANUP_PREVIEW_LIMIT", "Cleanup preview limit reached", str(exc)
            ) from exc
        except (FileBoundaryError, OSError) as exc:
            raise ApiProblem(
                400, "CLEANUP_INVALID", "Cleanup is invalid", str(exc)
            ) from exc
        return {
            "token": preview.token,
            "expires_at": preview.expires_at.isoformat(),
            "file_count": len(preview.targets),
            "bytes": preview.total_bytes,
        }

    return router
