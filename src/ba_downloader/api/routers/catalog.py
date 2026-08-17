from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ba_downloader.api.models import (
    AssetListResponse,
    AssetResponse,
    CatalogSummaryResponse,
    OperationPreviewRequest,
    OperationPreviewResponse,
)
from ba_downloader.api.problems import (
    ApiProblem,
    require_catalog,
    require_context,
)
from ba_downloader.api.services import ApiServices
from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.asset import AssetRecord
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.services.asset_filter import (
    RESOURCE_FIELDS,
    AssetFilterService,
)
from ba_downloader.domain.services.resource_query import ResourceQueryService


def create_router(services: ApiServices) -> APIRouter:
    router = APIRouter(prefix="/api/v1/contexts/{context_id}")

    @router.get(
        "/catalog", operation_id="getCatalog", response_model=CatalogSummaryResponse
    )
    def get_catalog(context_id: str) -> dict[str, object]:
        catalog = require_catalog(services, context_id)
        item = require_context(services, context_id)
        return {
            "resource_version": item.context.version,
            "items": len(catalog),
            "bytes": sum(max(asset.size, 0) for asset in catalog),
        }

    @router.get(
        "/catalog/assets",
        operation_id="listCatalogAssets",
        response_model=AssetListResponse,
    )
    def list_catalog_assets(
        context_id: str,
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
        query: str = "",
    ) -> dict[str, object]:
        catalog = require_catalog(services, context_id)
        assets = [
            (asset_id, asset)
            for asset_id, asset in enumerate(catalog)
            if query.casefold() in asset.path.casefold()
        ]
        return {
            "items": [
                asset_view(asset_id, asset)
                for asset_id, asset in assets[cursor : cursor + limit]
            ],
            "next_cursor": str(cursor + limit)
            if cursor + limit < len(assets)
            else None,
        }

    @router.get(
        "/catalog/assets/{asset_id}",
        operation_id="getCatalogAsset",
        response_model=AssetResponse,
    )
    def get_catalog_asset(context_id: str, asset_id: int) -> dict[str, object]:
        catalog = require_catalog(services, context_id)
        try:
            asset = catalog[asset_id]
        except IndexError as exc:
            raise ApiProblem(
                404, "ASSET_NOT_FOUND", "Asset not found", str(asset_id)
            ) from exc
        assert isinstance(asset, AssetRecord)
        return asset_view(asset_id, asset)

    @router.post(
        "/operations/preview",
        operation_id="previewOperation",
        response_model=OperationPreviewResponse,
    )
    def preview_operation(
        context_id: str, body: OperationPreviewRequest
    ) -> dict[str, object]:
        require_context(services, context_id)
        resources = require_catalog(services, context_id)
        filtered = ResourceQueryService.filter_type(
            resources, tuple(body.resources) or ("table", "media", "bundle")
        )
        try:
            asset_filter = AssetFilter.parse(body.filters)
            entries = None
            if any(
                predicate.field not in RESOURCE_FIELDS
                for predicate in asset_filter.predicates
            ):
                entries = services.load_character_index(context_id).entries
            filtered = AssetFilterService.apply(
                filtered, asset_filter, character_entries=entries
            )
        except ConfigError as exc:
            raise ApiProblem(
                422, "FILTER_INVALID", "Asset filter is invalid", str(exc)
            ) from exc
        except (FileNotFoundError, OSError, ValueError) as exc:
            raise ApiProblem(
                409, "CHARACTER_INDEX_REQUIRED", "Character index is required", str(exc)
            ) from exc
        return {
            "items": len(filtered),
            "bytes": sum(max(asset.size, 0) for asset in filtered),
            "advanced_search_deferred": bool(body.filters),
        }

    return router


def asset_view(asset_id: int, asset: AssetRecord) -> dict[str, object]:
    return {
        "id": asset_id,
        "path": asset.path,
        "url": asset.url,
        "size": asset.size,
        "type": asset.asset_type.value,
        "checksum": {
            "algorithm": asset.checksum.algorithm,
            "value": asset.checksum.value,
        },
        "metadata": json_safe(asset.metadata),
    }


def json_safe(value: object) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"byte_count": len(value)}
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return str(value)
