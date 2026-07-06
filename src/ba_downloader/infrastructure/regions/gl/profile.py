from __future__ import annotations

from ba_downloader.domain.models.region_profile import (
    RegionSettingsPolicy,
    RegionWorkflowPolicy,
    SyncExtractionMode,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
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
    FlatBufferTablePayloadRouter,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.regions.gl.provider import (
    GLRegionProvider,
    GLRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.regions.gl.table_archives import (
    build_gl_legacy_archive_handlers,
)
from ba_downloader.infrastructure.regions.legacy_relation import (
    LegacyArchiveRelationSourceProfile,
)
from ba_downloader.infrastructure.regions.legacy_table_archives import (
    LEGACY_GL_GROUND_ROUTE,
    LEGACY_GL_NUMERIC_STAGE_ROUTE,
    LEGACY_MGS_LOGIC_GROUND_ROUTE,
    classify_legacy_table_archive,
)
from ba_downloader.infrastructure.tools.dump_backend import Cpp2IlDumpCsBackend

GL_WORKFLOW_POLICY = RegionWorkflowPolicy(
    prepares_schema_for_sync=True,
    sync_extraction_mode=SyncExtractionMode.direct,
)
GL_SETTINGS_POLICY = RegionSettingsPolicy(relation_command_includes_version=True)
GL_TABLE_ARCHIVE_KINDS = frozenset(
    {
        ROUTE_RHYTHM_BEATMAP,
        ROUTE_GROUND_GRID_PATCH,
        ROUTE_GROUND_NODE_LAYER_PATCH,
        ROUTE_GROUND_STAGE_PATCH,
        ROUTE_RAW,
        ROUTE_STANDARD,
        LEGACY_GL_GROUND_ROUTE,
        LEGACY_GL_NUMERIC_STAGE_ROUTE,
        LEGACY_MGS_LOGIC_GROUND_ROUTE,
    }
)


def build_provider(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> GLRegionProvider:
    return GLRegionProvider(http_client=http_client, logger=logger)


def build_runtime_asset_preparer(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> GLRuntimeAssetPreparer:
    return GLRuntimeAssetPreparer(http_client=http_client, logger=logger)


def build_dumper_backend(
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> Cpp2IlDumpCsBackend:
    return Cpp2IlDumpCsBackend(http_client=http_client, logger=logger)


def build_table_extraction_profile(
    context: RuntimeContext,
) -> TableExtractionProfile:
    _ = context
    return TableExtractionProfile(
        archive_registry=TableArchiveRegistry(
            classifier=classify_legacy_table_archive,
            enabled_kinds=GL_TABLE_ARCHIVE_KINDS,
            handler_factory=build_gl_legacy_archive_handlers,
        ),
        payload_router=FlatBufferTablePayloadRouter(),
    )


def build_relation_source_profile(
    context: RuntimeContext,
) -> CharacterRelationSourceProfile:
    _ = context
    return LegacyArchiveRelationSourceProfile()


def build_relation_composition_profile(
    context: RuntimeContext,
) -> CharacterRelationCompositionProfile:
    _ = context
    return CharacterRelationCompositionProfile(romanize_japanese_names=False)
