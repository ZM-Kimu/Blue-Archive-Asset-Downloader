from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from os import path


class TableArchiveKind(Enum):
    RHYTHM_BEATMAP = "rhythm_beatmap"
    GROUND_GRID_PATCH = "ground_grid_patch"
    GROUND_STAGE_PATCH = "ground_stage_patch"
    RAW = "raw"
    GL_GROUND = "gl_ground"
    GL_NUMERIC_STAGE = "gl_numeric_stage"
    MGS_LOGIC_GROUND = "mgs_logic_ground"
    STANDARD = "standard"


@dataclass(frozen=True, slots=True)
class TableArchiveRoute:
    kind: TableArchiveKind
    schema_name: str = ""
    info_message: str | None = None


class TableArchiveClassifier:
    GROUND_GRID_SCHEMA_NAME = "GroundGridFlat.bytes"
    GROUND_NODE_LAYER_SCHEMA_NAME = "GroundNodeLayerFlat.bytes"
    RHYTHM_BEATMAP_ARCHIVE_NAME = "RhythmBeatmapData.zip"
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

    def classify(self, file_name: str) -> TableArchiveRoute:
        archive_name = path.basename(file_name)
        if self.is_rhythm_beatmap_archive(archive_name):
            return TableArchiveRoute(
                TableArchiveKind.RHYTHM_BEATMAP,
                info_message=(
                    f"Extracted raw rhythm beatmap payloads from {archive_name}; "
                    "semantic parser is not implemented yet."
                ),
            )
        if self.is_ground_grid_patch_archive(archive_name):
            return TableArchiveRoute(TableArchiveKind.GROUND_GRID_PATCH)
        if self.is_ground_stage_patch_archive(archive_name):
            return TableArchiveRoute(TableArchiveKind.GROUND_STAGE_PATCH)
        if self.is_gl_c_sb_raw_script_archive(archive_name):
            return TableArchiveRoute(TableArchiveKind.RAW)
        if self.is_gl_ground_archive(archive_name):
            return TableArchiveRoute(
                TableArchiveKind.GL_GROUND,
                schema_name=self.resolve_gl_ground_schema_name(archive_name),
            )
        if (
            self.is_gl_eliminate_raid_archive(archive_name)
            or self.is_gl_enemy_boss_script_archive(archive_name)
            or self.is_gl_raw_script_test_archive(archive_name)
        ):
            return TableArchiveRoute(TableArchiveKind.RAW)
        if self.is_gl_numeric_stage_archive(archive_name):
            return TableArchiveRoute(TableArchiveKind.GL_NUMERIC_STAGE)
        if self.is_mgs_logic_ground_archive(archive_name):
            return TableArchiveRoute(TableArchiveKind.MGS_LOGIC_GROUND)
        return TableArchiveRoute(TableArchiveKind.STANDARD)

    @staticmethod
    def is_ground_grid_patch_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name)
        return (
            archive_name.startswith("TablePatchPack_") and "GroundGrid" in archive_name
        )

    @staticmethod
    def is_ground_stage_patch_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name)
        return (
            archive_name.startswith("TablePatchPack_") and "GroundStage" in archive_name
        )

    @classmethod
    def is_gl_ground_archive(cls, file_name: str) -> bool:
        archive_name = path.basename(file_name)
        lower_name = archive_name.lower()
        return lower_name.endswith(".zip") and lower_name.startswith(
            cls.GL_GROUND_ARCHIVE_PREFIXES
        )

    @classmethod
    def is_gl_c_sb_raw_script_archive(cls, file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return (
            archive_name.endswith(".zip")
            and archive_name.startswith("c_sb_")
            and any(
                keyword in archive_name for keyword in cls.GL_C_SB_RAW_SCRIPT_KEYWORDS
            )
        )

    @classmethod
    def resolve_gl_ground_schema_name(cls, archive_name: str) -> str:
        if "_nodelayer" in archive_name.lower():
            return cls.GROUND_NODE_LAYER_SCHEMA_NAME
        return cls.GROUND_GRID_SCHEMA_NAME

    @staticmethod
    def is_gl_numeric_stage_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return (
            archive_name.endswith(".zip")
            and archive_name[:1].isdigit()
            and "eliminateraid" not in archive_name
        )

    @staticmethod
    def is_gl_eliminate_raid_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return archive_name.endswith(".zip") and "eliminateraid" in archive_name

    @staticmethod
    def is_gl_enemy_boss_script_archive(file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return (
            archive_name.endswith(".zip")
            and archive_name.startswith("en")
            and len(archive_name) >= 6
            and archive_name[2:6].isdigit()
        )

    @staticmethod
    def is_mgs_logic_ground_archive(file_name: str) -> bool:
        return path.basename(file_name) == "MGSLogicGroundData.zip"

    @classmethod
    def is_gl_raw_script_test_archive(cls, file_name: str) -> bool:
        archive_name = path.basename(file_name).lower()
        return (
            archive_name.startswith(cls.GL_RAW_SCRIPT_TEST_PREFIXES)
            or "obstest" in archive_name
            or "timelinetest" in archive_name
            or "emojitest" in archive_name
            or archive_name in cls.GL_RAW_SCRIPT_TEST_ARCHIVE_NAMES
        )

    @classmethod
    def is_rhythm_beatmap_archive(cls, file_name: str) -> bool:
        return path.basename(file_name) == cls.RHYTHM_BEATMAP_ARCHIVE_NAME
