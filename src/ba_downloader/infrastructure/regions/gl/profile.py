from __future__ import annotations

from ba_downloader.domain.models.region_profile import (
    RegionSettingsPolicy,
    RegionWorkflowPolicy,
    SyncExtractionMode,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.execution import CancellationPort
from ba_downloader.domain.ports.extract import (
    ExtractionPrerequisitePort,
    SchemaPreparationPort,
)
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
from ba_downloader.infrastructure.extraction.table.prerequisites import (
    TableExtractionPrerequisite,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.regions.gl.character_index import (
    GlDbCharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.regions.gl.provider import GLRegionProvider
from ba_downloader.infrastructure.regions.gl.runtime_assets import (
    GLRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.regions.gl.sqlcipher_key import (
    GlSqlCipherKeyProvider,
)
from ba_downloader.infrastructure.regions.gl.table_archives import (
    classify_gl_table_archive,
)
from ba_downloader.infrastructure.regions.ground_table_archives import (
    GROUND_FLATBUFFER_ARCHIVE_ROUTE,
    MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE,
    build_semantic_ground_archive_handlers,
)
from ba_downloader.infrastructure.storage import SqlCipherDatabaseResolver
from ba_downloader.infrastructure.tools.dump_backend import Cpp2IlDumpCsBackend

GL_WORKFLOW_POLICY = RegionWorkflowPolicy(
    prepares_schema_for_sync=True,
    sync_extraction_mode=SyncExtractionMode.post_download,
    table_extraction_prerequisite=True,
)
GL_SETTINGS_POLICY = RegionSettingsPolicy(
    retain_sqlcipher_key_hex=True,
)
GL_TABLE_ARCHIVE_ROUTES = frozenset(
    {
        ROUTE_RHYTHM_BEATMAP,
        ROUTE_GROUND_GRID_PATCH,
        ROUTE_GROUND_NODE_LAYER_PATCH,
        ROUTE_GROUND_STAGE_PATCH,
        ROUTE_RAW,
        ROUTE_STANDARD,
        GROUND_FLATBUFFER_ARCHIVE_ROUTE,
        MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE,
    }
)
GL_MEMORYPACK_DB_ROOT_TYPES = {
    "LevelSkillDataDBSchema.db": "MX.GameData.DAO.Battle.SkillLogicDAO",
    "LogicEffectDataDBSchema.db": "MX.GameData.DAO.Battle.LogicEffectDAO",
    "SkillVisualEffectDataDBSchema.db": "MX.AppData.DAO.Battle.SkillVisualDAO",
}
GL_TOP_LEVEL_MEMORYPACK_PAYLOADS = {
    "TableCatalog.bytes": "TableCatalog",
}
GL_PRESERVED_TOP_LEVEL_FILES = frozenset({"TableCatalog.hash"})
GL_PRESERVED_ARCHIVE_ENTRIES = frozenset(
    {
        "minigamecardexceltable.bytes",
        "minigameroadpuzzleexceltable.bytes",
        "minigameshootingexceltable.bytes",
    }
)


def build_provider(
    http_client: HttpClientPort,
    logger: LoggerPort,
    progress_factory: ProgressReporterFactoryPort | None = None,
    cancellation: CancellationPort | None = None,
) -> GLRegionProvider:
    _ = (progress_factory, cancellation)
    return GLRegionProvider(http_client=http_client, logger=logger)


def build_runtime_asset_preparer(
    http_client: HttpClientPort,
    logger: LoggerPort,
    progress_factory: ProgressReporterFactoryPort | None = None,
    cancellation: CancellationPort | None = None,
) -> GLRuntimeAssetPreparer:
    return GLRuntimeAssetPreparer(
        http_client=http_client,
        logger=logger,
        progress_factory=progress_factory,
        cancellation=cancellation,
    )


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
    _ = context
    return TableExtractionProfile(
        archive_registry=TableArchiveRegistry(
            classifier=classify_gl_table_archive,
            enabled_routes=GL_TABLE_ARCHIVE_ROUTES,
            handler_factory=build_semantic_ground_archive_handlers,
        ),
        payload_router=MemoryPackTablePayloadRouter(
            GL_MEMORYPACK_DB_ROOT_TYPES,
            allow_partial_memorypack=False,
        ),
        database_path_resolver=SqlCipherDatabaseResolver(
            context,
            key_provider=GlSqlCipherKeyProvider(context),
        ),
        top_level_memorypack_payloads=GL_TOP_LEVEL_MEMORYPACK_PAYLOADS,
        preserved_top_level_files=GL_PRESERVED_TOP_LEVEL_FILES,
        preserved_archive_entries=GL_PRESERVED_ARCHIVE_ENTRIES,
    )


def build_character_index_source_profile(
    context: RuntimeContext,
) -> CharacterIndexSourceProfile:
    _ = context
    return GlDbCharacterIndexSourceProfile()


def build_character_index_composition_profile(
    context: RuntimeContext,
) -> CharacterIndexCompositionProfile:
    _ = context
    return CharacterIndexCompositionProfile(romanize_japanese_names=False)


def build_extraction_prerequisite(
    schema_preparation: SchemaPreparationPort,
    logger: LoggerPort,
) -> ExtractionPrerequisitePort:
    return TableExtractionPrerequisite(
        schema_preparation,
        region="GL",
        logger=logger,
    )
