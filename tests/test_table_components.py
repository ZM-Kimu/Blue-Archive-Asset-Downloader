from __future__ import annotations

import sqlite3

import pytest

from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
)
from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    ROUTE_GROUND_GRID_PATCH,
    ROUTE_GROUND_STAGE_PATCH,
    ROUTE_RAW,
    ROUTE_RHYTHM_BEATMAP,
    ROUTE_STANDARD,
    ROUTE_UNSUPPORTED,
    classify_table_archive,
)
from ba_downloader.infrastructure.extraction.table.payload_router import (
    TablePayloadCodec,
)
from ba_downloader.infrastructure.regions.cn.table_archives import (
    classify_cn_table_archive,
)
from ba_downloader.infrastructure.regions.cn_gl_table_archives import (
    is_cn_gl_table_archive_name,
)
from ba_downloader.infrastructure.regions.gl.table_archives import (
    GROUND_FLATBUFFER_ARCHIVE_ROUTE,
    MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE,
    classify_gl_table_archive,
)
from ba_downloader.infrastructure.regions.jp.table_archives import (
    classify_jp_table_archive,
)
from ba_downloader.infrastructure.storage.sqlite_reader import TableDatabase
from support import build_runtime_context


def test_table_archive_classifier_preserves_shared_archive_routes() -> None:
    assert (
        classify_table_archive("RhythmBeatmapData.zip").route_key
        == ROUTE_RHYTHM_BEATMAP
    )
    assert (
        classify_table_archive("TablePatchPack_GroundGrid_11.zip").route_key
        == ROUTE_GROUND_GRID_PATCH
    )
    assert (
        classify_table_archive("TablePatchPack_GroundStage_1.zip").route_key
        == ROUTE_GROUND_STAGE_PATCH
    )
    assert classify_table_archive("Excel.zip").route_key == ROUTE_STANDARD


def test_cn_gl_table_archive_detectors_identify_shared_archive_families() -> None:
    assert is_cn_gl_table_archive_name("C_sb_01_hyakkiyakomatsuri_p02_Little.zip")
    assert is_cn_gl_table_archive_name("1041104_03_s3_boss_02_desertcity_p01_d.zip")
    assert is_cn_gl_table_archive_name("MGSLogicGroundData.zip")


def test_cn_table_archive_classifier_preserves_cn_gl_archives_as_raw() -> None:
    assert (
        classify_cn_table_archive("C_sb_01_hyakkiyakomatsuri_p02_Little.zip").route_key
        == ROUTE_RAW
    )
    assert (
        classify_cn_table_archive(
            "1041104_03_s3_boss_02_desertcity_p01_d.zip"
        ).route_key
        == ROUTE_RAW
    )


@pytest.mark.parametrize(
    "archive_name",
    [
        "C_sb_01_destroyhyakkiyakomatsuri_p01_Many.zip",
        "C_sb_01_wildhuntstreet_p02_Many.zip",
        "C_sb_03_expresstrain_p01_Little.zip",
        "C_sb_01_hyakkiyakomoviestreet_p01_Many.zip",
        "C_sb_02_trainroof_p01_d_NoSideTrain.zip",
        "C_sb_02_trainroof_p01_n_SideTrain.zip",
        "6062106_eliminateRaid_perorozilla_outdoor_light_insane_start2phase.zip",
        "EN0006_Eliminate_LightArmor_Hard.zip",
        "EN0006_VeryHard.zip",
        "EN0013_Torment_3Phase.zip",
        "DamageTest_Street_LightArmor.zip",
        "character_resource_video_03.zip",
        "chesedscenariotest.zip",
        "CH0265Test.zip",
        "BaseMentTest.zip",
        "combattest_hod01.zip",
        "EffectCountLimitTest_Limit.zip",
        "EmojiTest.zip",
        "AriusStreet_p01_n_Many_ObsTest.zip",
        "colourtimelinetest.zip",
        "CameraRotateTest.zip",
        "ChangeLookTargetTest.zip",
        "GroundPassiveTest01.zip",
        "HoldTest.zip",
        "HoverCraftTest.zip",
        "hyakkiyako.zip",
        "newyearpathvisualtest_p01.zip",
        "NP186Test.zip",
        "NPCTEST.zip",
        "OverrideTest_Normal.zip",
        "playground_obstacleset_little.zip",
        "RaidTest.zip",
        "9970_WorldEmojiTest.zip",
        "CH0265Test2.zip",
    ],
)
def test_cn_gl_table_archive_classifier_routes_raw_script_archives(
    archive_name: str,
) -> None:
    assert classify_gl_table_archive(archive_name).route_key == ROUTE_RAW
    assert classify_cn_table_archive(archive_name).route_key == ROUTE_RAW


@pytest.mark.parametrize(
    "archive_name",
    [
        "1041104_03_s3_boss_02_desertcity_p01_d.zip",
        "1052101_01_s2_02_deserttrack_p01_n.zip",
    ],
)
def test_cn_gl_table_archive_classifier_routes_numeric_stage_archives(
    archive_name: str,
) -> None:
    assert classify_gl_table_archive(archive_name).route_key == ROUTE_RAW
    assert classify_cn_table_archive(archive_name).route_key == ROUTE_RAW


def test_gl_table_archive_classifier_routes_ground_archives_for_semantic_decode() -> (
    None
):
    grid_route = classify_gl_table_archive("sb_02_desertcity_p01_e.zip")
    node_layer_route = classify_gl_table_archive("sb_02_desertcity_p01_e_nodelayer.zip")

    assert grid_route.route_key == GROUND_FLATBUFFER_ARCHIVE_ROUTE
    assert grid_route.schema_name == "GroundGridFlat.bytes"
    assert node_layer_route.route_key == GROUND_FLATBUFFER_ARCHIVE_ROUTE
    assert node_layer_route.schema_name == "GroundNodeLayerFlat.bytes"


def test_gl_table_archive_classifier_routes_mgs_logic_ground_as_mixed_decode() -> None:
    route = classify_gl_table_archive("MGSLogicGroundData.zip")

    assert route.route_key == MGS_LOGIC_GROUND_MIXED_ARCHIVE_ROUTE


def test_jp_table_archive_classifier_does_not_route_cn_gl_archive_families() -> None:
    jp_route = classify_jp_table_archive("sb_02_desertcity_p01_e.zip")
    gl_route = classify_gl_table_archive("sb_02_desertcity_p01_e.zip")

    assert jp_route.route_key == ROUTE_UNSUPPORTED
    assert gl_route.route_key == GROUND_FLATBUFFER_ARCHIVE_ROUTE
    assert gl_route.schema_name == "GroundGridFlat.bytes"


def test_table_extraction_profile_splits_jp_cn_and_gl_routing(tmp_path) -> None:
    jp_context = build_runtime_context(tmp_path, region="jp")
    cn_context = build_runtime_context(tmp_path, region="cn")
    gl_context = build_runtime_context(tmp_path, region="gl")
    jp_profile = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(
        "jp"
    ).table_profile_factory(jp_context)
    cn_profile = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(
        "cn"
    ).table_profile_factory(cn_context)
    gl_profile = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(
        "gl"
    ).table_profile_factory(gl_context)

    jp_route = jp_profile.payload_router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )
    cn_route = cn_profile.payload_router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )
    gl_route = gl_profile.payload_router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )

    assert (
        jp_profile.archive_registry.classifier("sb_02_desertcity_p01_e.zip").route_key
        == ROUTE_UNSUPPORTED
    )
    assert (
        cn_profile.archive_registry.classifier("sb_02_desertcity_p01_e.zip").route_key
        == ROUTE_RAW
    )
    assert (
        gl_profile.archive_registry.classifier("sb_02_desertcity_p01_e.zip").route_key
        == GROUND_FLATBUFFER_ARCHIVE_ROUTE
    )
    assert ROUTE_RAW in cn_profile.archive_registry.enabled_routes
    assert GROUND_FLATBUFFER_ARCHIVE_ROUTE in gl_profile.archive_registry.enabled_routes
    assert jp_route.codec is TablePayloadCodec.MEMORYPACK
    assert jp_route.allow_partial_memorypack is False
    assert cn_route.codec is TablePayloadCodec.MEMORYPACK
    assert cn_route.allow_partial_memorypack is True
    assert gl_route.codec is TablePayloadCodec.FLATBUFFER


def test_table_database_quotes_special_table_names(tmp_path) -> None:
    db_path = tmp_path / "special.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute('CREATE TABLE "select table" ("Id" INTEGER, "Name" TEXT)')
        connection.execute('INSERT INTO "select table" VALUES (1, "Arona")')

    with TableDatabase(str(db_path)) as database:
        assert database.get_table_list() == ["select table"]
        assert [
            column.name
            for column in database.get_table_column_structure("select table")
        ] == [
            "Id",
            "Name",
        ]
        column_names, rows = database.get_table_data("select table")

    assert column_names == ["Id", "Name"]
    assert rows == [(1, "Arona")]


def test_table_database_rejects_unknown_table_name(tmp_path) -> None:
    db_path = tmp_path / "sample.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute('CREATE TABLE "Sample" ("Id" INTEGER)')

    with (
        TableDatabase(str(db_path)) as database,
        pytest.raises(LookupError, match="Unknown SQLite table"),
    ):
        database.get_table_data('Sample"; DROP TABLE Sample; --')
