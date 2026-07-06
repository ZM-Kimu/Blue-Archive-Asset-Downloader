from __future__ import annotations

from collections.abc import Callable, Mapping
from os import path

from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    ROUTE_RAW,
    ROUTE_STANDARD,
    TableArchiveRoute,
    TableArchiveRouteKey,
    classify_table_archive,
)
from ba_downloader.infrastructure.extraction.table.archive_support import (
    TableArchiveServices,
)
from ba_downloader.infrastructure.extraction.table.archives import ArchiveHandler
from ba_downloader.infrastructure.extraction.table.models import ProgressCallback
from ba_downloader.infrastructure.extraction.table.raw_archives import (
    RawArchiveExporter,
)

GROUND_GRID_SCHEMA_NAME = "GroundGridFlat.bytes"
GROUND_NODE_LAYER_SCHEMA_NAME = "GroundNodeLayerFlat.bytes"
LEGACY_GL_GROUND_ROUTE = "gl_ground"
LEGACY_GL_NUMERIC_STAGE_ROUTE = "gl_numeric_stage"
LEGACY_MGS_LOGIC_GROUND_ROUTE = "mgs_logic_ground"
GL_GROUND_ARCHIVE_PREFIXES = ("sb_", "rb_", "rd_", "db_", "c_sb_")
GL_C_SB_RAW_SCRIPT_KEYWORDS = (
    "destroyhyakkiyakomatsuri",
    "wildhuntstreet",
    "expresstrain",
    "hyakkiyakomatsuri",
    "hyakkiyakomoviestreet",
    "hyakkiyakonorthtown",
    "trainroof",
)
GL_RAW_SCRIPT_TEST_PREFIXES = (
    "basementtest",
    "character_resource_",
    "charactertest",
    "ch0265test",
    "chesedscenariotest",
    "combattest_",
    "damagetest_",
    "effectcountlimittest_",
    "groundpassivetest",
    "holdtest",
    "hovercrafttest",
    "hyakkiyako",
    "newyearpathvisualtest",
    "np186test",
    "npctest",
    "overridetest_",
    "playground_obstacleset_",
    "raidtest",
)
GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES = (
    "camerarotatetest.zip",
    "changelooktargettest.zip",
    "ch0265test2.zip",
)


def classify_legacy_table_archive(file_name: str) -> TableArchiveRoute:
    archive_name = path.basename(file_name)

    standard_route = classify_table_archive(archive_name)
    if standard_route.kind != ROUTE_STANDARD:
        return standard_route
    if archive_name == "MGSLogicGroundData.zip":
        return TableArchiveRoute(LEGACY_MGS_LOGIC_GROUND_ROUTE)

    lower_name = archive_name.lower()
    if is_gl_c_sb_raw_script_archive(lower_name):
        return TableArchiveRoute(ROUTE_RAW)
    if is_gl_ground_archive(lower_name):
        return TableArchiveRoute(
            LEGACY_GL_GROUND_ROUTE,
            schema_name=resolve_gl_ground_schema_name(lower_name),
        )
    if (
        is_gl_eliminate_raid_archive(lower_name)
        or is_gl_enemy_boss_script_archive(lower_name)
        or is_gl_raw_script_test_archive(lower_name)
    ):
        return TableArchiveRoute(ROUTE_RAW)
    if is_gl_numeric_stage_archive(lower_name):
        return TableArchiveRoute(LEGACY_GL_NUMERIC_STAGE_ROUTE)

    return TableArchiveRoute(ROUTE_STANDARD)


def is_legacy_table_archive_name(file_name: str) -> bool:
    archive_name = path.basename(file_name)
    lower_name = archive_name.lower()
    return (
        archive_name == "MGSLogicGroundData.zip"
        or is_gl_c_sb_raw_script_archive(lower_name)
        or is_gl_ground_archive(lower_name)
        or is_gl_eliminate_raid_archive(lower_name)
        or is_gl_enemy_boss_script_archive(lower_name)
        or is_gl_raw_script_test_archive(lower_name)
        or is_gl_numeric_stage_archive(lower_name)
    )


def is_gl_ground_archive(archive_name: str) -> bool:
    return archive_name.endswith(".zip") and archive_name.startswith(
        GL_GROUND_ARCHIVE_PREFIXES
    )


def is_gl_c_sb_raw_script_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name.startswith("c_sb_")
        and any(keyword in archive_name for keyword in GL_C_SB_RAW_SCRIPT_KEYWORDS)
    )


def resolve_gl_ground_schema_name(archive_name: str) -> str:
    if "_nodelayer" in archive_name:
        return GROUND_NODE_LAYER_SCHEMA_NAME
    return GROUND_GRID_SCHEMA_NAME


def is_gl_numeric_stage_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name[:1].isdigit()
        and "eliminateraid" not in archive_name
    )


def is_gl_eliminate_raid_archive(archive_name: str) -> bool:
    return archive_name.endswith(".zip") and "eliminateraid" in archive_name


def is_gl_enemy_boss_script_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name.startswith("en")
        and len(archive_name) >= 6
        and archive_name[2:6].isdigit()
    )


def is_gl_raw_script_test_archive(archive_name: str) -> bool:
    return (
        archive_name.startswith(GL_RAW_SCRIPT_TEST_PREFIXES)
        or "obstest" in archive_name
        or "timelinetest" in archive_name
        or "emojitest" in archive_name
        or archive_name in GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES
    )


def build_legacy_raw_archive_handlers(
    services: TableArchiveServices,
    raw_exporter: RawArchiveExporter,
) -> Mapping[TableArchiveRouteKey, ArchiveHandler]:
    _ = services

    def extract_legacy_raw(
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = inner_password_names
        raw_exporter.extract(
            file_name,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
            info_message=route.info_message,
        )

    return {LEGACY_GL_NUMERIC_STAGE_ROUTE: extract_legacy_raw}
