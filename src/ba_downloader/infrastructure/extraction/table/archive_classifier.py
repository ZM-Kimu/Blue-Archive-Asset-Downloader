from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from os import path


class TableArchiveKind(Enum):
    RHYTHM_BEATMAP = "rhythm_beatmap"
    GROUND_GRID_PATCH = "ground_grid_patch"
    GROUND_NODE_LAYER_PATCH = "ground_node_layer_patch"
    GROUND_STAGE_PATCH = "ground_stage_patch"
    RAW = "raw"
    UNSUPPORTED = "unsupported"
    GL_GROUND = "gl_ground"
    GL_NUMERIC_STAGE = "gl_numeric_stage"
    MGS_LOGIC_GROUND = "mgs_logic_ground"
    STANDARD = "standard"


@dataclass(frozen=True, slots=True)
class TableArchiveRoute:
    kind: TableArchiveKind
    schema_name: str = ""
    info_message: str | None = None


_RHYTHM_BEATMAP_ARCHIVE_NAME = "RhythmBeatmapData.zip"
_GROUND_GRID_SCHEMA_NAME = "GroundGridFlat.bytes"
_GROUND_NODE_LAYER_SCHEMA_NAME = "GroundNodeLayerFlat.bytes"
_GL_GROUND_ARCHIVE_PREFIXES = ("sb_", "rb_", "rd_", "db_", "c_sb_")
_GL_C_SB_RAW_SCRIPT_KEYWORDS = (
    "destroyhyakkiyakomatsuri",
    "wildhuntstreet",
    "expresstrain",
    "hyakkiyakomatsuri",
    "hyakkiyakomoviestreet",
    "hyakkiyakonorthtown",
    "trainroof",
)
_GL_RAW_SCRIPT_TEST_PREFIXES = (
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
_GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES = (
    "camerarotatetest.zip",
    "changelooktargettest.zip",
    "ch0265test2.zip",
)


def classify_table_archive(file_name: str) -> TableArchiveRoute:
    return classify_legacy_table_archive(file_name)


def classify_jp_table_archive(file_name: str) -> TableArchiveRoute:
    archive_name = path.basename(file_name)
    lower_name = archive_name.lower()

    if archive_name == _RHYTHM_BEATMAP_ARCHIVE_NAME:
        return TableArchiveRoute(
            TableArchiveKind.RHYTHM_BEATMAP,
            info_message=(
                f"Extracted raw rhythm beatmap payloads from {archive_name}; "
                "semantic parser is not implemented yet."
            ),
        )

    if archive_name.startswith("TablePatchPack_"):
        if "GroundGrid" in archive_name:
            return TableArchiveRoute(TableArchiveKind.GROUND_GRID_PATCH)
        if "GroundNodeLayer" in archive_name:
            return TableArchiveRoute(TableArchiveKind.GROUND_NODE_LAYER_PATCH)
        if "GroundStage" in archive_name:
            return TableArchiveRoute(TableArchiveKind.GROUND_STAGE_PATCH)

    if _is_legacy_table_archive_name(archive_name, lower_name):
        return TableArchiveRoute(
            TableArchiveKind.UNSUPPORTED,
            info_message=(
                "JP table profile does not support legacy GL/MGS archive routes."
            ),
        )

    return TableArchiveRoute(TableArchiveKind.STANDARD)


def classify_legacy_table_archive(file_name: str) -> TableArchiveRoute:
    archive_name = path.basename(file_name)

    jp_route = classify_jp_table_archive(archive_name)
    if jp_route.kind not in {TableArchiveKind.STANDARD, TableArchiveKind.UNSUPPORTED}:
        return jp_route
    if archive_name == "MGSLogicGroundData.zip":
        return TableArchiveRoute(TableArchiveKind.MGS_LOGIC_GROUND)

    lower_name = archive_name.lower()
    if _is_gl_c_sb_raw_script_archive(lower_name):
        return TableArchiveRoute(TableArchiveKind.RAW)
    if _is_gl_ground_archive(lower_name):
        return TableArchiveRoute(
            TableArchiveKind.GL_GROUND,
            schema_name=_resolve_gl_ground_schema_name(lower_name),
        )
    if (
        _is_gl_eliminate_raid_archive(lower_name)
        or _is_gl_enemy_boss_script_archive(lower_name)
        or _is_gl_raw_script_test_archive(lower_name)
    ):
        return TableArchiveRoute(TableArchiveKind.RAW)
    if _is_gl_numeric_stage_archive(lower_name):
        return TableArchiveRoute(TableArchiveKind.GL_NUMERIC_STAGE)

    return TableArchiveRoute(TableArchiveKind.STANDARD)


def _is_legacy_table_archive_name(archive_name: str, lower_name: str) -> bool:
    return (
        archive_name == "MGSLogicGroundData.zip"
        or _is_gl_c_sb_raw_script_archive(lower_name)
        or _is_gl_ground_archive(lower_name)
        or _is_gl_eliminate_raid_archive(lower_name)
        or _is_gl_enemy_boss_script_archive(lower_name)
        or _is_gl_raw_script_test_archive(lower_name)
        or _is_gl_numeric_stage_archive(lower_name)
    )


def _is_gl_ground_archive(archive_name: str) -> bool:
    return archive_name.endswith(".zip") and archive_name.startswith(
        _GL_GROUND_ARCHIVE_PREFIXES
    )


def _is_gl_c_sb_raw_script_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name.startswith("c_sb_")
        and any(keyword in archive_name for keyword in _GL_C_SB_RAW_SCRIPT_KEYWORDS)
    )


def _resolve_gl_ground_schema_name(archive_name: str) -> str:
    if "_nodelayer" in archive_name:
        return _GROUND_NODE_LAYER_SCHEMA_NAME
    return _GROUND_GRID_SCHEMA_NAME


def _is_gl_numeric_stage_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name[:1].isdigit()
        and "eliminateraid" not in archive_name
    )


def _is_gl_eliminate_raid_archive(archive_name: str) -> bool:
    return archive_name.endswith(".zip") and "eliminateraid" in archive_name


def _is_gl_enemy_boss_script_archive(archive_name: str) -> bool:
    return (
        archive_name.endswith(".zip")
        and archive_name.startswith("en")
        and len(archive_name) >= 6
        and archive_name[2:6].isdigit()
    )


def _is_gl_raw_script_test_archive(archive_name: str) -> bool:
    return (
        archive_name.startswith(_GL_RAW_SCRIPT_TEST_PREFIXES)
        or "obstest" in archive_name
        or "timelinetest" in archive_name
        or "emojitest" in archive_name
        or archive_name in _GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES
    )
