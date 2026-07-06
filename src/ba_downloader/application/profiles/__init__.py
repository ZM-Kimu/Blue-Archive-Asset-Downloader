from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.region_profile import (
    RegionSettingsPolicy,
    RegionWorkflowPolicy,
    SyncExtractionMode,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.catalog_metadata import CatalogMetadataPolicy


class NoopCatalogMetadataPolicy:
    def on_catalog_loaded(
        self,
        context: RuntimeContext,
        resources: AssetCollection,
    ) -> None:
        _ = context
        _ = resources

    def resolve_existing_table_resources(
        self,
        context: RuntimeContext,
    ) -> tuple[RuntimeContext, AssetCollection | None]:
        return context, None


@dataclass(frozen=True, slots=True)
class RegionProfile:
    prepares_schema_for_sync: bool
    sync_extraction_mode: SyncExtractionMode
    settings_policy: RegionSettingsPolicy
    catalog_metadata: CatalogMetadataPolicy
    table_extraction_prerequisite: bool = False


def build_region_profile(
    workflow_policy: RegionWorkflowPolicy,
    settings_policy: RegionSettingsPolicy,
    catalog_metadata: CatalogMetadataPolicy | None = None,
) -> RegionProfile:
    return RegionProfile(
        prepares_schema_for_sync=workflow_policy.prepares_schema_for_sync,
        sync_extraction_mode=workflow_policy.sync_extraction_mode,
        settings_policy=settings_policy,
        catalog_metadata=catalog_metadata or NoopCatalogMetadataPolicy(),
        table_extraction_prerequisite=workflow_policy.table_extraction_prerequisite,
    )


__all__ = [
    "CatalogMetadataPolicy",
    "NoopCatalogMetadataPolicy",
    "RegionProfile",
    "RegionSettingsPolicy",
    "SyncExtractionMode",
    "build_region_profile",
]
