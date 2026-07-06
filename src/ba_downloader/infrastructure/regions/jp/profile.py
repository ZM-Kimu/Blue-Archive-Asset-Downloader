from __future__ import annotations

from ba_downloader.domain.models.region_profile import (
    RegionSettingsPolicy,
    RegionWorkflowPolicy,
    SyncExtractionMode,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.catalog_metadata import (
    CatalogMetadataPolicy,
    TableMetadataManifestPort,
)
from ba_downloader.domain.ports.extract import (
    ExtractionPrerequisitePort,
    SchemaPreparationPort,
)
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.infrastructure.extraction.character.relation_composer import (
    CharacterRelationCompositionProfile,
)
from ba_downloader.infrastructure.extraction.character.relation_sources import (
    CharacterRelationSourceProfile,
)
from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    ROUTE_GROUND_GRID_PATCH,
    ROUTE_GROUND_NODE_LAYER_PATCH,
    ROUTE_GROUND_STAGE_PATCH,
    ROUTE_RAW,
    ROUTE_RHYTHM_BEATMAP,
    ROUTE_STANDARD,
)
from ba_downloader.infrastructure.extraction.table.archives import TableArchiveRegistry
from ba_downloader.infrastructure.extraction.table.payload_router import (
    MemoryPackTablePayloadRouter,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.regions.jp.catalog_decoder import JPCatalogDecoder
from ba_downloader.infrastructure.regions.jp.catalog_metadata import (
    JpTableCatalogMetadataPolicy,
)
from ba_downloader.infrastructure.regions.jp.prerequisites import (
    JpTableExtractionPrerequisite,
)
from ba_downloader.infrastructure.regions.jp.provider import JPRegionProvider
from ba_downloader.infrastructure.regions.jp.relation import JpDbRelationSourceProfile
from ba_downloader.infrastructure.regions.jp.runtime_assets import (
    JPRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.regions.jp.table_archives import (
    JpTableArchiveWarningPolicy,
    classify_jp_table_archive,
)
from ba_downloader.infrastructure.storage import SqlCipherDatabaseResolver
from ba_downloader.infrastructure.tools.dump_backend import Cpp2IlDumpCsBackend

JP_WORKFLOW_POLICY = RegionWorkflowPolicy(
    prepares_schema_for_sync=True,
    sync_extraction_mode=SyncExtractionMode.post_download,
    table_extraction_prerequisite=True,
)
JP_SETTINGS_POLICY = RegionSettingsPolicy(
    include_platform_in_default_dirs=True,
    retain_sqlcipher_key_hex=True,
    relation_command_includes_version=False,
)

JP_TABLE_ARCHIVE_KINDS = frozenset(
    {
        ROUTE_RHYTHM_BEATMAP,
        ROUTE_GROUND_GRID_PATCH,
        ROUTE_GROUND_NODE_LAYER_PATCH,
        ROUTE_GROUND_STAGE_PATCH,
        ROUTE_RAW,
        ROUTE_STANDARD,
    }
)
JP_MEMORYPACK_DB_ROOT_TYPES = {
    "LevelSkillDataDBSchema.db": "MX.GameData.DAO.Battle.SkillLogicDAO",
    "LogicEffectDataDBSchema.db": "MX.GameData.DAO.Battle.LogicEffectDAO",
    "SkillVisualEffectDataDBSchema.db": "MX.AppData.DAO.Battle.SkillVisualDAO",
}


def build_provider(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> JPRegionProvider:
    return JPRegionProvider(
        http_client,
        logger,
        catalog_decoder=JPCatalogDecoder(),
    )


def build_runtime_asset_preparer(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> JPRuntimeAssetPreparer:
    _ = http_client
    return JPRuntimeAssetPreparer(logger)


def build_dumper_backend(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> Cpp2IlDumpCsBackend:
    return Cpp2IlDumpCsBackend(http_client=http_client, logger=logger)


def build_table_extraction_profile(
    context: RuntimeContext,
) -> TableExtractionProfile:
    return TableExtractionProfile(
        archive_registry=TableArchiveRegistry(
            classifier=classify_jp_table_archive,
            enabled_kinds=JP_TABLE_ARCHIVE_KINDS,
            warning_policy=JpTableArchiveWarningPolicy(),
        ),
        payload_router=MemoryPackTablePayloadRouter(
            JP_MEMORYPACK_DB_ROOT_TYPES,
            allow_partial_memorypack=False,
        ),
        database_path_resolver=SqlCipherDatabaseResolver(context),
    )


def build_relation_source_profile(
    context: RuntimeContext,
) -> CharacterRelationSourceProfile:
    _ = context
    return JpDbRelationSourceProfile()


def build_relation_composition_profile(
    context: RuntimeContext,
) -> CharacterRelationCompositionProfile:
    _ = context
    return CharacterRelationCompositionProfile(romanize_japanese_names=True)


def build_extraction_prerequisite(
    schema_preparation: SchemaPreparationPort,
    logger: LoggerPort,
) -> ExtractionPrerequisitePort:
    return JpTableExtractionPrerequisite(schema_preparation, logger)


def build_catalog_metadata_policy(
    provider: RegionProvider,
    logger: LoggerPort,
    table_metadata_store: TableMetadataManifestPort,
) -> CatalogMetadataPolicy:
    return JpTableCatalogMetadataPolicy(provider, logger, table_metadata_store)
