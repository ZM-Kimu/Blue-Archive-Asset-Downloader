from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.domain.models.character import CharacterRelation
from ba_downloader.domain.models.database import DBColumn, DBTable
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.character.relation import (
    CharacterNameRelation,
)
from ba_downloader.infrastructure.extraction.table.models import ProcessedTableArtifact


class RecordingLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warn_messages: list[str] = []
        self.error_messages: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def warn(self, message: str) -> None:
        self.warn_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)


class FakeTableSource:
    def __init__(
        self,
        tmp_path: Path,
        tables_by_name: dict[str, list[dict]] | None = None,
        zip_payloads: dict[str, bytes] | None = None,
    ) -> None:
        self.table_file_folder = str(tmp_path / "Raw" / "Table")
        self.extract_folder = str(tmp_path / "Temp" / "Table")
        self.tables_by_name = tables_by_name or {}
        self.zip_payloads = zip_payloads or {}
        self.table_names: list[str] = []

    def process_db_file(
        self,
        file_path: str,
        table_name: str = "",
        **kwargs: object,
    ) -> list[DBTable]:
        _ = file_path
        _ = kwargs
        self.table_names.append(table_name)
        rows = self.tables_by_name.get(table_name, [])
        return [_db_table(table_name, rows)] if rows else []

    def process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact:
        _ = archive_name
        _ = file_data
        _ = detect_type
        return ProcessedTableArtifact(
            data=self.zip_payloads.get(file_name, b"[]"),
            file_name=file_name,
        )


def _build_context(tmp_path: Path, region: str = "jp") -> RuntimeContext:
    return RuntimeContext(
        region=region,
        threads=4,
        version="1.0.0",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _db_table(name: str, rows: list[dict]) -> DBTable:
    columns = [DBColumn(name="Bytes", data_type="BLOB")]
    data = [[row] for row in rows]
    return DBTable(name=name, columns=columns, data=data)


def test_relation_extract_excel_warns_and_continues_when_one_source_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="cn"),
        logger,
        table_source=FakeTableSource(tmp_path),
    )

    monkeypatch.setattr(
        relation,
        "_CharacterNameRelation__extract_scenario_db",
        lambda: [{"Bytes": {"NameJP": "Arona", "SmallPortrait": "Portrait_Arona"}}],
    )
    monkeypatch.setattr(
        relation,
        "_CharacterNameRelation__extract_excel_bytes_files",
        lambda: {
            "characterexceltable.bytes": tmp_path / "characterexceltable.bytes",
        },
    )
    monkeypatch.setattr(
        relation,
        "_CharacterNameRelation__load_excel_payloads",
        lambda paths: {
            "characterexceltable.bytes": [{"Id": 1001, "DevName": "Arona"}],
        },
    )

    (
        scenario_db,
        char_profile,
        char_excel,
        costume_excel,
        shop_recruit,
        localize_gacha,
    ) = relation._CharacterNameRelation__extract_excel()

    assert scenario_db
    assert char_profile == []
    assert char_excel == [{"Id": 1001, "DevName": "Arona"}]
    assert costume_excel == []
    assert shop_recruit == []
    assert localize_gacha == []
    assert logger.warn_messages == [
        "Some relation sources are missing or invalid: localizecharprofileexceltable.bytes. Name relation might be incomplete."
    ]


def test_jp_relation_extract_excel_uses_excel_db_schema_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    table_source = FakeTableSource(
        tmp_path,
        {
            "ScenarioCharacterNameDBSchema": [
                {
                    "CharacterName": 1001,
                    "NameJP": "Arona",
                    "SmallPortrait": "Portrait_Arona",
                }
            ],
            "CharacterDBSchema": [
                {
                    "Id": 1001,
                    "DevName": "Arona",
                    "School": "SCHALE",
                    "Club": "System",
                }
            ],
            "LocalizeCharProfileDBSchema": [
                {
                    "CharacterId": 1001,
                    "FullNameJp": "Arona",
                    "CharacterVoiceJp": "Kohara Konomi",
                    "CharacterAgeJp": "16",
                    "CharHeightJp": "152cm",
                    "BirthDay": "1/1",
                    "IllustratorNameJp": "DoReMi",
                }
            ],
        },
    )
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        logger,
        table_source=table_source,
    )
    monkeypatch.setattr(
        relation,
        "_CharacterNameRelation__extract_excel_bytes_files",
        lambda: pytest.fail("JP relation should read ExcelDB schema tables"),
    )

    (
        scenario_db,
        char_profile,
        char_excel,
        costume_excel,
        shop_recruit,
        localize_gacha,
    ) = relation._CharacterNameRelation__extract_excel()

    assert table_source.table_names == [
        "ScenarioCharacterNameDBSchema",
        "CharacterDBSchema",
        "LocalizeCharProfileDBSchema",
    ]
    assert scenario_db == [
        {
            "Bytes": {
                "CharacterName": 1001,
                "NameJP": "Arona",
                "SmallPortrait": "Portrait_Arona",
            }
        }
    ]
    assert char_excel == [
        {
            "Id": 1001,
            "DevName": "Arona",
            "School": "SCHALE",
            "Club": "System",
        }
    ]
    assert char_profile == [
        {
            "CharacterId": 1001,
            "FullNameJp": "Arona",
            "CharacterVoiceJp": "Kohara Konomi",
            "CharacterAgeJp": "16",
            "CharHeightJp": "152cm",
            "BirthDay": "1/1",
            "IllustratorNameJp": "DoReMi",
        }
    ]
    assert costume_excel == []
    assert shop_recruit == []
    assert localize_gacha == []
    assert logger.warn_messages == []


def test_jp_relation_extract_excel_warns_with_schema_name_when_source_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        logger,
        table_source=FakeTableSource(
            tmp_path,
            {
                "ScenarioCharacterNameDBSchema": [
                    {
                        "CharacterName": 1001,
                        "NameJP": "Arona",
                        "SmallPortrait": "Portrait_Arona",
                    }
                ],
                "CharacterDBSchema": [{"Id": 1001, "DevName": "Arona"}],
            },
        ),
    )

    (
        scenario_db,
        char_profile,
        char_excel,
        costume_excel,
        shop_recruit,
        localize_gacha,
    ) = relation._CharacterNameRelation__extract_excel()

    assert scenario_db
    assert char_profile == []
    assert char_excel == [{"Id": 1001, "DevName": "Arona"}]
    assert costume_excel == []
    assert shop_recruit == []
    assert localize_gacha == []
    assert logger.warn_messages == [
        "Some relation sources are missing or invalid: LocalizeCharProfileDBSchema. Name relation might be incomplete."
    ]


def test_jp_relation_extract_excel_fails_when_all_db_sources_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    with pytest.raises(
        LookupError,
        match="all core relation sources are missing",
    ):
        relation._CharacterNameRelation__extract_excel()


def test_cn_relation_extract_excel_fails_when_all_core_sources_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="cn"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    monkeypatch.setattr(
        relation,
        "_CharacterNameRelation__extract_scenario_db",
        lambda: [],
    )
    monkeypatch.setattr(
        relation,
        "_CharacterNameRelation__extract_excel_bytes_files",
        lambda: {},
    )
    monkeypatch.setattr(
        relation,
        "_CharacterNameRelation__load_excel_payloads",
        lambda paths: {},
    )

    with pytest.raises(
        LookupError,
        match="all core relation sources are missing",
    ):
        relation._CharacterNameRelation__extract_excel()


def test_relation_uses_cn_profile_fallback_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="cn"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[],
        char_profile=[
            {
                "CharacterId": 10003,
                "CharacterVoiceKr": "本渡枫/米糊",
                "CharacterAgeKr": "16岁",
                "CharHeightKr": "158cm",
                "BirthDay": "11/27",
                "IllustratorNameKr": "Hwansang",
            }
        ],
        char_excel=[
            {
                "Id": 10003,
                "DevName": "Hihumi_default",
                "School": "Trinity",
                "Club": "RemedialClass",
            }
        ],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].cv == "本渡枫/米糊"
    assert relation_by_id[10003].age == 16
    assert relation_by_id[10003].height == 158
    assert relation_by_id[10003].birthday == "11/27"
    assert relation_by_id[10003].illustrator == "Hwansang"
    assert relation_by_id[10003].school_en == "Trinity"
    assert relation_by_id[10003].club_en == "RemedialClass"


def test_relation_applies_cn_gacha_names_and_costume_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="cn"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[],
        char_profile=[{"CharacterId": 10003}],
        char_excel=[{"Id": 10003, "DevName": "Hihumi_default"}],
        costume_excel=[
            {
                "CostumeGroupId": 10003,
                "DevName": "Hihumi_default",
                "ModelPrefabName": "Hihumi_Original",
                "TextureDir": "UIs/01_Common/01_Character/Student_Portrait_Hihumi",
            }
        ],
        shop_recruit=[{"Id": 5000200, "InfoCharacterId": [10003]}],
        localize_gacha=[
            {
                "GachaShopId": 5000200,
                "SubTitleKr": "日富美\uff083★\uff09招募概率提升\uff01",
            }
        ],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].names == ["日富美"]
    assert relation_by_id[10003].file_name == {"Hihumi"}


def test_relation_merges_scenario_aliases_without_scenario_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="cn"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[
            {
                "Bytes": {
                    "CharacterName": 4200835236,
                    "NameKr": "",
                    "NameJP": "",
                    "SmallPortrait": "UIs/01_Common/01_Character/Student_Portrait_Hihumi_Robber",
                }
            }
        ],
        char_profile=[{"CharacterId": 10003}],
        char_excel=[{"Id": 10003, "DevName": "Hihumi_default"}],
        costume_excel=[
            {
                "CostumeGroupId": 10003,
                "DevName": "Hihumi_default",
                "ModelPrefabName": "Hihumi_Original",
                "TextureDir": "UIs/01_Common/01_Character/Student_Portrait_Hihumi",
            }
        ],
        shop_recruit=[],
        localize_gacha=[],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].file_name == {
        "Hihumi",
        "HihumiRobber",
        "Hihumi_Robber",
    }
    assert 4200835236 not in relation_by_id


def test_jp_relation_does_not_match_non_latin_names_by_empty_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[
            {
                "Bytes": {
                    "CharacterName": 4200835236,
                    "NameJP": "ヒナ",
                    "SmallPortrait": "UIs/01_Common/01_Character/Student_Portrait_Hina",
                }
            }
        ],
        char_profile=[
            {
                "CharacterId": 16004,
                "FullNameJp": "朝比奈フィーナ",
                "PersonalNameJp": "フィーナ",
            }
        ],
        char_excel=[{"Id": 16004, "DevName": "Pina_default"}],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert sorted(relation_by_id) == [16004, 4200835236]
    assert relation_by_id[16004].file_name is None
    assert relation_by_id[4200835236].file_name == {"Hina"}
    assert relation_by_id[4200835236].names == ["hina", "ヒナ"]


def test_jp_relation_matches_kana_scenario_name_with_hepburn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[
            {
                "Bytes": {
                    "CharacterName": 4200835236,
                    "NameJP": "ヒフミ",
                    "SmallPortrait": "UIs/01_Common/01_Character/Student_Portrait_Hihumi",
                }
            }
        ],
        char_profile=[
            {
                "CharacterId": 10003,
                "FullNameJp": "阿慈谷ヒフミ",
                "PersonalNameJp": "ヒフミ",
            }
        ],
        char_excel=[{"Id": 10003, "DevName": "Hihumi_default"}],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].file_name == {"Hihumi"}


def test_jp_relation_keeps_long_alias_prefix_match_for_variants(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[
            {
                "Bytes": {
                    "CharacterName": 4200835236,
                    "NameJP": "ヒフミ",
                    "SmallPortrait": "UIs/01_Common/01_Character/Student_Portrait_Hihumi",
                }
            },
            {
                "Bytes": {
                    "CharacterName": 3077082557,
                    "NameJP": "",
                    "SmallPortrait": "UIs/01_Common/01_Character/Student_Portrait_Hihumi_Robber",
                }
            },
        ],
        char_profile=[
            {
                "CharacterId": 10003,
                "FullNameJp": "阿慈谷ヒフミ",
                "PersonalNameJp": "ヒフミ",
            }
        ],
        char_excel=[{"Id": 10003, "DevName": "Hihumi_default"}],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].file_name == {
        "Hihumi",
        "HihumiRobber",
        "Hihumi_Robber",
    }


def test_jp_relation_prefers_exact_file_match_over_prefix_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[
            {
                "Bytes": {
                    "CharacterName": 4200835236,
                    "NameJP": "",
                    "SmallPortrait": "UIs/01_Common/01_Character/Student_Portrait_Hinata",
                }
            }
        ],
        char_profile=[
            {
                "CharacterId": 10004,
                "FullNameJp": "空崎ヒナ",
                "PersonalNameJp": "ヒナ",
            },
            {
                "CharacterId": 10043,
                "FullNameJp": "若葉ヒナタ",
                "PersonalNameJp": "ヒナタ",
            },
        ],
        char_excel=[
            {"Id": 10004, "DevName": "Hina_default"},
            {"Id": 10043, "DevName": "Hinata_default"},
        ],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10004].file_name is None
    assert relation_by_id[10043].file_name == {"Hinata"}


def test_jp_relation_registers_unmatched_scenario_portraits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[
            {
                "Bytes": {
                    "CharacterName": 4200835236,
                    "NameJP": "未登録",
                    "SmallPortrait": "UIs/01_Common/01_Character/Student_Portrait_Unknown",
                }
            }
        ],
        char_profile=[],
        char_excel=[],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[4200835236].dev_name == "Unknown"
    assert relation_by_id[4200835236].names == ["mitouroku", "未登録"]
    assert relation_by_id[4200835236].file_name == {"Unknown"}


def test_jp_relation_registers_yume_scenario_only_portraits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[
            {
                "Bytes": {
                    "CharacterName": 2357886682,
                    "NameJP": "ユメ",
                    "SmallPortrait": "UIs/01_Common/01_Character/Student_Portrait_CH0157",
                }
            },
            {
                "Bytes": {
                    "CharacterName": 4059581467,
                    "NameJP": "ユメ",
                    "SmallPortrait": "UIs/01_Common/01_Character/NPC_Portrait_NP0166",
                }
            },
        ],
        char_profile=[],
        char_excel=[],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )

    assert len(relations) == 1
    assert relations[0].names == ["yume", "ユメ"]
    assert relations[0].file_name == {"CH0157", "NP0166"}


def test_jp_relation_registers_decagram_scenario_only_portrait(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )

    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[
            {
                "Bytes": {
                    "CharacterName": 48056105,
                    "NameJP": "デカグラマトン",
                    "SmallPortrait": "UIs/01_Common/01_Character/NPC_Portrait_NP0274",
                }
            }
        ],
        char_profile=[],
        char_excel=[],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[48056105].dev_name == "NP0274"
    assert relation_by_id[48056105].file_name == {"NP0274"}
    assert "デカグラマトン" in relation_by_id[48056105].names


def test_relation_search_matches_dev_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relation = CharacterNameRelation(
        _build_context(tmp_path, region="jp"),
        RecordingLogger(),
        table_source=FakeTableSource(tmp_path),
    )
    relations = relation._CharacterNameRelation__create_relation_list(
        scenario_db=[],
        char_profile=[],
        char_excel=[{"Id": 7010301, "DevName": "Droid_Decagram_Shield_M"}],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )
    character_relation = CharacterRelation("JP1.0.0", relations)

    keywords = relation._CharacterNameRelation__search_keywords(
        character_relation,
        ["decagram"],
    )

    assert keywords == ["Droid_Decagram_Shield_M"]


def test_relation_build_logs_saved_file_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = _build_context(tmp_path, region="jp")
    relation = CharacterNameRelation(
        context, logger, table_source=FakeTableSource(tmp_path)
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        relation,
        "_CharacterNameRelation__extract_excel",
        lambda: (
            [],
            [],
            [{"Id": 10003, "DevName": "Hihumi_default"}],
            [],
            [],
            [],
        ),
    )

    relation.build()

    relation_path = tmp_path / "JPCharacterRelation.json"
    assert relation_path.exists()
    assert logger.info_messages[-1] == (
        f"Character relation file saved to {relation_path.resolve()}."
    )
