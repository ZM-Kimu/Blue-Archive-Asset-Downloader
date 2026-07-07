from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ba_downloader.application.profiles import (
    NoopCatalogMetadataPolicy,
    RegionProfile,
    build_region_profile,
)
from ba_downloader.domain.models.region import Region
from ba_downloader.domain.models.region_profile import (
    RegionSettingsPolicy,
    RegionWorkflowPolicy,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.catalog_metadata import (
    CatalogMetadataPolicy,
    TableMetadataManifestPort,
)
from ba_downloader.domain.ports.extract import (
    ExtractionPrerequisitePort,
    Il2CppDumpBackendPort,
    SchemaPreparationPort,
)
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort
from ba_downloader.infrastructure.extraction.character.index_composer import (
    CharacterIndexCompositionProfile,
)
from ba_downloader.infrastructure.extraction.character.index_sources import (
    CharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)

ProviderFactory = Callable[[HttpClientPort, LoggerPort], RegionProvider]
RuntimeAssetPreparerFactory = Callable[
    [HttpClientPort, LoggerPort],
    RuntimeAssetPreparerPort,
]
DumperBackendFactory = Callable[
    [HttpClientPort, LoggerPort],
    Il2CppDumpBackendPort,
]
TableProfileFactory = Callable[[RuntimeContext], TableExtractionProfile]
CharacterIndexSourceProfileFactory = Callable[
    [RuntimeContext],
    CharacterIndexSourceProfile,
]
CharacterIndexCompositionProfileFactory = Callable[
    [RuntimeContext],
    CharacterIndexCompositionProfile,
]
ExtractionPrerequisiteFactory = Callable[
    [SchemaPreparationPort, LoggerPort],
    ExtractionPrerequisitePort | None,
]
CatalogMetadataPolicyFactory = Callable[
    [RegionProvider, LoggerPort, TableMetadataManifestPort],
    CatalogMetadataPolicy,
]
RegionServiceProfileFactory = Callable[[], "RegionServiceProfile"]


def _no_extraction_prerequisite(
    schema_preparation: SchemaPreparationPort,
    logger: LoggerPort,
) -> None:
    _ = (schema_preparation, logger)
    return None


def _noop_catalog_metadata_policy(
    provider: RegionProvider,
    logger: LoggerPort,
    table_metadata_store: TableMetadataManifestPort,
) -> CatalogMetadataPolicy:
    _ = (provider, logger, table_metadata_store)
    return NoopCatalogMetadataPolicy()


@dataclass(frozen=True, slots=True)
class RegionServiceProfile:
    region: Region
    workflow_policy: RegionWorkflowPolicy
    settings_policy: RegionSettingsPolicy
    provider_factory: ProviderFactory
    runtime_asset_preparer_factory: RuntimeAssetPreparerFactory
    dumper_backend_factory: DumperBackendFactory
    table_profile_factory: TableProfileFactory
    character_index_source_profile_factory: CharacterIndexSourceProfileFactory
    character_index_composition_profile_factory: CharacterIndexCompositionProfileFactory
    extraction_prerequisite_factory: ExtractionPrerequisiteFactory = (
        _no_extraction_prerequisite
    )
    catalog_metadata_policy_factory: CatalogMetadataPolicyFactory = (
        _noop_catalog_metadata_policy
    )


class RegionServiceProfileRegistry:
    def __init__(self) -> None:
        self._profiles: dict[Region, RegionServiceProfile] = {}
        self._factories: dict[Region, RegionServiceProfileFactory] = {}

    def register(self, profile: RegionServiceProfile) -> None:
        self._profiles[profile.region] = profile

    def register_factory(
        self,
        region: Region,
        factory: RegionServiceProfileFactory,
    ) -> None:
        self._factories[region] = factory

    def resolve(self, region: Region) -> RegionServiceProfile:
        if region in self._profiles:
            return self._profiles[region]
        if region in self._factories:
            profile = self._factories[region]()
            self.register(profile)
            return profile
        else:
            raise KeyError(f"Region '{region}' is not registered.")


def build_application_region_profile(
    service_profile: RegionServiceProfile,
    context: RuntimeContext,
    *,
    http_client: HttpClientPort,
    logger: LoggerPort,
    table_metadata_store: TableMetadataManifestPort,
    provider: RegionProvider | None = None,
) -> RegionProfile:
    _ = context
    active_provider = provider or service_profile.provider_factory(http_client, logger)
    return build_region_profile(
        service_profile.workflow_policy,
        service_profile.settings_policy,
        service_profile.catalog_metadata_policy_factory(
            active_provider,
            logger,
            table_metadata_store,
        ),
    )


def _build_cn_service_profile() -> RegionServiceProfile:
    from ba_downloader.infrastructure.regions.cn import profile as cn_profile

    return RegionServiceProfile(
        region="cn",
        workflow_policy=cn_profile.CN_WORKFLOW_POLICY,
        settings_policy=cn_profile.CN_SETTINGS_POLICY,
        provider_factory=cn_profile.build_provider,
        runtime_asset_preparer_factory=cn_profile.build_runtime_asset_preparer,
        dumper_backend_factory=cn_profile.build_dumper_backend,
        table_profile_factory=cn_profile.build_table_extraction_profile,
        character_index_source_profile_factory=cn_profile.build_character_index_source_profile,
        character_index_composition_profile_factory=(
            cn_profile.build_character_index_composition_profile
        ),
    )


def _build_gl_service_profile() -> RegionServiceProfile:
    from ba_downloader.infrastructure.regions.gl import profile as gl_profile

    return RegionServiceProfile(
        region="gl",
        workflow_policy=gl_profile.GL_WORKFLOW_POLICY,
        settings_policy=gl_profile.GL_SETTINGS_POLICY,
        provider_factory=gl_profile.build_provider,
        runtime_asset_preparer_factory=gl_profile.build_runtime_asset_preparer,
        dumper_backend_factory=gl_profile.build_dumper_backend,
        table_profile_factory=gl_profile.build_table_extraction_profile,
        character_index_source_profile_factory=gl_profile.build_character_index_source_profile,
        character_index_composition_profile_factory=(
            gl_profile.build_character_index_composition_profile
        ),
    )


def _build_jp_service_profile() -> RegionServiceProfile:
    from ba_downloader.infrastructure.regions.jp import profile as jp_profile

    return RegionServiceProfile(
        region="jp",
        workflow_policy=jp_profile.JP_WORKFLOW_POLICY,
        settings_policy=jp_profile.JP_SETTINGS_POLICY,
        provider_factory=jp_profile.build_provider,
        runtime_asset_preparer_factory=jp_profile.build_runtime_asset_preparer,
        dumper_backend_factory=jp_profile.build_dumper_backend,
        table_profile_factory=jp_profile.build_table_extraction_profile,
        character_index_source_profile_factory=jp_profile.build_character_index_source_profile,
        character_index_composition_profile_factory=jp_profile.build_character_index_composition_profile,
        extraction_prerequisite_factory=jp_profile.build_extraction_prerequisite,
        catalog_metadata_policy_factory=jp_profile.build_catalog_metadata_policy,
    )


def build_default_region_service_profile_registry() -> RegionServiceProfileRegistry:
    registry = RegionServiceProfileRegistry()
    registry.register_factory("cn", _build_cn_service_profile)
    registry.register_factory("gl", _build_gl_service_profile)
    registry.register_factory("jp", _build_jp_service_profile)
    return registry


DEFAULT_REGION_SERVICE_PROFILE_REGISTRY = (
    build_default_region_service_profile_registry()
)
