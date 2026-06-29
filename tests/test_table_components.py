from __future__ import annotations

import sqlite3

import pytest

from ba_downloader.infrastructure.extraction.table.archives import (
    TableArchiveClassifier,
    TableArchiveKind,
)
from ba_downloader.infrastructure.storage.sqlite_reader import TableDatabase


def test_table_archive_classifier_preserves_special_archive_routes() -> None:
    classifier = TableArchiveClassifier()

    assert (
        classifier.classify("RhythmBeatmapData.zip").kind
        is TableArchiveKind.RHYTHM_BEATMAP
    )
    assert (
        classifier.classify("TablePatchPack_GroundGrid_11.zip").kind
        is TableArchiveKind.GROUND_GRID_PATCH
    )
    assert (
        classifier.classify("TablePatchPack_GroundStage_1.zip").kind
        is TableArchiveKind.GROUND_STAGE_PATCH
    )
    assert (
        classifier.classify("C_sb_01_hyakkiyakomatsuri_p02_Little.zip").kind
        is TableArchiveKind.RAW
    )
    assert (
        classifier.classify("1041104_03_s3_boss_02_desertcity_p01_d.zip").kind
        is TableArchiveKind.GL_NUMERIC_STAGE
    )
    assert (
        classifier.classify("MGSLogicGroundData.zip").kind
        is TableArchiveKind.MGS_LOGIC_GROUND
    )
    assert classifier.classify("Excel.zip").kind is TableArchiveKind.STANDARD


def test_table_archive_classifier_preserves_gl_ground_schema_selection() -> None:
    classifier = TableArchiveClassifier()

    grid_route = classifier.classify("sb_02_desertcity_p01_e.zip")
    node_layer_route = classifier.classify("sb_02_desertcity_p01_e_nodelayer.zip")

    assert grid_route.kind is TableArchiveKind.GL_GROUND
    assert grid_route.schema_name == "GroundGridFlat.bytes"
    assert node_layer_route.kind is TableArchiveKind.GL_GROUND
    assert node_layer_route.schema_name == "GroundNodeLayerFlat.bytes"


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
