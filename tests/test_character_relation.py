from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
)
from ba_downloader.domain.models.character import CharacterData, CharacterRelation
from ba_downloader.domain.models.database import DBColumn, DBTable
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.character.relation import (
    CharacterNameRelation,
)
from ba_downloader.infrastructure.extraction.character.relation_composer import (
    CharacterRelationComposer,
    CharacterRelationCompositionProfile,
)
from ba_downloader.infrastructure.extraction.character.relation_sources import (
    CharacterRelationSourceLoader,
    CharacterRelationSources,
)
from ba_downloader.infrastructure.extraction.character.relation_store import (
    CharacterRelationSearchIndex,
)
from ba_downloader.infrastructure.extraction.table.models import ProcessedTableArtifact
from ba_downloader.infrastructure.regions.jp.relation import JpDbRelationSourceProfile
from ba_downloader.infrastructure.regions.legacy_relation import (
    LegacyArchiveRelationSourceProfile,
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


class FakeRelationSourceLoader:
    def __init__(self, sources: CharacterRelationSources) -> None:
        self.sources = sources
        self.source_profiles: list[object] = []

    def load(self, source_profile: object) -> CharacterRelationSources:
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
) -> CharacterRelationSources:
    return CharacterRelationSources(
        scenario_db=scenario_db or [],
        char_profile=char_profile or [],
        char_excel=char_excel or [],
        costume_excel=costume_excel or [],
        shop_recruit=shop_recruit or [],
        localize_gacha=localize_gacha or [],
    )


def _compose_relation(
    region: str,
    *,
    scenario_db: list[dict] | None = None,
    char_profile: list[dict] | None = None,
    char_excel: list[dict] | None = None,
    costume_excel: list[dict] | None = None,
    shop_recruit: list[dict] | None = None,
    localize_gacha: list[dict] | None = None,
) -> list[CharacterData]:
    context = _build_context(Path("."), region=region)
    return CharacterRelationComposer().compose(
        _sources(
            scenario_db=scenario_db,
            char_profile=char_profile,
            char_excel=char_excel,
            costume_excel=costume_excel,
            shop_recruit=shop_recruit,
            localize_gacha=localize_gacha,
        ),
        _service_profile(region).relation_composition_profile_factory(context),
    )


def test_cn_relation_sources_warn_but_continue_when_profile_bytes_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = _build_context(tmp_path, region="cn")
    loader = CharacterRelationSourceLoader(FakeTableSource(tmp_path), logger)

    monkeypatch.setattr(
        loader,
        "extract_scenario_db",
        lambda: [{"Bytes": {"NameJP": "Arona", "SmallPortrait": "Portrait_Arona"}}],
    )
    monkeypatch.setattr(
        loader,
        "extract_excel_bytes_files",
        lambda: {
            "characterexceltable.bytes": tmp_path / "characterexceltable.bytes",
        },
    )
    monkeypatch.setattr(
        loader,
        "load_excel_payloads",
        lambda paths: {
            "characterexceltable.bytes": [{"Id": 1001, "DevName": "Arona"}],
        },
    )

    sources = loader.load(
        _service_profile(context.region).relation_source_profile_factory(context)
    )

    assert sources.scenario_db
    assert sources.char_excel == [{"Id": 1001, "DevName": "Arona"}]
    assert logger.by_level("warn") == [
        "Some relation sources are missing or invalid: localizecharprofileexceltable.bytes. Name relation might be incomplete."
    ]


def test_relation_source_profile_selects_jp_db_and_legacy_archive(
    tmp_path: Path,
) -> None:
    jp_context = _build_context(tmp_path, region="jp")
    cn_context = _build_context(tmp_path, region="cn")
    assert isinstance(
        _service_profile("jp").relation_source_profile_factory(jp_context),
        JpDbRelationSourceProfile,
    )
    assert isinstance(
        _service_profile("cn").relation_source_profile_factory(cn_context),
        LegacyArchiveRelationSourceProfile,
    )


def test_jp_relation_sources_read_excel_db_schemas_without_excel_zip(
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
    loader = CharacterRelationSourceLoader(table_source, logger)
    monkeypatch.setattr(
        loader,
        "extract_excel_bytes_files",
        lambda: pytest.fail("JP relation should read ExcelDB schema tables"),
    )

    sources = loader.load(
        _service_profile(context.region).relation_source_profile_factory(context)
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


def test_jp_relation_sources_warn_with_schema_name_when_source_is_missing(
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = _build_context(tmp_path, region="jp")
    loader = CharacterRelationSourceLoader(
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
        _service_profile(context.region).relation_source_profile_factory(context)
    )

    assert sources.scenario_db
    assert sources.char_excel == [{"Id": 1001, "DevName": "Arona"}]
    assert logger.by_level("warn") == [
        "Some relation sources are missing or invalid: LocalizeCharProfileDBSchema. Name relation might be incomplete."
    ]


def test_jp_relation_extract_excel_fails_when_all_db_sources_are_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="jp")
    loader = CharacterRelationSourceLoader(
        FakeTableSource(tmp_path),
        RecordingLogger(),
    )

    with pytest.raises(
        LookupError,
        match="all core relation sources are missing",
    ):
        loader.load(
            _service_profile(context.region).relation_source_profile_factory(context)
        )


def test_cn_relation_extract_excel_fails_when_all_core_sources_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    loader = CharacterRelationSourceLoader(
        FakeTableSource(tmp_path),
        RecordingLogger(),
    )

    monkeypatch.setattr(
        loader,
        "extract_scenario_db",
        lambda: [],
    )
    monkeypatch.setattr(
        loader,
        "extract_excel_bytes_files",
        lambda: {},
    )
    monkeypatch.setattr(
        loader,
        "load_excel_payloads",
        lambda paths: {},
    )

    with pytest.raises(
        LookupError,
        match="all core relation sources are missing",
    ):
        loader.load(
            _service_profile(context.region).relation_source_profile_factory(context)
        )


def test_relation_uses_cn_profile_fallback_fields() -> None:
    relations = _compose_relation(
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

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].cv == "本渡枫/米糊"
    assert relation_by_id[10003].age == 16
    assert relation_by_id[10003].height == 158
    assert relation_by_id[10003].birthday == "11/27"
    assert relation_by_id[10003].illustrator == "Hwansang"
    assert relation_by_id[10003].school_en == "Trinity"
    assert relation_by_id[10003].club_en == "RemedialClass"


def test_jp_relation_romanization_is_controlled_by_profile_policy() -> None:
    sources = _sources(
        char_profile=[
            {
                "CharacterId": 10003,
                "FullNameJp": "阿慈谷ヒフミ",
                "PersonalNameJp": "ヒフミ",
            }
        ],
    )
    composer = CharacterRelationComposer()

    jp_relations = composer.compose(
        sources,
        _service_profile("jp").relation_composition_profile_factory(
            _build_context(Path("."), "jp")
        ),
    )
    legacy_relations = composer.compose(
        sources,
        CharacterRelationCompositionProfile(
            romanize_japanese_names=False,
            enrichers=(),
        ),
    )

    assert "hifumi" in {name.lower() for name in jp_relations[0].names}
    assert "hifumi" not in {name.lower() for name in legacy_relations[0].names}


def test_relation_applies_cn_gacha_names_and_costume_aliases() -> None:
    relations = _compose_relation(
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

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].names == ["日富美"]
    assert relation_by_id[10003].file_name == {"Hihumi"}


def test_relation_merges_scenario_aliases_without_scenario_names() -> None:
    relations = _compose_relation(
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

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].file_name == {
        "Hihumi",
        "HihumiRobber",
        "Hihumi_Robber",
    }
    assert 4200835236 not in relation_by_id


def test_jp_relation_does_not_match_non_latin_names_by_empty_token() -> None:
    relations = _compose_relation(
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

    relation_by_id = {item.character_id: item for item in relations}
    assert sorted(relation_by_id) == [16004, 4200835236]
    assert relation_by_id[16004].file_name is None
    assert relation_by_id[4200835236].file_name == {"Hina"}
    assert relation_by_id[4200835236].names == ["hina", "ヒナ"]


def test_jp_relation_matches_kana_scenario_name_with_hepburn() -> None:
    relations = _compose_relation(
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

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].file_name == {"Hihumi"}


def test_jp_relation_keeps_long_alias_prefix_match_for_variants() -> None:
    relations = _compose_relation(
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

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10003].file_name == {
        "Hihumi",
        "HihumiRobber",
        "Hihumi_Robber",
    }


def test_jp_relation_prefers_exact_file_match_over_prefix_match() -> None:
    relations = _compose_relation(
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

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[10004].file_name is None
    assert relation_by_id[10043].file_name == {"Hinata"}


def test_jp_relation_registers_yume_scenario_only_portraits() -> None:
    relations = _compose_relation(
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

    assert len(relations) == 1
    assert relations[0].names == ["yume", "ユメ"]
    assert relations[0].file_name == {"CH0157", "NP0166"}


def test_jp_relation_registers_decagram_scenario_only_portrait() -> None:
    relations = _compose_relation(
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

    relation_by_id = {item.character_id: item for item in relations}
    assert relation_by_id[48056105].dev_name == "NP0274"
    assert relation_by_id[48056105].file_name == {"NP0274"}
    assert "デカグラマトン" in relation_by_id[48056105].names


def test_relation_search_matches_dev_name() -> None:
    relations = _compose_relation(
        "jp",
        scenario_db=[],
        char_profile=[],
        char_excel=[{"Id": 7010301, "DevName": "Droid_Decagram_Shield_M"}],
        costume_excel=[],
        shop_recruit=[],
        localize_gacha=[],
    )
    character_relation = CharacterRelation("JP1.0.0", relations)

    keywords = CharacterRelationSearchIndex().search(
        character_relation,
        ["decagram"],
    )

    assert keywords == ["Droid_Decagram_Shield_M"]


def test_relation_search_index_matches_names_files_dev_name_and_attributes() -> None:
    relation = CharacterRelation(
        "JP1.0.0",
        [
            CharacterData(
                10003,
                dev_name="Hihumi_default",
                names=["Ajitani Hifumi", "Hifumi"],
                file_name={"Hihumi"},
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
    search_index = CharacterRelationSearchIndex()

    assert search_index.search(relation, ["hifumi"]) == ["Hihumi", "Hihumi_default"]
    assert search_index.search(relation, ["cv=hondo kaede"]) == [
        "Hihumi",
        "Hihumi_default",
    ]
    assert search_index.search(relation, ["school=trinity"]) == [
        "Hihumi",
        "Hihumi_default",
    ]


def test_relation_build_logs_saved_file_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    context = _build_context(tmp_path, region="jp")
    source_loader = FakeRelationSourceLoader(
        _sources(char_excel=[{"Id": 10003, "DevName": "Hihumi_default"}])
    )
    relation = CharacterNameRelation(
        context,
        logger,
        table_source=FakeTableSource(tmp_path),
        source_loader=source_loader,
        relation_source_profile_factory=(
            _service_profile("jp").relation_source_profile_factory
        ),
    )
    monkeypatch.chdir(tmp_path)

    relation.build()

    relation_path = tmp_path / "JPCharacterRelation.json"
    assert relation_path.exists()
    assert logger.by_level("info")[-1] == (
        f"Character relation file saved to {relation_path.resolve()}."
    )
