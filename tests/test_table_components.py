from __future__ import annotations

import sqlite3

import pytest

from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    TableArchiveKind,
    classify_jp_table_archive,
    classify_legacy_table_archive,
    classify_table_archive,
)
from ba_downloader.infrastructure.extraction.table.payload_router import (
    TablePayloadCodec,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    build_table_extraction_profile,
)
from ba_downloader.infrastructure.storage.sqlite_reader import TableDatabase
from support import build_runtime_context


def test_table_archive_classifier_preserves_special_archive_routes() -> None:
    assert (
        classify_table_archive("RhythmBeatmapData.zip").kind
        is TableArchiveKind.RHYTHM_BEATMAP
    )
    assert (
        classify_table_archive("TablePatchPack_GroundGrid_11.zip").kind
        is TableArchiveKind.GROUND_GRID_PATCH
    )
    assert (
        classify_table_archive("TablePatchPack_GroundStage_1.zip").kind
        is TableArchiveKind.GROUND_STAGE_PATCH
    )
    assert (
        classify_table_archive("C_sb_01_hyakkiyakomatsuri_p02_Little.zip").kind
        is TableArchiveKind.RAW
    )
    assert (
        classify_table_archive("1041104_03_s3_boss_02_desertcity_p01_d.zip").kind
        is TableArchiveKind.GL_NUMERIC_STAGE
    )
    assert (
        classify_table_archive("MGSLogicGroundData.zip").kind
        is TableArchiveKind.MGS_LOGIC_GROUND
    )
    assert classify_table_archive("Excel.zip").kind is TableArchiveKind.STANDARD


def test_table_archive_classifier_preserves_gl_ground_schema_selection() -> None:
    grid_route = classify_table_archive("sb_02_desertcity_p01_e.zip")
    node_layer_route = classify_table_archive("sb_02_desertcity_p01_e_nodelayer.zip")

    assert grid_route.kind is TableArchiveKind.GL_GROUND
    assert grid_route.schema_name == "GroundGridFlat.bytes"
    assert node_layer_route.kind is TableArchiveKind.GL_GROUND
    assert node_layer_route.schema_name == "GroundNodeLayerFlat.bytes"


def test_jp_table_archive_classifier_does_not_route_gl_legacy_archives() -> None:
    jp_route = classify_jp_table_archive("sb_02_desertcity_p01_e.zip")
    legacy_route = classify_legacy_table_archive("sb_02_desertcity_p01_e.zip")

    assert jp_route.kind is TableArchiveKind.UNSUPPORTED
    assert legacy_route.kind is TableArchiveKind.GL_GROUND
    assert legacy_route.schema_name == "GroundGridFlat.bytes"


def test_table_extraction_profile_splits_jp_and_legacy_routing(tmp_path) -> None:
    jp_profile = build_table_extraction_profile(
        build_runtime_context(tmp_path, region="jp")
    )
    cn_profile = build_table_extraction_profile(
        build_runtime_context(tmp_path, region="cn")
    )
    gl_profile = build_table_extraction_profile(
        build_runtime_context(tmp_path, region="gl")
    )

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

    assert jp_profile.archive_registry.classifier(
        "sb_02_desertcity_p01_e.zip"
    ).kind is (TableArchiveKind.UNSUPPORTED)
    assert cn_profile.archive_registry.classifier(
        "sb_02_desertcity_p01_e.zip"
    ).kind is (TableArchiveKind.GL_GROUND)
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
