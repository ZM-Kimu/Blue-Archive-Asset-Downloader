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
    FlatBufferTablePayloadRouter,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.regions.archive_character_index import (
    ArchiveCharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.regions.gl.provider import (
    GLRegionProvider,
    GLRuntimeAssetPreparer,
)
from ba_downloader.infrastructure.regions.gl.table_archives import (
    GROUND_FLATBUFFER_ARCHIVE_ROUTE,
    MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE,
    build_gl_table_archive_handlers,
    classify_gl_table_archive,
)
from ba_downloader.infrastructure.tools.dump_backend import Cpp2IlDumpCsBackend

GL_WORKFLOW_POLICY = RegionWorkflowPolicy(
    prepares_schema_for_sync=True,
    sync_extraction_mode=SyncExtractionMode.direct,
)
GL_SETTINGS_POLICY = RegionSettingsPolicy(character_index_command_includes_version=True)
GL_TABLE_ARCHIVE_KINDS = frozenset(
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
            classifier=classify_gl_table_archive,
            enabled_routes=GL_TABLE_ARCHIVE_KINDS,
            handler_factory=build_gl_table_archive_handlers,
        ),
        payload_router=FlatBufferTablePayloadRouter(),
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
    return CharacterIndexCompositionProfile(romanize_japanese_names=False)
