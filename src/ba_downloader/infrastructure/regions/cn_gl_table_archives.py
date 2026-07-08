from __future__ import annotations

from os import path

GROUND_GRID_SCHEMA_NAME = "GroundGridFlat.bytes"
GROUND_NODE_LAYER_SCHEMA_NAME = "GroundNodeLayerFlat.bytes"
MGS_LOGIC_GROUND_ARCHIVE_NAME = "MGSLogicGroundData.zip"
GROUND_ARCHIVE_PREFIXES = ("sb_", "rb_", "rd_", "db_", "c_sb_")
C_SB_RAW_SCRIPT_KEYWORDS = (
    "destroyhyakkiyakomatsuri",
    "wildhuntstreet",
    "expresstrain",
    "hyakkiyakomatsuri",
    "hyakkiyakomoviestreet",
    "hyakkiyakonorthtown",
    "trainroof",
)
RAW_SCRIPT_TEST_PREFIXES = (
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
RAW_SCRIPT_TEST_ARCHIVE_NAMES = (
    "camerarotatetest.zip",
    "changelooktargettest.zip",
    "ch0265test2.zip",
)


def is_cn_gl_table_archive_name(file_name: str) -> bool:
    archive_name = path.basename(file_name)
    lower_name = archive_name.lower()
    return (
        is_mgs_logic_ground_archive(archive_name)
        or is_c_sb_raw_script_archive(lower_name)
        or is_ground_archive(lower_name)
        or is_eliminate_raid_archive(lower_name)
        or is_enemy_boss_script_archive(lower_name)
        or is_raw_script_test_archive(lower_name)
        or is_numeric_stage_archive(lower_name)
    )


def is_mgs_logic_ground_archive(archive_name: str) -> bool:
    return archive_name == MGS_LOGIC_GROUND_ARCHIVE_NAME


def is_ground_archive(archive_name: str) -> bool:
    return archive_name.endswith(".zip") and archive_name.startswith(
        GROUND_ARCHIVE_PREFIXES
    )


def is_c_sb_raw_script_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name.startswith("c_sb_")
        and any(keyword in archive_name for keyword in C_SB_RAW_SCRIPT_KEYWORDS)
    )


def resolve_ground_schema_name(archive_name: str) -> str:
    if "_nodelayer" in archive_name:
        return GROUND_NODE_LAYER_SCHEMA_NAME
    return GROUND_GRID_SCHEMA_NAME


def is_numeric_stage_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name[:1].isdigit()
        and "eliminateraid" not in archive_name
    )


def is_eliminate_raid_archive(archive_name: str) -> bool:
    return archive_name.endswith(".zip") and "eliminateraid" in archive_name


def is_enemy_boss_script_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name.startswith("en")
        and len(archive_name) >= 6
        and archive_name[2:6].isdigit()
    )


def is_raw_script_test_archive(archive_name: str) -> bool:
    return (
        archive_name.startswith(RAW_SCRIPT_TEST_PREFIXES)
        or "obstest" in archive_name
        or "timelinetest" in archive_name
        or "emojitest" in archive_name
        or archive_name in RAW_SCRIPT_TEST_ARCHIVE_NAMES
    )
