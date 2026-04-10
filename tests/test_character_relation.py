from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extractors.character import CharacterNameRelation


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


def _patch_table_extractor_init(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_init(
        self: CharacterNameRelation,
        table_file_folder: str,
        extract_folder: str,
        flat_data_folder: str,
        *,
        logger: RecordingLogger,
    ) -> None:
        self.table_file_folder = table_file_folder
        self.extract_folder = extract_folder
        self.flat_data_folder = flat_data_folder
        self.logger = logger

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extractors.table.TableExtractor.__init__",
        fake_init,
    )


def test_relation_extract_excel_warns_and_continues_when_one_source_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_table_extractor_init(monkeypatch)
    logger = RecordingLogger()
    relation = CharacterNameRelation(_build_context(tmp_path), logger)

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


def test_relation_extract_excel_fails_when_all_core_sources_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_table_extractor_init(monkeypatch)
    relation = CharacterNameRelation(_build_context(tmp_path), RecordingLogger())

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
    _patch_table_extractor_init(monkeypatch)
    relation = CharacterNameRelation(_build_context(tmp_path, region="cn"), RecordingLogger())

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
    _patch_table_extractor_init(monkeypatch)
    relation = CharacterNameRelation(_build_context(tmp_path, region="cn"), RecordingLogger())

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
                "SubTitleKr": "日富美（3★）招募概率提升！",
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
    _patch_table_extractor_init(monkeypatch)
    relation = CharacterNameRelation(_build_context(tmp_path, region="cn"), RecordingLogger())

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
    assert relation_by_id[10003].file_name == {"Hihumi", "HihumiRobber", "Hihumi_Robber"}
    assert 4200835236 not in relation_by_id
