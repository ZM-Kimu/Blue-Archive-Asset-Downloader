from __future__ import annotations

from pathlib import Path

from ba_downloader.application.use_cases.download_assets import DownloadAssetsUseCase
from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
    build_application_region_profile,
)
from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.runtime import RuntimeContext
from support import RecordingLogger, StaticProvider, build_runtime_context


class RecordingDownloader:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def verify_and_download(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> None:
        _ = context
        self.calls.append([item.path for item in resources])


class RecordingTableMetadataStore:
    def __init__(self) -> None:
        self.write_calls: list[tuple[RuntimeContext, AssetCollection]] = []

    def load(self, context: RuntimeContext) -> AssetCollection | None:
        _ = context
        return None

    def write(self, context: RuntimeContext, resources: AssetCollection) -> None:
        self.write_calls.append((context, resources))


def _build_table_catalog(context: RuntimeContext) -> RegionCatalogResult:
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/Table/TablePatchPack_GroundStage_1.zip",
        "Table/TablePatchPack_GroundStage_1.zip",
        10,
        "deadbeef",
        "crc",
        AssetType.table,
        {"includes": ["EN0010_VeryHard.zip"]},
    )
    return RegionCatalogResult(resources=resources, context=context)


def test_download_writes_catalog_table_metadata_manifest(tmp_path: Path) -> None:
    context = build_runtime_context(
        tmp_path,
        region="jp",
        resource_type=("table",),
    )
    provider = StaticProvider(_build_table_catalog(context))
    downloader = RecordingDownloader()
    metadata_store = RecordingTableMetadataStore()
    service = DownloadAssetsUseCase(
        provider,
        downloader,
        workflow_profile=build_application_region_profile(
            DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve("jp"),
            context,
            http_client=object(),
            logger=RecordingLogger(),
            table_metadata_store=metadata_store,
            provider=provider,
        ),
    )

    service.run(context)

    assert metadata_store.write_calls == [(context, provider.result.resources)]
    assert downloader.calls == [["Table/TablePatchPack_GroundStage_1.zip"]]
