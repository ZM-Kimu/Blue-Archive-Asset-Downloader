from __future__ import annotations

import shutil
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import cast

from fastapi import APIRouter

from ba_downloader.api.models import (
    DiscoveryResponse,
    HealthResponse,
    RegionCapabilitiesResponse,
    ShutdownResponse,
    SystemInfoResponse,
)
from ba_downloader.api.problems import ApiProblem
from ba_downloader.api.services import ApiServices
from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
)
from ba_downloader.domain.models.region import Region

API_VERSION = "v1"
PROTOCOL_ID = "baad-local-api"


def create_router(services: ApiServices) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get(
        "/discovery", operation_id="discoverLocalApi", response_model=DiscoveryResponse
    )
    def discovery() -> dict[str, object]:
        return {
            "protocol": PROTOCOL_ID,
            "api_version": API_VERSION,
            "application_version": application_version(),
            "instance_id": services.instance_id,
            "port": services.port,
            "ready": True,
        }

    @router.get("/health", operation_id="getHealth", response_model=HealthResponse)
    def health() -> dict[str, object]:
        return {"status": "ok"}

    @router.get(
        "/system", operation_id="getSystemInfo", response_model=SystemInfoResponse
    )
    def system_info() -> dict[str, object]:
        return {
            "application_version": application_version(),
            "api_version": API_VERSION,
            "instance_id": services.instance_id,
            "python_version": sys.version.split()[0],
            "port": services.port,
            "context_count": len(services.contexts.list()),
            "job_count": len(services.jobs.list_jobs()),
            "busy": services.jobs.is_busy(),
            "dotnet": shutil.which("dotnet"),
            "ffmpeg": shutil.which("ffmpeg"),
        }

    @router.post(
        "/system/shutdown",
        operation_id="shutdownServer",
        response_model=ShutdownResponse,
    )
    def shutdown() -> dict[str, object]:
        services.shutdown_event.set()
        if services.shutdown_callback is not None:
            services.shutdown_callback()
        return {"status": "shutting-down"}

    @router.get(
        "/regions",
        operation_id="listRegions",
        response_model=list[RegionCapabilitiesResponse],
    )
    def regions() -> list[dict[str, object]]:
        return [region_capabilities(region) for region in ("cn", "gl", "jp")]

    @router.get(
        "/regions/{region}/capabilities",
        operation_id="getRegionCapabilities",
        response_model=RegionCapabilitiesResponse,
    )
    def region_capabilities(region: str) -> dict[str, object]:
        normalized = region.lower()
        try:
            definition = DEFAULT_REGION_GATEWAY_REGISTRY.resolve(
                cast(Region, normalized)
            )
        except LookupError as exc:
            raise ApiProblem(
                404, "REGION_NOT_FOUND", "Region not found", str(exc)
            ) from exc
        descriptor = definition.descriptor
        capabilities = descriptor.capabilities
        return {
            "region": normalized,
            "platform_specific_directories": (
                descriptor.settings_policy.include_platform_in_default_dirs
            ),
            "accepts_sqlcipher_key": (
                descriptor.settings_policy.retain_sqlcipher_key_hex
            ),
            "supports_sync": capabilities.supports_sync,
            "supports_advanced_search": capabilities.supports_advanced_search,
            "supports_character_index_build": (
                capabilities.supports_character_index_build
            ),
        }

    return router


def application_version() -> str:
    try:
        return version("ba-downloader")
    except PackageNotFoundError:
        return "0.0.0"
