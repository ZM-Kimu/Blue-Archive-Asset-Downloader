from __future__ import annotations

from os import path

from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    ROUTE_RAW,
    ROUTE_STANDARD,
    TableArchiveRoute,
    classify_table_archive,
)
from ba_downloader.infrastructure.regions.cn_gl_table_archives import (
    is_c_sb_raw_script_archive,
    is_eliminate_raid_archive,
    is_enemy_boss_script_archive,
    is_ground_archive,
    is_ground_tool_archive,
    is_numeric_stage_archive,
    is_script_test_archive,
)
from ba_downloader.infrastructure.regions.ground_table_archives import (
    is_mgs_logic_ground_archive,
)


def classify_cn_table_archive(file_name: str) -> TableArchiveRoute:
    archive_name = path.basename(file_name)

    standard_route = classify_table_archive(archive_name)
    if standard_route.route_key != ROUTE_STANDARD:
        return standard_route

    lower_name = archive_name.lower()
    if (
        is_c_sb_raw_script_archive(lower_name)
        or is_ground_archive(lower_name)
        or is_eliminate_raid_archive(lower_name)
        or is_enemy_boss_script_archive(lower_name)
        or is_ground_tool_archive(lower_name)
        or is_script_test_archive(archive_name)
        or is_numeric_stage_archive(lower_name)
        or is_mgs_logic_ground_archive(archive_name)
    ):
        return TableArchiveRoute(ROUTE_RAW)

    return TableArchiveRoute(ROUTE_STANDARD)
