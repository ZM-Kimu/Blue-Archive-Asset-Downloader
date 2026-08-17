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
from ba_downloader.domain.ports.execution import CancellationPort
from ba_downloader.domain.ports.extract import (
    ExtractionPrerequisitePort,
    SchemaPreparationPort,
)
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import ProgressReporterFactoryPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.infrastructure.extraction.character.index_composer import (
    CharacterIndexCompositionProfile,
)
from ba_downloader.infrastructure.extraction.character.index_sources import (
    CharacterIndexSourceProfile,
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
from ba_downloader.infrastructure.extraction.table.prerequisites import (
    TableExtractionPrerequisite,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.regions.ground_table_archives import (
    MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE,
    build_semantic_ground_archive_handlers,
)
from ba_downloader.infrastructure.regions.jp.catalog_decoder import JPCatalogDecoder
from ba_downloader.infrastructure.regions.jp.catalog_metadata import (
    JpTableCatalogMetadataPolicy,
)
from ba_downloader.infrastructure.regions.jp.character_index import (
    JpDbCharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.regions.jp.provider import JPRegionProvider
from ba_downloader.infrastructure.regions.jp.runtime_assets import (
    JPRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.regions.jp.sqlcipher_key import (
    JpSqlCipherKeyProvider,
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
)

JP_TABLE_ARCHIVE_ROUTES = frozenset(
    {
        ROUTE_RHYTHM_BEATMAP,
        ROUTE_GROUND_GRID_PATCH,
        ROUTE_GROUND_NODE_LAYER_PATCH,
        ROUTE_GROUND_STAGE_PATCH,
        ROUTE_RAW,
        ROUTE_STANDARD,
        MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE,
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
    progress_factory: ProgressReporterFactoryPort | None = None,
    cancellation: CancellationPort | None = None,
) -> JPRegionProvider:
    return JPRegionProvider(
        http_client,
        logger,
        catalog_decoder=JPCatalogDecoder(),
        progress_factory=progress_factory,
        cancellation=cancellation,
    )


def build_runtime_asset_preparer(
    http_client: HttpClientPort,
    logger: LoggerPort,
    progress_factory: ProgressReporterFactoryPort | None = None,
    cancellation: CancellationPort | None = None,
) -> JPRuntimeAssetPreparer:
    _ = (http_client, progress_factory)
    return JPRuntimeAssetPreparer(logger, cancellation=cancellation)


def build_dumper_backend(
    http_client: HttpClientPort,
    logger: LoggerPort,
    cancellation: CancellationPort,
) -> Cpp2IlDumpCsBackend:
    return Cpp2IlDumpCsBackend(
        http_client=http_client,
        logger=logger,
        cancellation=cancellation,
    )


def build_table_extraction_profile(
    context: RuntimeContext,
) -> TableExtractionProfile:
    return TableExtractionProfile(
        archive_registry=TableArchiveRegistry(
            classifier=classify_jp_table_archive,
            enabled_routes=JP_TABLE_ARCHIVE_ROUTES,
            handler_factory=build_semantic_ground_archive_handlers,
            warning_policy=JpTableArchiveWarningPolicy(),
        ),
        payload_router=MemoryPackTablePayloadRouter(
            JP_MEMORYPACK_DB_ROOT_TYPES,
            allow_partial_memorypack=False,
        ),
        database_path_resolver=SqlCipherDatabaseResolver(
            context,
            key_provider=JpSqlCipherKeyProvider(context),
        ),
    )


def build_character_index_source_profile(
    context: RuntimeContext,
) -> CharacterIndexSourceProfile:
    _ = context
    return JpDbCharacterIndexSourceProfile()


def build_character_index_composition_profile(
    context: RuntimeContext,
) -> CharacterIndexCompositionProfile:
    _ = context
    return CharacterIndexCompositionProfile(romanize_japanese_names=True)


def build_extraction_prerequisite(
    schema_preparation: SchemaPreparationPort,
    logger: LoggerPort,
) -> ExtractionPrerequisitePort:
    return TableExtractionPrerequisite(
        schema_preparation,
        region="JP",
        logger=logger,
    )


def build_catalog_metadata_policy(
    provider: RegionProvider,
    logger: LoggerPort,
    table_metadata_store: TableMetadataManifestPort,
) -> CatalogMetadataPolicy:
    return JpTableCatalogMetadataPolicy(provider, logger, table_metadata_store)
