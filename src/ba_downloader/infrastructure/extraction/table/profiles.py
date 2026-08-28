from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    SHARED_TABLE_ARCHIVE_ROUTE_KEYS,
    classify_table_archive,
)
from ba_downloader.infrastructure.extraction.table.archives import TableArchiveRegistry
from ba_downloader.infrastructure.extraction.table.database import DatabasePathResolver
from ba_downloader.infrastructure.extraction.table.payload_router import (
    FlatBufferTablePayloadRouter,
    TablePayloadRouter,
)


@dataclass(frozen=True, slots=True)
class TableExtractionProfile:
    archive_registry: TableArchiveRegistry
    payload_router: TablePayloadRouter
    database_path_resolver: DatabasePathResolver | None = None
    top_level_memorypack_payloads: Mapping[str, str] = field(default_factory=dict)
    preserved_top_level_files: frozenset[str] = frozenset()
    preserved_archive_entries: frozenset[str] = frozenset()


DEFAULT_TABLE_ARCHIVE_ROUTES = SHARED_TABLE_ARCHIVE_ROUTE_KEYS


def build_default_table_extraction_profile() -> TableExtractionProfile:
    return TableExtractionProfile(
        archive_registry=TableArchiveRegistry(
            classifier=classify_table_archive,
            enabled_routes=DEFAULT_TABLE_ARCHIVE_ROUTES,
        ),
        payload_router=FlatBufferTablePayloadRouter(),
    )


def build_default_table_profile_for_context(
    context: ExecutionContext,
    database_source_identity: DatabaseSourceIdentity | None = None,
) -> TableExtractionProfile:
    _ = (context, database_source_identity)
    return build_default_table_extraction_profile()
