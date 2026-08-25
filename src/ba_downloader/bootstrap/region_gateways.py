from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ba_downloader.application.profiles import (
    NoopCatalogMetadataPolicy,
    RegionProfile,
    build_region_profile,
)
from ba_downloader.domain.models.asset import RegionCapabilities
from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region import Region
from ba_downloader.domain.models.region_profile import (
    RegionSettingsPolicy,
    RegionWorkflowPolicy,
)
from ba_downloader.domain.ports.catalog_metadata import (
    CatalogMetadataPolicy,
    TableMetadataManifestPort,
)
from ba_downloader.domain.ports.execution import CancellationPort
from ba_downloader.domain.ports.extract import (
    ExtractionPrerequisitePort,
    Il2CppDumpBackendPort,
    SchemaPreparationPort,
)
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import ProgressReporterFactoryPort
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

ProviderFactory = Callable[
    [
        HttpClientPort,
        LoggerPort,
        ProgressReporterFactoryPort | None,
        CancellationPort,
    ],
    RegionProvider,
]
RuntimeAssetPreparerFactory = Callable[
    [
        HttpClientPort,
        LoggerPort,
        ProgressReporterFactoryPort | None,
        CancellationPort,
    ],
    RuntimeAssetPreparerPort,
]
DumpBackendFactory = Callable[
    [
        HttpClientPort,
        LoggerPort,
        ProgressReporterFactoryPort | None,
        CancellationPort,
    ],
    Il2CppDumpBackendPort,
]
TableExtractionProfileFactory = Callable[
    [ExecutionContext, DatabaseSourceIdentity | None], TableExtractionProfile
]
ExtractionPrerequisiteFactory = Callable[
    [SchemaPreparationPort, LoggerPort],
    ExtractionPrerequisitePort | None,
]
CharacterIndexSourceFactory = Callable[
    [ExecutionContext],
    CharacterIndexSourceProfile,
]
CharacterIndexCompositionFactory = Callable[
    [ExecutionContext],
    CharacterIndexCompositionProfile,
]
CatalogMetadataPolicyFactory = Callable[
    [RegionProvider, LoggerPort, TableMetadataManifestPort],
    CatalogMetadataPolicy,
]


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
class RegionDescriptor:
    region: Region
    capabilities: RegionCapabilities
    workflow_policy: RegionWorkflowPolicy
    settings_policy: RegionSettingsPolicy


@dataclass(frozen=True, slots=True)
class CatalogGatewayFactories:
    provider: ProviderFactory


@dataclass(frozen=True, slots=True)
class RuntimeGatewayFactories:
    asset_preparer: RuntimeAssetPreparerFactory
    dump_backend: DumpBackendFactory


@dataclass(frozen=True, slots=True)
class TableGatewayFactories:
    extraction_profile: TableExtractionProfileFactory
    extraction_prerequisite: ExtractionPrerequisiteFactory = _no_extraction_prerequisite


@dataclass(frozen=True, slots=True)
class CharacterIndexGatewayFactories:
    source_profile: CharacterIndexSourceFactory
    composition_profile: CharacterIndexCompositionFactory


@dataclass(frozen=True, slots=True)
class CatalogMetadataGatewayFactories:
    policy: CatalogMetadataPolicyFactory = _noop_catalog_metadata_policy


@dataclass(frozen=True, slots=True)
class RegionGatewayDefinition:
    descriptor: RegionDescriptor
    catalog: CatalogGatewayFactories
    runtime: RuntimeGatewayFactories
    tables: TableGatewayFactories
    character_index: CharacterIndexGatewayFactories
    catalog_metadata: CatalogMetadataGatewayFactories = (
        CatalogMetadataGatewayFactories()
    )


RegionGatewayDefinitionFactory = Callable[[], RegionGatewayDefinition]


class RegionGatewayRegistry:
    def __init__(self) -> None:
        self._definitions: dict[Region, RegionGatewayDefinition] = {}
        self._factories: dict[Region, RegionGatewayDefinitionFactory] = {}

    def register_factory(
        self,
        region: Region,
        factory: RegionGatewayDefinitionFactory,
    ) -> None:
        self._factories[region] = factory

    def resolve(self, region: Region) -> RegionGatewayDefinition:
        definition = self._definitions.get(region)
        if definition is not None:
            return definition
        factory = self._factories.get(region)
        if factory is None:
            raise KeyError(f"Region '{region}' is not registered.")
        definition = factory()
        actual_region = definition.descriptor.region
        if actual_region != region:
            raise ValueError(
                f"Region gateway factory registered for '{region}' returned "
                f"'{actual_region}'."
            )
        self._definitions[region] = definition
        return definition


def _build_cn_gateway_definition() -> RegionGatewayDefinition:
    from ba_downloader.infrastructure.regions.cn import profile
    from ba_downloader.infrastructure.regions.cn.provider import CNRegionProvider

    return RegionGatewayDefinition(
        descriptor=RegionDescriptor(
            region="cn",
            capabilities=CNRegionProvider.CAPABILITIES,
            workflow_policy=profile.CN_WORKFLOW_POLICY,
            settings_policy=profile.CN_SETTINGS_POLICY,
        ),
        catalog=CatalogGatewayFactories(profile.build_provider),
        runtime=RuntimeGatewayFactories(
            profile.build_runtime_asset_preparer,
            profile.build_dumper_backend,
        ),
        tables=TableGatewayFactories(profile.build_table_extraction_profile),
        character_index=CharacterIndexGatewayFactories(
            profile.build_character_index_source_profile,
            profile.build_character_index_composition_profile,
        ),
    )


def _build_gl_gateway_definition() -> RegionGatewayDefinition:
    from ba_downloader.infrastructure.regions.gl import profile
    from ba_downloader.infrastructure.regions.gl.provider import GLRegionProvider

    return RegionGatewayDefinition(
        descriptor=RegionDescriptor(
            region="gl",
            capabilities=GLRegionProvider.CAPABILITIES,
            workflow_policy=profile.GL_WORKFLOW_POLICY,
            settings_policy=profile.GL_SETTINGS_POLICY,
        ),
        catalog=CatalogGatewayFactories(profile.build_provider),
        runtime=RuntimeGatewayFactories(
            profile.build_runtime_asset_preparer,
            profile.build_dumper_backend,
        ),
        tables=TableGatewayFactories(
            profile.build_table_extraction_profile,
            profile.build_extraction_prerequisite,
        ),
        character_index=CharacterIndexGatewayFactories(
            profile.build_character_index_source_profile,
            profile.build_character_index_composition_profile,
        ),
    )


def _build_jp_gateway_definition() -> RegionGatewayDefinition:
    from ba_downloader.infrastructure.regions.jp import profile
    from ba_downloader.infrastructure.regions.jp.provider import JPRegionProvider

    return RegionGatewayDefinition(
        descriptor=RegionDescriptor(
            region="jp",
            capabilities=JPRegionProvider.CAPABILITIES,
            workflow_policy=profile.JP_WORKFLOW_POLICY,
            settings_policy=profile.JP_SETTINGS_POLICY,
        ),
        catalog=CatalogGatewayFactories(profile.build_provider),
        runtime=RuntimeGatewayFactories(
            profile.build_runtime_asset_preparer,
            profile.build_dumper_backend,
        ),
        tables=TableGatewayFactories(
            profile.build_table_extraction_profile,
            profile.build_extraction_prerequisite,
        ),
        character_index=CharacterIndexGatewayFactories(
            profile.build_character_index_source_profile,
            profile.build_character_index_composition_profile,
        ),
        catalog_metadata=CatalogMetadataGatewayFactories(
            profile.build_catalog_metadata_policy
        ),
    )


def build_default_region_gateway_registry() -> RegionGatewayRegistry:
    registry = RegionGatewayRegistry()
    registry.register_factory("cn", _build_cn_gateway_definition)
    registry.register_factory("gl", _build_gl_gateway_definition)
    registry.register_factory("jp", _build_jp_gateway_definition)
    return registry


DEFAULT_REGION_GATEWAY_REGISTRY = build_default_region_gateway_registry()


def build_application_region_profile(
    definition: RegionGatewayDefinition,
    *,
    logger: LoggerPort,
    table_metadata_store: TableMetadataManifestPort,
    provider: RegionProvider,
) -> RegionProfile:
    descriptor = definition.descriptor
    return build_region_profile(
        descriptor.workflow_policy,
        descriptor.settings_policy,
        definition.catalog_metadata.policy(
            provider,
            logger,
            table_metadata_store,
        ),
    )
