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
from ba_downloader.infrastructure.regions.cn_gl_table_archives import (
    is_cn_gl_table_archive_name,
)

STALE_JP_EXCEL_ENTRIES = frozenset(
    {
        "interactiveworldraidcarrierexceltable.bytes",
        "minigamecardexceltable.bytes",
        "minigamedreamcollectionscenarioexceltable.bytes",
        "minigameroadpuzzleexceltable.bytes",
        "minigameshootingexceltable.bytes",
        "scenarioresourceinfoexceltable.bytes",
    }
)
STALE_JP_EXCEL_WARNING_PREFIX = "stale JP Excel.zip entry: "


def classify_jp_table_archive(file_name: str) -> TableArchiveRoute:
    standard_route = classify_table_archive(file_name)
    if standard_route.route_key != ROUTE_STANDARD:
        return standard_route

    if is_cn_gl_table_archive_name(file_name):
        return TableArchiveRoute(
            ROUTE_UNSUPPORTED,
            info_message=(
                "JP table profile does not support CN/GL archive-family routes."
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
        if item_name.lower() in STALE_JP_EXCEL_ENTRIES:
            warnings.append(f"{STALE_JP_EXCEL_WARNING_PREFIX}{item_name}")
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
        stale_excel_warnings = [
            warning
            for warning in warnings
            if warning.startswith(STALE_JP_EXCEL_WARNING_PREFIX)
        ]
        if not stale_excel_warnings:
            return
        examples = ", ".join(
            warning.removeprefix(STALE_JP_EXCEL_WARNING_PREFIX)
            for warning in stale_excel_warnings[:6]
        )
        services.logger.warn(
            f"Skipped {len(stale_excel_warnings)} stale JP Excel.zip "
            "entries; JP semantic table output should come from ExcelDB.db "
            f"or Const outputs. Examples: {examples}"
        )
