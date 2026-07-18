from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
)
from ba_downloader.domain.models.character import CharacterIndex, CharacterIndexEntry
from ba_downloader.domain.models.database import DBColumn, DBTable
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.character.character_index import (
    CharacterIndexBuilder,
)
from ba_downloader.infrastructure.extraction.character.index_composer import (
    CharacterIndexComposer,
    CharacterIndexCompositionProfile,
)
from ba_downloader.infrastructure.extraction.character.index_sources import (
    CharacterIndexSourceLoader,
    CharacterIndexSources,
)
from ba_downloader.infrastructure.extraction.character.index_store import (
    CharacterIndexSearcher,
)
from ba_downloader.infrastructure.extraction.table.models import ProcessedTableArtifact
from ba_downloader.infrastructure.regions.archive_character_index import (
    ArchiveCharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.regions.cn.character_index import (
    CnDbCharacterIndexSourceProfile,
)
from ba_downloader.infrastructure.regions.jp.character_index import (
    JpDbCharacterIndexSourceProfile,
)
from support import RecordingLogger


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


class FakeIndexSourceLoader:
    def __init__(self, sources: CharacterIndexSources) -> None:
        self.sources = sources
        self.source_profiles: list[object] = []

    def load(self, source_profile: object) -> CharacterIndexSources:
        self.source_profiles.append(source_profile)
        return self.sources


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


def _service_profile(region: str):
    return DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(region)  # type: ignore[arg-type]


def _db_table(name: str, rows: list[dict]) -> DBTable:
    columns = [DBColumn(name="Bytes", data_type="BLOB")]
    data = [[row] for row in rows]
    return DBTable(name=name, columns=columns, data=data)


def _sources(
    *,
    scenario_db: list[dict] | None = None,
    char_profile: list[dict] | None = None,
    char_excel: list[dict] | None = None,
    costume_excel: list[dict] | None = None,
    shop_recruit: list[dict] | None = None,
    localize_gacha: list[dict] | None = None,
) -> CharacterIndexSources:
    return CharacterIndexSources(
        scenario_db=scenario_db or [],
        char_profile=char_profile or [],
        char_excel=char_excel or [],
        costume_excel=costume_excel or [],
        shop_recruit=shop_recruit or [],
        localize_gacha=localize_gacha or [],
    )


def _compose_index_entries(
    region: str,
    *,
    scenario_db: list[dict] | None = None,
    char_profile: list[dict] | None = None,
    char_excel: list[dict] | None = None,
    costume_excel: list[dict] | None = None,
    shop_recruit: list[dict] | None = None,
    localize_gacha: list[dict] | None = None,
) -> list[CharacterIndexEntry]:
    context = _build_context(Path("."), region=region)
    return CharacterIndexComposer().compose(
        _sources(
            scenario_db=scenario_db,
            char_profile=char_profile,
            char_excel=char_excel,
            costume_excel=costume_excel,
            shop_recruit=shop_recruit,
            localize_gacha=localize_gacha,
        ),
        _service_profile(region).character_index_composition_profile_factory(context),
    )


def test_cn_index_sources_read_excel_db_schemas_without_archive_zip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = _build_context(tmp_path, region="cn")
    table_source = FakeTableSource(
        tmp_path,
        {
            "ScenarioCharacterNameDBSchema": [
                {
                    "CharacterName": 1001,
                    "NameKR": "阿洛娜",
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
                    "FullNameKr": "阿洛娜",
                    "CharacterVoiceKr": "Kohara Konomi",
                    "CharacterAgeKr": "16",
                    "CharHeightKr": "152cm",
                    "BirthDay": "1/1",
                    "IllustratorNameKr": "DoReMi",
                }
            ],
            "CostumeDBSchema": [
                {
                    "CostumeGroupId": 1001,
                    "DevName": "Arona_default",
                    "TextureDir": "Student_Portrait_Arona",
                }
            ],
            "ShopRecruitDBSchema": [{"Id": 100, "InfoCharacterId": [1001]}],
            "LocalizeGachaShopDBSchema": [
                {"GachaShopId": 100, "SubTitleKr": "【特别】阿洛娜招募概率提升!"}
            ],
        },
    )
    loader = CharacterIndexSourceLoader(table_source, logger)
    monkeypatch.setattr(
        loader,
        "extract_excel_bytes_files",
        lambda: pytest.fail("CN character index should read ExcelDB schema tables"),
    )

    sources = loader.load(
        _service_profile(context.region).character_index_source_profile_factory(context)
    )

    assert table_source.table_names == [
        "ScenarioCharacterNameDBSchema",
        "CharacterDBSchema",
        "LocalizeCharProfileDBSchema",
        "CostumeDBSchema",
        "ShopRecruitDBSchema",
        "LocalizeGachaShopDBSchema",
    ]
    assert sources.scenario_db == [
        {
            "Bytes": {
                "CharacterName": 1001,
                "NameKR": "阿洛娜",
                "SmallPortrait": "Portrait_Arona",
            }
        }
    ]
    assert sources.char_excel == [
        {
            "Id": 1001,
            "DevName": "Arona",
            "School": "SCHALE",
            "Club": "System",
        }
    ]
    assert sources.char_profile == [
        {
            "CharacterId": 1001,
            "FullNameKr": "阿洛娜",
            "CharacterVoiceKr": "Kohara Konomi",
            "CharacterAgeKr": "16",
            "CharHeightKr": "152cm",
            "BirthDay": "1/1",
            "IllustratorNameKr": "DoReMi",
        }
    ]
    assert sources.costume_excel == [
        {
            "CostumeGroupId": 1001,
            "DevName": "Arona_default",
            "TextureDir": "Student_Portrait_Arona",
        }
    ]
    assert sources.shop_recruit == [{"Id": 100, "InfoCharacterId": [1001]}]
    assert sources.localize_gacha == [
        {"GachaShopId": 100, "SubTitleKr": "【特别】阿洛娜招募概率提升!"}
    ]
    assert logger.by_level("warn") == []


def test_index_source_profile_selects_region_owned_sources(
    tmp_path: Path,
) -> None:
    jp_context = _build_context(tmp_path, region="jp")
    cn_context = _build_context(tmp_path, region="cn")
    gl_context = _build_context(tmp_path, region="gl")
    assert isinstance(
        _service_profile("jp").character_index_source_profile_factory(jp_context),
        JpDbCharacterIndexSourceProfile,
    )
    assert isinstance(
        _service_profile("cn").character_index_source_profile_factory(cn_context),
        CnDbCharacterIndexSourceProfile,
    )
    assert isinstance(
        _service_profile("gl").character_index_source_profile_factory(gl_context),
        ArchiveCharacterIndexSourceProfile,
    )


def test_jp_index_sources_read_excel_db_schemas_without_excel_zip(
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
    context = _build_context(tmp_path, region="jp")
    loader = CharacterIndexSourceLoader(table_source, logger)
    monkeypatch.setattr(
        loader,
        "extract_excel_bytes_files",
        lambda: pytest.fail("JP character index should read ExcelDB schema tables"),
    )

    sources = loader.load(
        _service_profile(context.region).character_index_source_profile_factory(context)
    )

    assert table_source.table_names == [
        "ScenarioCharacterNameDBSchema",
        "CharacterDBSchema",
        "LocalizeCharProfileDBSchema",
    ]
    assert sources.scenario_db == [
        {
            "Bytes": {
                "CharacterName": 1001,
                "NameJP": "Arona",
                "SmallPortrait": "Portrait_Arona",
            }
        }
    ]
    assert sources.char_excel == [
        {
            "Id": 1001,
            "DevName": "Arona",
            "School": "SCHALE",
            "Club": "System",
        }
    ]
    assert sources.char_profile == [
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
    assert logger.by_level("warn") == []


def test_jp_index_sources_warn_with_schema_name_when_source_is_missing(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = _build_context(tmp_path, region="jp")
    loader = CharacterIndexSourceLoader(
        FakeTableSource(
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
        logger,
    )

    sources = loader.load(
        _service_profile(context.region).character_index_source_profile_factory(context)
    )

    assert sources.scenario_db
    assert sources.char_excel == [{"Id": 1001, "DevName": "Arona"}]
    assert logger.by_level("warn") == [
        "Some character index sources are missing or invalid: LocalizeCharProfileDBSchema. Character index might be incomplete."
    ]


def test_jp_index_extract_excel_fails_when_all_db_sources_are_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="jp")
    loader = CharacterIndexSourceLoader(
        FakeTableSource(tmp_path),
        RecordingLogger(),
    )

    with pytest.raises(
        LookupError,
        match="all core index sources are missing",
    ):
        loader.load(
            _service_profile(context.region).character_index_source_profile_factory(
                context
            )
        )


def test_cn_index_sources_warn_with_schema_name_when_source_is_missing(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = _build_context(tmp_path, region="cn")
    loader = CharacterIndexSourceLoader(
        FakeTableSource(
            tmp_path,
            {
                "ScenarioCharacterNameDBSchema": [
                    {
                        "CharacterName": 1001,
                        "NameKR": "阿洛娜",
                        "SmallPortrait": "Portrait_Arona",
                    }
                ],
                "CharacterDBSchema": [{"Id": 1001, "DevName": "Arona"}],
            },
        ),
        logger,
    )

    sources = loader.load(
        _service_profile(context.region).character_index_source_profile_factory(context)
    )

    assert sources.scenario_db
    assert sources.char_excel == [{"Id": 1001, "DevName": "Arona"}]
    assert logger.by_level("warn") == [
        "Some character index sources are missing or invalid: LocalizeCharProfileDBSchema. Character index might be incomplete."
    ]


def test_cn_index_sources_fail_when_all_core_db_sources_are_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    loader = CharacterIndexSourceLoader(
        FakeTableSource(tmp_path),
        RecordingLogger(),
    )

    with pytest.raises(
        LookupError,
        match="all core index sources are missing",
    ):
        loader.load(
            _service_profile(context.region).character_index_source_profile_factory(
                context
            )
        )


def test_index_uses_cn_profile_fallback_fields() -> None:
    entries = _compose_index_entries(
        "cn",
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

    entry_by_id = {item.character_id: item for item in entries}
    assert entry_by_id[10003].cv == "本渡枫/米糊"
    assert entry_by_id[10003].age == 16
    assert entry_by_id[10003].height == 158
    assert entry_by_id[10003].birthday == "11/27"
    assert entry_by_id[10003].illustrator == "Hwansang"
    assert entry_by_id[10003].school_en == "Trinity"
    assert entry_by_id[10003].club_en == "RemedialClass"


def test_jp_index_romanization_is_controlled_by_profile_policy() -> None:
    sources = _sources(
        char_profile=[
            {
                "CharacterId": 10003,
                "FullNameJp": "阿慈谷ヒフミ",
                "PersonalNameJp": "ヒフミ",
            }
        ],
    )
    composer = CharacterIndexComposer()

    jp_entries = composer.compose(
        sources,
        _service_profile("jp").character_index_composition_profile_factory(
            _build_context(Path("."), "jp")
        ),
    )
    non_romanized_entries = composer.compose(
        sources,
        CharacterIndexCompositionProfile(
            romanize_japanese_names=False,
            enrichers=(),
        ),
    )

    assert "hifumi" in {name.lower() for name in jp_entries[0].names}
    assert "hifumi" not in {name.lower() for name in non_romanized_entries[0].names}


def test_index_applies_cn_gacha_names_and_costume_aliases() -> None:
    entries = _compose_index_entries(
        "cn",
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

    entry_by_id = {item.character_id: item for item in entries}
    assert entry_by_id[10003].names == ["日富美"]
    assert entry_by_id[10003].file_aliases == {"Hihumi"}


def test_index_merges_scenario_aliases_without_scenario_names() -> None:
    entries = _compose_index_entries(
        "cn",
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

    entry_by_id = {item.character_id: item for item in entries}
    assert entry_by_id[10003].file_aliases == {
        "Hihumi",
        "HihumiRobber",
        "Hihumi_Robber",
    }
    assert 4200835236 not in entry_by_id


def test_jp_index_does_not_match_non_latin_names_by_empty_token() -> None:
    entries = _compose_index_entries(
        "jp",
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

    entry_by_id = {item.character_id: item for item in entries}
    assert sorted(entry_by_id) == [16004, 4200835236]
    assert entry_by_id[16004].file_aliases is None
    assert entry_by_id[4200835236].file_aliases == {"Hina"}
    assert entry_by_id[4200835236].names == ["hina", "ヒナ"]


def test_jp_index_matches_kana_scenario_name_with_hepburn() -> None:
    entries = _compose_index_entries(
        "jp",
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

    entry_by_id = {item.character_id: item for item in entries}
    assert entry_by_id[10003].file_aliases == {"Hihumi"}


def test_jp_index_keeps_long_alias_prefix_match_for_variants() -> None:
    entries = _compose_index_entries(
        "jp",
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

    entry_by_id = {item.character_id: item for item in entries}
    assert entry_by_id[10003].file_aliases == {
        "Hihumi",
        "HihumiRobber",
        "Hihumi_Robber",
    }


def test_jp_index_prefers_exact_file_match_over_prefix_match() -> None:
    entries = _compose_index_entries(
        "jp",
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

    entry_by_id = {item.character_id: item for item in entries}
    assert entry_by_id[10004].file_aliases is None
    assert entry_by_id[10043].file_aliases == {"Hinata"}


def test_jp_index_registers_yume_scenario_only_portraits() -> None:
    entries = _compose_index_entries(
        "jp",
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

    assert len(entries) == 1
    assert entries[0].names == ["yume", "ユメ"]
    assert entries[0].file_aliases == {"CH0157", "NP0166"}


def test_jp_index_registers_decagram_scenario_only_portrait() -> None:
    entries = _compose_index_entries(
        "jp",
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

    entry_by_id = {item.character_id: item for item in entries}
    assert entry_by_id[48056105].dev_name == "NP0274"
    assert entry_by_id[48056105].file_aliases == {"NP0274"}
    assert "デカグラマトン" in entry_by_id[48056105].names


def test_character_index_search_matches_dev_name() -> None:
    entries = _compose_index_entries(
        "jp",
        scenario_db=[],
        char_profile=[],
        char_excel=[{"Id": 7010301, "DevName": "Droid_Decagram_Shield_M"}],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )
    character_index = CharacterIndex("JP1.0.0", entries)

    keywords = CharacterIndexSearcher().search(
        character_index,
        ["decagram"],
    )

    assert keywords == ["Droid_Decagram_Shield_M"]


def test_character_index_search_index_matches_names_files_dev_name_and_attributes() -> (
    None
):
    index = CharacterIndex(
        "JP1.0.0",
        [
            CharacterIndexEntry(
                10003,
                dev_name="Hihumi_default",
                names=["Ajitani Hifumi", "Hifumi"],
                file_aliases={"Hihumi"},
                cv="Hondo Kaede",
                age=16,
                height=158,
                birthday="11/27",
                illustrator="Hwansang",
                school_en="Trinity",
                club_en="RemedialClass",
            )
        ],
    )
    searcher = CharacterIndexSearcher()

    assert searcher.search(index, ["hifumi"]) == ["Hihumi", "Hihumi_default"]
    assert searcher.search(index, ["cv=hondo kaede"]) == [
        "Hihumi",
        "Hihumi_default",
    ]
    assert searcher.search(index, ["school=trinity"]) == [
        "Hihumi",
        "Hihumi_default",
    ]


def test_index_build_logs_saved_file_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = _build_context(tmp_path, region="jp")
    source_loader = FakeIndexSourceLoader(
        _sources(char_excel=[{"Id": 10003, "DevName": "Hihumi_default"}])
    )
    index_builder = CharacterIndexBuilder(
        context,
        logger,
        table_source=FakeTableSource(tmp_path),
        source_loader=source_loader,
        character_index_source_profile_factory=(
            _service_profile("jp").character_index_source_profile_factory
        ),
    )
    monkeypatch.chdir(tmp_path)

    index_builder.build()

    index_path = tmp_path / "JPCharacterIndex.json"
    assert index_path.exists()
    assert logger.by_level("info")[-1] == (
        f"Character index file saved to {index_path.resolve()}."
    )
