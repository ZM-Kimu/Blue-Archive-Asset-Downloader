from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient, Response

pytest.importorskip("fastapi", reason="API optional dependency is not installed")

from ba_downloader.api.app import create_app
from ba_downloader.api.jobs import JobManager
from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetRecord,
    AssetType,
    ChecksumSpec,
)
from ba_downloader.domain.models.character import CharacterIndex, CharacterIndexEntry
from ba_downloader.domain.models.execution import ExecutionContext


def test_preview_reports_direct_member_selection_without_support_archives(
    tmp_path: Path,
) -> None:
    catalog = AssetCollection(
        [
            AssetRecord(
                "https://cdn.example/FullPatch_044.zip",
                "Bundle/FullPatch_044.zip",
                329_304_643,
                ChecksumSpec("crc", "0"),
                AssetType.bundle,
                member_paths=(
                    "characters/ibuki.bundle",
                    "characters/other.bundle",
                ),
            )
        ]
    )

    def load_catalog(
        context: ExecutionContext,
    ) -> tuple[ExecutionContext, AssetCollection]:
        return context.resolve_resource_version("test"), catalog

    app = create_app(
        port=0,
        job_manager=JobManager(process_target=lambda *args: None),
        catalog_loader=load_catalog,
        character_index_loader=lambda context: CharacterIndex(
            context.require_resource_version(),
            [CharacterIndexEntry(335, dev_name="Ibuki", names=["Ibuki"])],
        ),
    )

    async def send_requests() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test.local",
        ) as client:
            created = await client.post(
                "/api/v1/contexts",
                json={
                    "region": "jp",
                    "platform": "android",
                    "workspace": str(tmp_path),
                },
            )
            assert created.status_code == 201
            context_id = created.json()["id"]
            return await client.post(
                f"/api/v1/contexts/{context_id}/operations/preview",
                json={
                    "operation": "assets.extract",
                    "resources": ["bundle"],
                    "filters": ["name=ibuki"],
                    "bundle_handler": "assetripper",
                },
            )

    response = asyncio.run(send_requests())

    assert response.status_code == 200
    estimate = response.json()["estimate"]
    assert estimate == {
        "total": {"items": 1, "bytes": 329_304_643},
        "direct": {"items": 1, "bytes": 329_304_643},
        "missing_direct": {"items": 1, "bytes": 329_304_643},
        "target_members": 1,
        "ready": False,
    }
    assert "support" not in estimate
    assert "missing_support" not in estimate
