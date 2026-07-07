from __future__ import annotations

from ba_downloader.domain.models.region_profile import (
    RegionSettingsPolicy,
    RegionWorkflowPolicy,
    SyncExtractionMode,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
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
from ba_downloader.infrastructure.regions.archive_character_index import (
    ArchiveCharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.regions.cn.character_index import (
    CnArchiveCharacterIndexEnricher,
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
CN_SETTINGS_POLICY = RegionSettingsPolicy(
    character_index_command_includes_version=False
)
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
) -> CNRegionProvider:
    return CNRegionProvider(http_client=http_client, logger=logger)


def build_runtime_asset_preparer(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> CNRuntimeAssetPreparer:
    return CNRuntimeAssetPreparer(http_client=http_client, logger=logger)


def build_dumper_backend(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> CnMetadataRecoveryDumpBackend:
    return CnMetadataRecoveryDumpBackend(http_client=http_client, logger=logger)


def build_table_extraction_profile(
    context: RuntimeContext,
) -> TableExtractionProfile:
    _ = context
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
    context: RuntimeContext,
) -> CharacterIndexSourceProfile:
    _ = context
    return ArchiveCharacterIndexSourceProfile()


def build_character_index_composition_profile(
    context: RuntimeContext,
) -> CharacterIndexCompositionProfile:
    _ = context
    return CharacterIndexCompositionProfile(
        romanize_japanese_names=False,
        enrichers=(CnArchiveCharacterIndexEnricher(),),
    )
