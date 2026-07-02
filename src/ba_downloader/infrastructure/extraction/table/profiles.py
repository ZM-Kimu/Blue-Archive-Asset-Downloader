from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    TableArchiveKind,
    classify_jp_table_archive,
    classify_legacy_table_archive,
)
from ba_downloader.infrastructure.extraction.table.archives import TableArchiveRegistry
from ba_downloader.infrastructure.extraction.table.database import DatabasePathResolver
from ba_downloader.infrastructure.extraction.table.payload_router import (
    CnLegacyTablePayloadRouter,
    FlatBufferTablePayloadRouter,
    JpTablePayloadRouter,
    TablePayloadRouter,
)
from ba_downloader.infrastructure.storage import SqlCipherDatabaseResolver


@dataclass(frozen=True, slots=True)
class TableExtractionProfile:
    archive_registry: TableArchiveRegistry
    payload_router: TablePayloadRouter
    database_path_resolver: DatabasePathResolver | None = None


JP_TABLE_ARCHIVE_KINDS = frozenset(
    {
        TableArchiveKind.RHYTHM_BEATMAP,
        TableArchiveKind.GROUND_GRID_PATCH,
        TableArchiveKind.GROUND_NODE_LAYER_PATCH,
        TableArchiveKind.GROUND_STAGE_PATCH,
        TableArchiveKind.RAW,
        TableArchiveKind.STANDARD,
    }
)

LEGACY_TABLE_ARCHIVE_KINDS = frozenset(TableArchiveKind)


def build_jp_table_archive_registry() -> TableArchiveRegistry:
    return TableArchiveRegistry(
        classifier=classify_jp_table_archive,
        enabled_kinds=JP_TABLE_ARCHIVE_KINDS,
    )


def build_legacy_table_archive_registry() -> TableArchiveRegistry:
    return TableArchiveRegistry(
        classifier=classify_legacy_table_archive,
        enabled_kinds=LEGACY_TABLE_ARCHIVE_KINDS,
    )


def build_table_extraction_profile(context: RuntimeContext) -> TableExtractionProfile:
    if context.region == "jp":
        return TableExtractionProfile(
            archive_registry=build_jp_table_archive_registry(),
            payload_router=JpTablePayloadRouter(),
            database_path_resolver=SqlCipherDatabaseResolver(context),
        )
    if context.region == "cn":
        return TableExtractionProfile(
            archive_registry=build_legacy_table_archive_registry(),
            payload_router=CnLegacyTablePayloadRouter(),
        )
    return TableExtractionProfile(
        archive_registry=build_legacy_table_archive_registry(),
        payload_router=FlatBufferTablePayloadRouter(),
    )


def build_default_table_extraction_profile() -> TableExtractionProfile:
    return TableExtractionProfile(
        archive_registry=build_legacy_table_archive_registry(),
        payload_router=FlatBufferTablePayloadRouter(),
    )
