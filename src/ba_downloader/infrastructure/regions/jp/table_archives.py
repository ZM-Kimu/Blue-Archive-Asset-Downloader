from __future__ import annotations

from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    ROUTE_STANDARD,
    ROUTE_UNSUPPORTED,
    TableArchiveRoute,
    classify_table_archive,
)
from ba_downloader.infrastructure.extraction.table.archive_support import (
    TableArchiveServices,
)
from ba_downloader.infrastructure.regions.legacy_table_archives import (
    is_legacy_table_archive_name,
)

LEGACY_JP_EXCEL_STALE_ENTRIES = frozenset(
    {
        "interactiveworldraidcarrierexceltable.bytes",
        "minigamecardexceltable.bytes",
        "minigamedreamcollectionscenarioexceltable.bytes",
        "minigameroadpuzzleexceltable.bytes",
        "minigameshootingexceltable.bytes",
        "scenarioresourceinfoexceltable.bytes",
    }
)
LEGACY_JP_EXCEL_STALE_WARNING_PREFIX = "legacy JP Excel.zip stale entry: "


def classify_jp_table_archive(file_name: str) -> TableArchiveRoute:
    standard_route = classify_table_archive(file_name)
    if standard_route.kind != ROUTE_STANDARD:
        return standard_route

    if is_legacy_table_archive_name(file_name):
        return TableArchiveRoute(
            ROUTE_UNSUPPORTED,
            info_message=(
                "JP table profile does not support legacy GL/MGS archive routes."
            ),
        )

    return TableArchiveRoute(ROUTE_STANDARD)


class JpTableArchiveWarningPolicy:
    def warn_unsupported_entry(
        self,
        services: TableArchiveServices,
        archive_name: str,
        item_name: str,
        warnings: list[str],
        first_error: Exception,
        second_error: Exception,
    ) -> bool:
        if archive_name != "Excel.zip":
            return False
        if item_name.lower() in LEGACY_JP_EXCEL_STALE_ENTRIES:
            warnings.append(f"{LEGACY_JP_EXCEL_STALE_WARNING_PREFIX}{item_name}")
            return True
        services.warn_skipped_entry(
            archive_name,
            item_name,
            warnings,
            "schema/payload unsupported; JP may expose this table via "
            f"ExcelDB.db DBSchema output. {first_error}; fallback failed "
            f"({second_error}).",
        )
        return True

    def emit_warning_summary(
        self,
        services: TableArchiveServices,
        archive_name: str,
        warnings: list[str],
    ) -> None:
        _ = archive_name
        legacy_excel_warnings = [
            warning
            for warning in warnings
            if warning.startswith(LEGACY_JP_EXCEL_STALE_WARNING_PREFIX)
        ]
        if not legacy_excel_warnings:
            return
        examples = ", ".join(
            warning.removeprefix(LEGACY_JP_EXCEL_STALE_WARNING_PREFIX)
            for warning in legacy_excel_warnings[:6]
        )
        services.logger.warn(
            f"Skipped {len(legacy_excel_warnings)} stale legacy Excel.zip "
            "entries; JP semantic table output should come from ExcelDB.db "
            f"or Const outputs. Examples: {examples}"
        )
