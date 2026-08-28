from __future__ import annotations

from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region_profile import (
    RegionSettingsPolicy,
    RegionWorkflowPolicy,
    SyncExtractionMode,
)
from ba_downloader.domain.ports.execution import CancellationPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import ProgressReporterFactoryPort
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
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.regions.cn.character_index import (
    CnCharacterIndexEnricher,
    CnDbCharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.regions.cn.dump_backend import (
    CnMetadataRecoveryDumpBackend,
)
from ba_downloader.infrastructure.regions.cn.provider import (
    CNRegionProvider,
    CNRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.regions.cn.table_archives import (
    classify_cn_table_archive,
)

CN_WORKFLOW_POLICY = RegionWorkflowPolicy(
    prepares_schema_for_sync=True,
    sync_extraction_mode=SyncExtractionMode.post_download,
)
CN_SETTINGS_POLICY = RegionSettingsPolicy()
CN_TABLE_ARCHIVE_KINDS = frozenset(
    {
        ROUTE_RHYTHM_BEATMAP,
        ROUTE_GROUND_GRID_PATCH,
        ROUTE_GROUND_NODE_LAYER_PATCH,
        ROUTE_GROUND_STAGE_PATCH,
        ROUTE_RAW,
        ROUTE_STANDARD,
    }
)
CN_MEMORYPACK_DB_ROOT_TYPES = {
    "LevelSkillDataDBSchema.db": "MX.GameData.DAO.Battle.SkillLogicDAO",
    "LogicEffectDataDBSchema.db": "MX.GameData.DAO.Battle.LogicEffectDAO",
    "SkillVisualEffectDataDBSchema.db": "MX.AppData.DAO.Battle.SkillVisualDAO",
}


def build_provider(
    http_client: HttpClientPort,
    logger: LoggerPort,
    progress_factory: ProgressReporterFactoryPort | None = None,
    cancellation: CancellationPort | None = None,
) -> CNRegionProvider:
    _ = (progress_factory, cancellation)
    return CNRegionProvider(http_client=http_client, logger=logger)


def build_runtime_asset_preparer(
    http_client: HttpClientPort,
    logger: LoggerPort,
    progress_factory: ProgressReporterFactoryPort | None = None,
    cancellation: CancellationPort | None = None,
) -> CNRuntimeAssetPreparer:
    return CNRuntimeAssetPreparer(
        http_client=http_client,
        logger=logger,
        progress_factory=progress_factory,
        cancellation=cancellation,
    )


def build_dumper_backend(
    http_client: HttpClientPort,
    logger: LoggerPort,
    progress_factory: ProgressReporterFactoryPort | None,
    cancellation: CancellationPort,
) -> CnMetadataRecoveryDumpBackend:
    return CnMetadataRecoveryDumpBackend(
        http_client=http_client,
        logger=logger,
        progress_factory=progress_factory,
        cancellation=cancellation,
    )


def build_table_extraction_profile(
    context: ExecutionContext,
    database_source_identity: DatabaseSourceIdentity | None = None,
) -> TableExtractionProfile:
    _ = (context, database_source_identity)
    return TableExtractionProfile(
        archive_registry=TableArchiveRegistry(
            classifier=classify_cn_table_archive,
            enabled_routes=CN_TABLE_ARCHIVE_KINDS,
        ),
        payload_router=MemoryPackTablePayloadRouter(
            CN_MEMORYPACK_DB_ROOT_TYPES,
            allow_partial_memorypack=True,
        ),
    )


def build_character_index_source_profile(
    context: ExecutionContext,
) -> CharacterIndexSourceProfile:
    _ = context
    return CnDbCharacterIndexSourceProfile()


def build_character_index_composition_profile(
    context: ExecutionContext,
) -> CharacterIndexCompositionProfile:
    _ = context
    return CharacterIndexCompositionProfile(
        romanize_japanese_names=False,
        enrichers=(CnCharacterIndexEnricher(),),
    )
