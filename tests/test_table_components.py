from __future__ import annotations

from ba_downloader.infrastructure.extractors.table_archives import (
    TableArchiveClassifier,
    TableArchiveKind,
)


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
