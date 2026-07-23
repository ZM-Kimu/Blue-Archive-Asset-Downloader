from __future__ import annotations

import json
import sqlite3
import zlib
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import flatbuffers
import pytest

from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.table.codecs import (
    TablePayloadCodecAdapter,
)
from ba_downloader.infrastructure.extraction.table.extractor import (
    FlatBufferExportError,
    MalformedTablePayloadError,
    ProcessedTableArtifact,
    TableDecryptError,
    TableExtractor,
    UnsupportedSchemaError,
)
from ba_downloader.infrastructure.extraction.table.payload_router import (
    FlatBufferTablePayloadRouter,
    TablePayloadCodec,
)
from ba_downloader.infrastructure.schema.crypto import xor_with_key, zip_password
from ba_downloader.infrastructure.schema.flatbuffer.generator import (
    CompileFlatBufferToPython,
)
from ba_downloader.infrastructure.schema.flatbuffer.parser import FlatBufferCSParser


def _table_profile(context: RuntimeContext):
    return DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(
        context.region
    ).table_profile_factory(context)


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


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
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


def _flatbuffer_dump_cs() -> str:
    return """// Namespace: FlatData
public struct CharacterExcel : FlatBuffers.IFlatbufferObject // TypeDefIndex: 1 Token: 0x02000001
{
}

// Namespace: FlatData
public struct CharacterExcelTable : FlatBuffers.IFlatbufferObject // TypeDefIndex: 2 Token: 0x02000002
{
    public System.Int32 DataListLength { get; } // Token: 0x17000001
    public System.Nullable`1<FlatData.CharacterExcel> DataList(System.Int32 j) { }
}

// Namespace: FlatData
public struct GroundGridFlat : FlatBuffers.IFlatbufferObject // TypeDefIndex: 3 Token: 0x02000003
{
}

// Namespace: FlatData
public struct GroundNodeLayerFlat : FlatBuffers.IFlatbufferObject // TypeDefIndex: 4 Token: 0x02000004
{
}
"""


def _flatbuffer_row_only_dump_cs() -> str:
    return """// Namespace: FlatData
public struct CharacterExcel : FlatBuffers.IFlatbufferObject // TypeDefIndex: 1 Token: 0x02000001
{
}
"""


def _create_flat_buffer_data_package(flatbuffer_data_dir: Path) -> None:
    dump_path = flatbuffer_data_dir.parent / "dump.cs"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_text(_flatbuffer_dump_cs(), encoding="utf8")
    parser = FlatBufferCSParser(str(dump_path))
    CompileFlatBufferToPython(
        parser.parse_types(),
        str(flatbuffer_data_dir),
        parser.parse_enums(),
    ).create_schema_files()


def _create_flat_buffer_row_only_package(flatbuffer_data_dir: Path) -> None:
    dump_path = flatbuffer_data_dir.parent / "dump.cs"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_text(_flatbuffer_row_only_dump_cs(), encoding="utf8")
    parser = FlatBufferCSParser(str(dump_path))
    CompileFlatBufferToPython(
        parser.parse_types(),
        str(flatbuffer_data_dir),
        parser.parse_enums(),
    ).create_schema_files()


def _create_empty_memorypack_data_package(memorypack_data_dir: Path) -> None:
    memorypack_data_dir.mkdir(parents=True, exist_ok=True)
    (memorypack_data_dir / "__init__.py").write_text(
        "from ._registry import MEMORYPACK_ENUMS, MEMORYPACK_TYPES\n",
        encoding="utf8",
    )
    (memorypack_data_dir / "_registry.py").write_text(
        "MEMORYPACK_TYPES = {}\nMEMORYPACK_ENUMS = {}\n",
        encoding="utf8",
    )


def _write_memorypack_formatter_sidecar(extract_dir: Path, payload: dict) -> None:
    dumps_dir = extract_dir / "Dumps"
    dumps_dir.mkdir(parents=True, exist_ok=True)
    (dumps_dir / "memorypack_formatters.json").write_text(
        json.dumps(payload),
        encoding="utf8",
    )


def _create_blob_database(
    table_dir: Path,
    db_name: str,
    table_name: str,
    rows: list[tuple[str, bytes]],
) -> None:
    table_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(table_dir / db_name) as connection:
        connection.execute(f'CREATE TABLE "{table_name}" (Key TEXT, Bytes BLOB)')
        connection.executemany(
            f'INSERT INTO "{table_name}" VALUES (?, ?)',
            rows,
        )


def _memorypack_utf8_string(value: str) -> bytes:
    raw = value.encode("utf8")
    if not raw:
        return (0).to_bytes(4, "little", signed=True)
    payload = bytearray()
    payload.extend((~len(raw)).to_bytes(4, "little", signed=True))
    payload.extend((len(raw)).to_bytes(4, "little", signed=True))
    payload.extend(raw)
    return bytes(payload)


def _memorypack_empty_collection() -> bytes:
    return (0).to_bytes(4, "little", signed=True)


def _skill_visual_payload(name: str, visual_data_key: str) -> bytes:
    payload = bytearray()
    payload.append(8)
    payload.extend(_memorypack_utf8_string(name))
    payload.extend(_memorypack_utf8_string(visual_data_key))
    payload.extend(_memorypack_utf8_string(""))
    payload.extend(_memorypack_empty_collection() * 5)
    return bytes(payload)


def _stage_save_data_payload(version: str = "1.1") -> bytes:
    payload = bytearray()
    payload.append(1)
    payload.extend(_memorypack_utf8_string(version))
    return bytes(payload)


def _logic_effect_payload(level: int, template_id: str) -> bytes:
    payload = bytearray()
    payload.append(17)
    payload.append(2)
    payload.extend(level.to_bytes(4, "little", signed=True))
    payload.extend(_memorypack_utf8_string(template_id))
    return bytes(payload)


def _write_stage_save_data_sidecar(extract_dir: Path) -> None:
    _write_memorypack_formatter_sidecar(
        extract_dir,
        {
            "version": 1,
            "formatters": [
                {
                    "target_type": "MX.Logic.Battles.StageSaveData.StageSaveData",
                    "kind": "object",
                    "object_header": True,
                    "members": [{"name": "Version", "cs_type": "string"}],
                }
            ],
        },
    )


def _write_logic_effect_sidecar(extract_dir: Path) -> None:
    _write_memorypack_formatter_sidecar(
        extract_dir,
        {
            "version": 1,
            "formatters": [
                {
                    "target_type": "MX.GameData.DAO.Battle.LogicEffectDAO",
                    "kind": "union",
                    "tag_type": "byte",
                    "union_tags": {
                        "17": "MX.GameData.DAO.Battle.DamageEffectDAO",
                    },
                },
                {
                    "target_type": "MX.GameData.DAO.Battle.DamageEffectDAO",
                    "kind": "object",
                    "object_header": True,
                    "members": [
                        {"name": "Level", "cs_type": "int"},
                        {"name": "TemplateId", "cs_type": "string"},
                    ],
                },
            ],
        },
    )


def _build_empty_flatbuffer_payload() -> bytes:
    builder = flatbuffers.Builder(0)
    builder.StartObject(0)
    root = builder.EndObject()
    builder.Finish(root)
    return bytes(builder.Output())


def _build_character_excel_table_payload() -> bytes:
    builder = flatbuffers.Builder(0)
    builder.StartObject(0)
    entry = builder.EndObject()
    builder.StartVector(4, 1, 4)
    builder.PrependUOffsetTRelative(entry)
    data_list = builder.EndVector()
    builder.StartObject(1)
    builder.PrependUOffsetTRelativeSlot(0, data_list, 0)
    root = builder.EndObject()
    builder.Finish(root)
    return bytes(builder.Output())


def test_table_extractor_processes_generated_flat_buffer_data_from_directory(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)

    extractor = TableExtractor.from_context(
        context,
        table_profile=_table_profile(context),
    )

    processed = extractor.process_zip_file(
        "Excel.zip",
        "CharacterExcelTable.bytes",
        _build_character_excel_table_payload(),
    )

    assert processed.file_name == "CharacterExcelTable.json"
    assert json.loads(processed.data.decode("utf8")) == [{}]


def test_cn_extract_zip_file_preserves_legacy_ground_archives_as_raw(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "sb_02_desertcity_p01_e.zip", "w") as archive:
        archive.writestr("GroundGridFlat.bytes", b"raw-ground-grid")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir) / "Table"),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("sb_02_desertcity_p01_e.zip")

    output_path = (
        Path(context.extract_dir)
        / "Table"
        / "sb_02_desertcity_p01_e"
        / "GroundGridFlat.bytes"
    )
    assert output_path.read_bytes() == b"raw-ground-grid"
    assert logger.error_messages == []


def test_extract_zip_file_synthesizes_missing_excel_table_wrapper(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_row_only_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    encrypted_payload = xor_with_key(
        "CharacterExcelTable",
        _build_character_excel_table_payload(),
    )
    with ZipFile(table_dir / "Excel.zip", "w") as archive:
        archive.writestr("characterexceltable.bytes", encrypted_payload)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("Excel.zip")

    output_path = Path(context.extract_dir) / "Excel" / "CharacterExcelTable.json"
    assert json.loads(output_path.read_text(encoding="utf8")) == [{}]
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_warns_when_synthetic_excel_table_fallback_fails(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_row_only_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "Excel.zip", "w") as archive:
        archive.writestr("characterexceltable.bytes", b"not-a-flatbuffer")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("Excel.zip")

    assert logger.error_messages == []
    assert any(
        "schema/payload unsupported" in message for message in logger.warn_messages
    )
    assert not any("ExcelDB.db" in message for message in logger.warn_messages)
    assert not (
        Path(context.extract_dir) / "Excel" / "CharacterExcelTable.json"
    ).exists()


def test_extract_zip_file_uses_compact_json_for_large_table_payloads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    encrypted_payload = xor_with_key(
        "CharacterExcelTable",
        _build_character_excel_table_payload(),
    )
    with ZipFile(table_dir / "Excel.zip", "w") as archive:
        archive.writestr("CharacterExcelTable.bytes", encrypted_payload)

    monkeypatch.setattr(TablePayloadCodecAdapter, "COMPACT_JSON_MIN_BYTES", 1)
    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("Excel.zip")

    output_path = Path(context.extract_dir) / "Excel" / "CharacterExcelTable.json"
    assert output_path.read_text(encoding="utf8") == "[{}]"


def test_table_extractor_raises_when_flat_buffer_data_directory_is_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")

    with pytest.raises(
        FileNotFoundError, match="FlatBufferData directory does not exist"
    ):
        TableExtractor.from_context(context, table_profile=_table_profile(context))


def test_extract_db_file_decodes_cn_memorypack_blob_with_formatter_sidecar(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    _create_empty_memorypack_data_package(Path(context.extract_dir) / "MemoryPackData")
    _write_memorypack_formatter_sidecar(
        Path(context.extract_dir),
        {
            "version": 1,
            "formatters": [
                {
                    "target_type": "MX.GameData.DAO.Battle.SkillLogicDAO",
                    "kind": "object",
                    "method_token": "0x06000001",
                    "members": [{"name": "Name", "cs_type": "string"}],
                }
            ],
        },
    )
    table_dir = Path(context.raw_dir) / "Table"
    _create_blob_database(
        table_dir,
        "LevelSkillDataDBSchema.db",
        "Enemy",
        [("AEV_Test", _memorypack_utf8_string("decoded-skill"))],
    )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    assert extractor.extract_db_file("LevelSkillDataDBSchema.db")

    output_path = Path(context.extract_dir) / "LevelSkillDataDBSchema" / "Enemy.json"
    rows = json.loads(output_path.read_text(encoding="utf8"))
    assert rows == [
        {
            "Key": "AEV_Test",
            "Bytes": {
                "__type__": "MX.GameData.DAO.Battle.SkillLogicDAO",
                "Name": "decoded-skill",
            },
        }
    ]
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_db_file_prefers_full_skill_visual_formatter_sidecar(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    _create_empty_memorypack_data_package(Path(context.extract_dir) / "MemoryPackData")
    _write_memorypack_formatter_sidecar(
        Path(context.extract_dir),
        {
            "version": 1,
            "formatters": [
                {
                    "target_type": "MX.AppData.DAO.Battle.SkillVisualDAO",
                    "kind": "object",
                    "object_header": True,
                    "formatter_type": "MX.AppData.DAO.Battle.SkillVisualDAOFormatter",
                    "formatter_token": "0x02003998",
                    "method_token": "0x0601BC7A",
                    "members": [
                        {"name": "name", "cs_type": "string"},
                        {"name": "VisualDataKey", "cs_type": "string"},
                        {"name": "GuidePrefabPath", "cs_type": "string"},
                        {"name": "ActionEffects", "cs_type": "object[]"},
                        {"name": "EntityEffects", "cs_type": "object[]"},
                        {"name": "LogicEffectVisuals", "cs_type": "object[]"},
                        {"name": "BattleItems", "cs_type": "object[]"},
                        {"name": "ParticleEffectDatas", "cs_type": "object[]"},
                    ],
                }
            ],
        },
    )
    table_dir = Path(context.raw_dir) / "Table"
    _create_blob_database(
        table_dir,
        "SkillVisualEffectDataDBSchema.db",
        "Challenge",
        [
            (
                "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio",
                _skill_visual_payload(
                    "Buff_AttackPower_Ally_10s_150_Ratio_SkillVisual01",
                    "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio",
                ),
            )
        ],
    )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    assert extractor.extract_db_file("SkillVisualEffectDataDBSchema.db")

    output_path = (
        Path(context.extract_dir) / "SkillVisualEffectDataDBSchema" / "Challenge.json"
    )
    rows = json.loads(output_path.read_text(encoding="utf8"))
    decoded = rows[0]["Bytes"]
    assert decoded == {
        "__type__": "MX.AppData.DAO.Battle.SkillVisualDAO",
        "name": "Buff_AttackPower_Ally_10s_150_Ratio_SkillVisual01",
        "VisualDataKey": (
            "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio"
        ),
        "GuidePrefabPath": "",
        "ActionEffects": [],
        "EntityEffects": [],
        "LogicEffectVisuals": [],
        "BattleItems": [],
        "ParticleEffectDatas": [],
    }
    assert "__partial_memorypack__" not in decoded
    assert "__payload_sha256__" not in decoded
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_db_file_decodes_logic_effect_blob_with_formatter_sidecar(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    _create_empty_memorypack_data_package(Path(context.extract_dir) / "MemoryPackData")
    _write_logic_effect_sidecar(Path(context.extract_dir))
    table_dir = Path(context.raw_dir) / "Table"
    _create_blob_database(
        table_dir,
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        [("EffectA", _logic_effect_payload(5, "Damage_Test"))],
    )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    assert extractor.extract_db_file("LogicEffectDataDBSchema.db")

    output_path = (
        Path(context.extract_dir) / "LogicEffectDataDBSchema" / "LogicEffect_PC.json"
    )
    rows = json.loads(output_path.read_text(encoding="utf8"))
    assert rows[0]["Bytes"] == {
        "__type__": "MX.GameData.DAO.Battle.DamageEffectDAO",
        "Level": 5,
        "TemplateId": "Damage_Test",
    }
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_db_file_deduplicates_cn_memorypack_fallback_warnings(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    _create_blob_database(
        table_dir,
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        [
            ("EffectA", b"\x01\x02\x03"),
            ("EffectB", b"\x04\x05\x06"),
        ],
    )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    assert extractor.extract_db_file("LogicEffectDataDBSchema.db")

    output_path = (
        Path(context.extract_dir) / "LogicEffectDataDBSchema" / "LogicEffect_PC.json"
    )
    rows = json.loads(output_path.read_text(encoding="utf8"))
    assert rows[0]["Bytes"]["__memorypack_error__"] == (
        "Unexpected end of MemoryPack payload."
    )
    assert rows[0]["Bytes"]["__root_type__"] == "MX.GameData.DAO.Battle.LogicEffectDAO"
    assert rows[0]["Bytes"]["__payload_size__"] == 3
    assert rows[0]["Bytes"]["__payload_head__"] == "010203"
    assert "__payload_sha256__" in rows[0]["Bytes"]
    assert rows[1]["Bytes"]["__memorypack_error__"] == (
        "Unexpected end of MemoryPack payload."
    )
    assert rows[1]["Bytes"]["__root_type__"] == "MX.GameData.DAO.Battle.LogicEffectDAO"
    assert rows[1]["Bytes"]["__payload_size__"] == 3
    assert rows[1]["Bytes"]["__payload_head__"] == "040506"
    assert "__payload_sha256__" in rows[1]["Bytes"]
    assert logger.warn_messages == [
        "Using raw MemoryPack fallback for bytes field Bytes in LogicEffect_PC: "
        "MemoryPack partial decode failed for MX.GameData.DAO.Battle.LogicEffectDAO: "
        "Unexpected end of MemoryPack payload."
    ]
    assert all(
        "FlatBufferData schema is missing" not in message
        for message in logger.warn_messages
    )


def test_jp_table_payload_router_routes_known_dao_blobs_without_partial_fallback() -> (
    None
):
    context = _build_context(Path(".")).with_updates(region="jp")
    router = _table_profile(context).payload_router

    route = router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )

    assert route.codec is TablePayloadCodec.MEMORYPACK
    assert route.root_type == "MX.GameData.DAO.Battle.LogicEffectDAO"
    assert route.allow_partial_memorypack is False


def test_cn_legacy_table_payload_router_routes_known_dao_blobs_with_partial_fallback() -> (
    None
):
    context = _build_context(Path(".")).with_updates(region="cn")
    router = _table_profile(context).payload_router

    route = router.resolve_database_blob(
        "SkillVisualEffectDataDBSchema.db",
        "Challenge",
        "Bytes",
    )

    assert route.codec is TablePayloadCodec.MEMORYPACK
    assert route.root_type == "MX.AppData.DAO.Battle.SkillVisualDAO"
    assert route.allow_partial_memorypack is True


def test_table_payload_router_keeps_excel_and_unknown_blobs_on_flatbuffer_path() -> (
    None
):
    router = FlatBufferTablePayloadRouter()

    assert (
        router.resolve_database_blob(
            "ExcelDB.db",
            "CharacterDBSchema",
            "Bytes",
        ).codec
        is TablePayloadCodec.FLATBUFFER
    )
    assert (
        router.resolve_database_blob(
            "Unknown.db",
            "Enemy",
            "Bytes",
        ).codec
        is TablePayloadCodec.FLATBUFFER
    )


def test_extract_db_file_partially_decodes_skill_visual_blob_without_formatter_sidecar(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    _create_blob_database(
        table_dir,
        "SkillVisualEffectDataDBSchema.db",
        "Challenge",
        [
            (
                "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio",
                _skill_visual_payload(
                    "Buff_AttackPower_Ally_10s_150_Ratio_SkillVisual01",
                    "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio",
                ),
            )
        ],
    )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    assert extractor.extract_db_file("SkillVisualEffectDataDBSchema.db")

    output_path = (
        Path(context.extract_dir) / "SkillVisualEffectDataDBSchema" / "Challenge.json"
    )
    rows = json.loads(output_path.read_text(encoding="utf8"))
    decoded = rows[0]["Bytes"]
    assert decoded["__type__"] == "MX.AppData.DAO.Battle.SkillVisualDAO"
    assert decoded["name"] == "Buff_AttackPower_Ally_10s_150_Ratio_SkillVisual01"
    assert decoded["VisualDataKey"] == (
        "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio"
    )
    assert decoded["GuidePrefabPath"] == ""
    assert decoded["__payload_size__"] == len(
        _skill_visual_payload(
            "Buff_AttackPower_Ally_10s_150_Ratio_SkillVisual01",
            "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio",
        )
    )
    assert "__payload_sha256__" in decoded
    assert "__memorypack_error__" not in decoded
    assert logger.warn_messages == []


def test_extract_db_file_keeps_partial_memorypack_decode_out_of_warning_log(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="cn")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    partial_payload = (
        _skill_visual_payload(
            "Buff_AttackPower_Ally_10s_150_Ratio_SkillVisual01",
            "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio",
        )
        + b"\x01"
    )
    _create_blob_database(
        table_dir,
        "SkillVisualEffectDataDBSchema.db",
        "Challenge",
        [
            (
                "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio",
                partial_payload,
            )
        ],
    )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        context=context,
        table_profile=_table_profile(context),
    )

    assert extractor.extract_db_file("SkillVisualEffectDataDBSchema.db")

    output_path = (
        Path(context.extract_dir) / "SkillVisualEffectDataDBSchema" / "Challenge.json"
    )
    rows = json.loads(output_path.read_text(encoding="utf8"))
    decoded = rows[0]["Bytes"]
    assert decoded["__partial_memorypack__"] is True
    assert decoded["__remaining_size__"] == 1
    assert logger.warn_messages == []
    assert logger.error_messages == []


@pytest.mark.parametrize(
    ("error_type", "expected_fragment"),
    [
        (UnsupportedSchemaError, "unsupported schema"),
        (TableDecryptError, "decrypt failed"),
        (FlatBufferExportError, "flatbuffer export failed"),
    ],
)
def test_extract_zip_file_warns_with_explicit_processing_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error_type: type[Exception],
    expected_fragment: str,
) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    zip_path = table_dir / "Excel.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("CharacterExcelTable.bytes", b"payload")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    def fail_processing(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        raise error_type(expected_fragment)

    monkeypatch.setattr(extractor, "process_zip_file", fail_processing)

    extractor.extract_zip_file("Excel.zip")

    assert any(expected_fragment in message for message in logger.warn_messages)
    assert logger.warn_messages[-1] == "Skipped 1 entries while extracting Excel.zip."
    assert not (Path(context.extract_dir) / "Excel").exists()


def test_extract_zip_file_summarizes_jp_stale_excel_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "Excel.zip", "w") as archive:
        archive.writestr("minigamecardexceltable.bytes", b"stale")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    def fail_processing(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        raise MalformedTablePayloadError("very long payload trace")

    monkeypatch.setattr(extractor, "process_zip_file", fail_processing)

    extractor.extract_zip_file("Excel.zip")

    assert any(
        "stale JP Excel.zip entries" in message for message in logger.warn_messages
    )
    assert not any(
        "very long payload trace" in message for message in logger.warn_messages
    )
    assert logger.warn_messages[-1] == "Skipped 1 entries while extracting Excel.zip."


def test_extract_zip_file_writes_excel_artifact(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "Excel.zip", "w") as archive:
        archive.writestr(
            "CharacterExcelTable.bytes", _build_character_excel_table_payload()
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("Excel.zip")

    output_path = Path(context.extract_dir) / "Excel" / "CharacterExcelTable.json"
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf8")) == [{}]
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_gl_extract_table_decodes_catalog_and_preserves_hash(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    _create_empty_memorypack_data_package(Path(context.extract_dir) / "MemoryPackData")
    _write_memorypack_formatter_sidecar(
        Path(context.extract_dir),
        {
            "version": 1,
            "formatters": [
                {
                    "target_type": "TableCatalog",
                    "kind": "object",
                    "object_header": True,
                    "members": [],
                }
            ],
        },
    )
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / "TableCatalog.bytes").write_bytes(b"\x00")
    (table_dir / "TableCatalog.hash").write_bytes(b"catalog-v1")

    logger = RecordingLogger()
    output_dir = Path(context.extract_dir) / "Table"
    extractor = TableExtractor(
        str(table_dir),
        str(output_dir),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_table("TableCatalog.bytes")
    extractor.extract_table("TableCatalog.hash")

    assert json.loads(
        (output_dir / "TableCatalog.json").read_text(encoding="utf8")
    ) == {"__type__": "TableCatalog"}
    assert (output_dir / "TableCatalog.hash").read_bytes() == b"catalog-v1"
    assert logger.warn_messages == []
    assert logger.error_messages == []


@pytest.mark.parametrize(
    "entry_name",
    [
        "MiniGameCardExcelTable.bytes",
        "MiniGameRoadPuzzleExcelTable.bytes",
        "MiniGameShootingExcelTable.bytes",
    ],
)
def test_gl_extract_zip_file_preserves_known_minigame_payloads(
    tmp_path: Path,
    entry_name: str,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "Excel.zip", "w") as archive:
        archive.writestr(entry_name, b"raw-minigame")

    logger = RecordingLogger()
    output_dir = Path(context.extract_dir) / "Table"
    extractor = TableExtractor(
        str(table_dir),
        str(output_dir),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("Excel.zip")

    assert (output_dir / "Excel" / entry_name).read_bytes() == b"raw-minigame"
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_gl_extract_zip_file_preserves_test_archive_as_raw(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "MovingAreaTestMap.zip", "w") as archive:
        archive.writestr("movingareatestmap.bytes", b"raw-test-map")

    logger = RecordingLogger()
    output_dir = Path(context.extract_dir) / "Table"
    extractor = TableExtractor(
        str(table_dir),
        str(output_dir),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("MovingAreaTestMap.zip")

    assert (
        output_dir / "MovingAreaTestMap" / "movingareatestmap.bytes"
    ).read_bytes() == b"raw-test-map"
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_reports_entry_progress(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "Battle.zip", "w") as archive:
        archive.writestr("first.bin", b"first")
        archive.writestr("second.bin", b"second")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )
    progress_updates: list[str] = []

    extractor.extract_zip_file("Battle.zip", progress_callback=progress_updates.append)

    assert progress_updates == ["1/2 entries", "2/2 entries"]
    assert logger.warn_messages == []
    assert logger.error_messages == []


@pytest.mark.parametrize(
    ("archive_name", "entry_name", "payload"),
    [
        ("Battle.zip", "obstacledata.bin", b"\x9d\x01\x00\x00raw-obstacle"),
        ("CN.zip", "sensitivewords.txt", b"blocked\nwords\n"),
    ],
)
def test_extract_zip_file_writes_raw_sidecar_entries(
    tmp_path: Path,
    archive_name: str,
    entry_name: str,
    payload: bytes,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / archive_name, "w") as archive:
        archive.writestr(entry_name, payload)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(archive_name)

    output_path = (
        Path(context.extract_dir) / archive_name.removesuffix(".zip") / entry_name
    )
    assert output_path.read_bytes() == payload
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_ground_grid_patch_artifact(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr(
            "sb_02_trainroof_p01_d.bytes", _build_empty_flatbuffer_payload()
        )

    with ZipFile(table_dir / "TablePatchPack_GroundGrid_11.zip", "w") as outer_archive:
        outer_archive.writestr(
            "sb_02_trainroof_p01_d.zip",
            inner_zip_buffer.getvalue(),
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("TablePatchPack_GroundGrid_11.zip")

    output_path = (
        Path(context.extract_dir)
        / "TablePatchPack_GroundGrid_11"
        / "sb_02_trainroof_p01_d"
        / "GroundGridFlat.json"
    )
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf8")) == {}
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_uses_catalog_case_for_ground_grid_password(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr(
            "sb_01_redwinterstreet_p01_d_arena.bytes",
            _build_empty_flatbuffer_payload(),
        )

    with ZipFile(table_dir / "TablePatchPack_GroundGrid_6.zip", "w") as outer_archive:
        outer_archive.writestr(
            "sb_01_redwinterstreet_p01_d_arena.zip",
            inner_zip_buffer.getvalue(),
        )

    original_read = ZipFile.read
    expected_password = zip_password("SB_01_RedWinterStreet_P01_D_Arena.zip")

    def assert_inner_password(self, name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "sb_01_redwinterstreet_p01_d_arena.bytes":
            assert self.pwd == expected_password
        return original_read(self, name, *args, **kwargs)

    monkeypatch.setattr(ZipFile, "read", assert_inner_password)
    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(
        "TablePatchPack_GroundGrid_6.zip",
        metadata={"includes": ["SB_01_RedWinterStreet_P01_D_Arena.zip"]},
    )

    output_path = (
        Path(context.extract_dir)
        / "TablePatchPack_GroundGrid_6"
        / "sb_01_redwinterstreet_p01_d_arena"
        / "GroundGridFlat.json"
    )
    assert json.loads(output_path.read_text(encoding="utf8")) == {}
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_preserves_bad_password_ground_grid_inner_zip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr(
            "bad_grid.bytes",
            _build_empty_flatbuffer_payload(),
        )
    inner_zip_data = inner_zip_buffer.getvalue()

    with ZipFile(table_dir / "TablePatchPack_GroundGrid_11.zip", "w") as outer_archive:
        outer_archive.writestr("bad_grid.zip", inner_zip_data)

    original_read = ZipFile.read

    def bad_password_read(self, name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "bad_grid.bytes":
            raise RuntimeError("Bad password for file 'bad_grid.bytes'")
        return original_read(self, name, *args, **kwargs)

    monkeypatch.setattr(ZipFile, "read", bad_password_read)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("TablePatchPack_GroundGrid_11.zip")

    encrypted_output = (
        Path(context.extract_dir)
        / "TablePatchPack_GroundGrid_11"
        / "_encrypted"
        / "bad_grid.zip"
    )
    assert encrypted_output.read_bytes() == inner_zip_data
    assert any("_encrypted" in message for message in logger.warn_messages)
    assert logger.error_messages == []


def test_extract_zip_file_reports_ground_grid_entry_start_progress(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr(
            "sb_02_trainroof_p01_d.bytes",
            _build_empty_flatbuffer_payload(),
        )

    with ZipFile(table_dir / "TablePatchPack_GroundGrid_11.zip", "w") as outer_archive:
        outer_archive.writestr(
            "sb_02_trainroof_p01_d.zip",
            inner_zip_buffer.getvalue(),
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )
    progress_updates: list[str] = []

    extractor.extract_zip_file(
        "TablePatchPack_GroundGrid_11.zip",
        progress_callback=progress_updates.append,
    )

    assert progress_updates[0] == "1/1 entries: sb_02_trainroof_p01_d.zip"
    assert progress_updates[-1] == "1/1 entries"


def test_extract_db_file_reports_table_progress(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(table_dir / "Simple.db") as connection:
        connection.execute('CREATE TABLE "First" (Key TEXT)')
        connection.execute('CREATE TABLE "Second" (Key TEXT)')

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
    )
    progress_updates: list[str] = []

    assert extractor.extract_db_file(
        "Simple.db",
        progress_callback=progress_updates.append,
    )

    assert progress_updates == ["1/2 tables", "2/2 tables"]
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_ground_stage_semantic_json(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    _write_stage_save_data_sidecar(Path(context.extract_dir))
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr(
            "1052103_02_s3_02_excavation_p02_n.bytes", _stage_save_data_payload()
        )

    with ZipFile(table_dir / "TablePatchPack_GroundStage_1.zip", "w") as outer_archive:
        outer_archive.writestr(
            "1052103_02_s3_02_excavation_p02_n.zip",
            inner_zip_buffer.getvalue(),
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
    )

    extractor.extract_zip_file("TablePatchPack_GroundStage_1.zip")

    output_path = (
        Path(context.extract_dir)
        / "TablePatchPack_GroundStage_1"
        / "1052103_02_s3_02_excavation_p02_n"
        / "StageSaveData.json"
    )
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf8")) == {
        "__type__": "MX.Logic.Battles.StageSaveData.StageSaveData",
        "Version": "1.1",
    }
    assert logger.warn_messages == []
    assert logger.error_messages == []
    assert logger.info_messages == []


def test_extract_zip_file_uses_catalog_case_for_ground_stage_password(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    _write_stage_save_data_sidecar(Path(context.extract_dir))
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr("en0010_veryhard.bytes", _stage_save_data_payload())

    with ZipFile(table_dir / "TablePatchPack_GroundStage_1.zip", "w") as outer_archive:
        outer_archive.writestr("en0010_veryhard.zip", inner_zip_buffer.getvalue())

    original_read = ZipFile.read
    expected_password = zip_password("EN0010_VeryHard.zip")

    def assert_inner_password(self, name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "en0010_veryhard.bytes":
            assert self.pwd == expected_password
        return original_read(self, name, *args, **kwargs)

    monkeypatch.setattr(ZipFile, "read", assert_inner_password)
    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(
        "TablePatchPack_GroundStage_1.zip",
        metadata={"includes": ["EN0010_VeryHard.zip"]},
    )

    output_path = (
        Path(context.extract_dir)
        / "TablePatchPack_GroundStage_1"
        / "en0010_veryhard"
        / "StageSaveData.json"
    )
    assert json.loads(output_path.read_text(encoding="utf8"))["Version"] == "1.1"
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_jp_ground_node_layer_patch_artifact(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr(
            "combattest_dtest00_nodelayer.bytes",
            _build_empty_flatbuffer_payload(),
        )
    with ZipFile(
        table_dir / "TablePatchPack_GroundNodeLayer_1.zip", "w"
    ) as outer_archive:
        outer_archive.writestr(
            "combattest_dtest00_nodelayer.zip",
            inner_zip_buffer.getvalue(),
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("TablePatchPack_GroundNodeLayer_1.zip")

    output_path = (
        Path(context.extract_dir)
        / "TablePatchPack_GroundNodeLayer_1"
        / "combattest_dtest00_nodelayer"
        / "GroundNodeLayerFlat.json"
    )
    assert json.loads(output_path.read_text(encoding="utf8")) == {}
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_gl_battle_stage_artifact(tmp_path: Path) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    with ZipFile(table_dir / "sb_02_desertcity_p01_e.zip", "w") as archive:
        archive.writestr(
            "sb_02_desertcity_p01_e.bytes", _build_empty_flatbuffer_payload()
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("sb_02_desertcity_p01_e.zip")

    output_path = (
        Path(context.extract_dir) / "sb_02_desertcity_p01_e" / "GroundGridFlat.json"
    )
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf8")) == {}
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_gl_battle_stage_nodelayer_artifact(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    with ZipFile(table_dir / "sb_02_desertcity_p01_e_nodelayer.zip", "w") as archive:
        archive.writestr(
            "sb_02_desertcity_p01_e_nodelayer.bytes", _build_empty_flatbuffer_payload()
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file("sb_02_desertcity_p01_e_nodelayer.zip")

    output_path = (
        Path(context.extract_dir)
        / "sb_02_desertcity_p01_e_nodelayer"
        / "GroundNodeLayerFlat.json"
    )
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf8")) == {}
    assert logger.warn_messages == []
    assert logger.error_messages == []


@pytest.mark.parametrize(
    ("archive_name", "entry_name", "payload", "expected_file_name", "expected_json"),
    [
        (
            "rb_03_hod_p01.zip",
            "rb_03_hod_p01.bytes",
            _build_empty_flatbuffer_payload(),
            "GroundGridFlat.json",
            {},
        ),
        (
            "rb_03_hieronymus_p01_d_scenario.zip",
            "rb_03_hieronymus_p01_d_scenario.bytes",
            _build_empty_flatbuffer_payload(),
            "GroundGridFlat.json",
            {},
        ),
        (
            "rd_02_EN0011_p01_d_01_nodelayer.zip",
            "rd_02_en0011_p01_d_01_nodelayer.bytes",
            _build_empty_flatbuffer_payload(),
            "GroundNodeLayerFlat.json",
            {},
        ),
        (
            "db_02_beachstage_01_nodelayer.zip",
            "db_02_beachstage_01_nodelayer.bytes",
            _build_empty_flatbuffer_payload(),
            "GroundNodeLayerFlat.json",
            {},
        ),
    ],
)
def test_extract_zip_file_writes_additional_gl_ground_artifacts(
    tmp_path: Path,
    archive_name: str,
    entry_name: str,
    payload: bytes,
    expected_file_name: str,
    expected_json: dict[str, str],
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    with ZipFile(table_dir / archive_name, "w") as archive:
        archive.writestr(entry_name, payload)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(archive_name)

    output_path = (
        Path(context.extract_dir)
        / archive_name.removesuffix(".zip")
        / expected_file_name
    )
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf8")) == expected_json
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_c_sb_hyakkiyakomatsuri_raw_artifact(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    archive_name = "C_sb_01_hyakkiyakomatsuri_p02_Little.zip"
    entry_name = "c_sb_01_hyakkiyakomatsuri_p02_little.bytes"
    payload = b"\x06\xfc\xff\xffbattle"
    with ZipFile(table_dir / archive_name, "w") as archive:
        archive.writestr(entry_name, payload)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(archive_name)

    output_path = (
        Path(context.extract_dir) / archive_name.removesuffix(".zip") / entry_name
    )
    assert output_path.is_file()
    assert output_path.read_bytes() == payload
    assert logger.warn_messages == []
    assert logger.error_messages == []
    assert logger.info_messages == []


def test_extract_zip_file_writes_gl_numeric_stage_raw_payloads(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    archive_name = "1041104_03_s3_boss_02_desertcity_p01_d.zip"
    entry_name = "1041104_03_s3_boss_02_desertcity_p01_d.bytes"
    payload = b"\x06\xfc\xff\xffbattle"
    with ZipFile(table_dir / archive_name, "w") as archive:
        archive.writestr(entry_name, payload)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(archive_name)

    output_path = (
        Path(context.extract_dir) / archive_name.removesuffix(".zip") / entry_name
    )
    assert output_path.is_file()
    assert output_path.read_bytes() == payload
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_gl_eliminate_raid_raw_payloads(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    archive_name = (
        "6062106_eliminateRaid_perorozilla_outdoor_light_insane_start2phase.zip"
    )
    entry_name = (
        "6062106_eliminateraid_perorozilla_outdoor_light_insane_start2phase.bytes"
    )
    payload = b"\x06\xfc\xff\xffbattle"
    with ZipFile(table_dir / archive_name, "w") as archive:
        archive.writestr(entry_name, payload)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(archive_name)

    output_path = (
        Path(context.extract_dir) / archive_name.removesuffix(".zip") / entry_name
    )
    assert output_path.is_file()
    assert output_path.read_bytes() == payload
    assert logger.warn_messages == []
    assert logger.error_messages == []
    assert logger.info_messages == []


def test_extract_zip_file_writes_gl_enemy_boss_script_raw_payloads(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    archive_name = "EN0006_Eliminate_LightArmor_Hard.zip"
    entry_name = "en0006_eliminate_lightarmor_hard.bytes"
    payload = b"\x06\xfc\xff\xffbattle"
    with ZipFile(table_dir / archive_name, "w") as archive:
        archive.writestr(entry_name, payload)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(archive_name)

    output_path = (
        Path(context.extract_dir) / archive_name.removesuffix(".zip") / entry_name
    )
    assert output_path.is_file()
    assert output_path.read_bytes() == payload
    assert logger.warn_messages == []
    assert logger.error_messages == []
    assert logger.info_messages == []


def test_extract_zip_file_writes_gl_script_test_raw_payloads(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    archive_name = "DamageTest_Street_LightArmor.zip"
    entry_name = "damagetest_street_lightarmor.bytes"
    payload = b"\x06\xfc\xff\xffbattle"
    with ZipFile(table_dir / archive_name, "w") as archive:
        archive.writestr(entry_name, payload)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    extractor.extract_zip_file(archive_name)

    output_path = (
        Path(context.extract_dir) / archive_name.removesuffix(".zip") / entry_name
    )
    assert output_path.is_file()
    assert output_path.read_bytes() == payload
    assert logger.warn_messages == []
    assert logger.error_messages == []
    assert logger.info_messages == []


def test_extract_zip_file_writes_mgs_logic_ground_mixed_artifacts(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path).with_updates(region="gl")
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    with ZipFile(table_dir / "MGSLogicGroundData.zip", "w") as archive:
        archive.writestr("logicground_free.bytes", _build_empty_flatbuffer_payload())
        archive.writestr("logicground_hard.bytes", b"\xff\x00bad-grid")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
        table_profile=_table_profile(context),
    )

    original_process_zip_file = extractor.process_zip_file

    def fake_process_zip_file(
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact:
        if file_data == b"\xff\x00bad-grid":
            raise UnsupportedSchemaError("grid parser failed")
        return original_process_zip_file(
            archive_name,
            file_name,
            file_data,
            detect_type=detect_type,
        )

    extractor.process_zip_file = fake_process_zip_file  # type: ignore[method-assign]

    extractor.extract_zip_file("MGSLogicGroundData.zip")

    grid_output = (
        Path(context.extract_dir) / "MGSLogicGroundData" / "GroundGridFlat.json"
    )
    raw_output = (
        Path(context.extract_dir) / "MGSLogicGroundData" / "logicground_hard.bytes"
    )
    assert grid_output.is_file()
    assert json.loads(grid_output.read_text(encoding="utf8")) == {}
    assert raw_output.is_file()
    assert raw_output.read_bytes() == b"\xff\x00bad-grid"
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_skips_ground_stage_entries_with_zlib_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr("broken_stage.bytes", b"\xff\x00stage")

    with ZipFile(table_dir / "TablePatchPack_GroundStage_1.zip", "w") as outer_archive:
        outer_archive.writestr("broken_stage.zip", inner_zip_buffer.getvalue())

    original_read = ZipFile.read

    def flaky_read(self, name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "broken_stage.bytes":
            raise zlib.error("invalid stored block lengths")
        return original_read(self, name, *args, **kwargs)

    monkeypatch.setattr(ZipFile, "read", flaky_read)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
    )

    extractor.extract_zip_file("TablePatchPack_GroundStage_1.zip")

    assert logger.error_messages == []
    assert any(
        "invalid stored block lengths" in message for message in logger.warn_messages
    )
    assert logger.warn_messages[-1] == (
        "Skipped 1 entries while extracting TablePatchPack_GroundStage_1.zip."
    )
    assert not (Path(context.extract_dir) / "TablePatchPack_GroundStage_1").exists()


def test_extract_zip_file_exports_rhythm_beatmap_as_raw_bytes(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "RhythmBeatmapData.zip", "w") as archive:
        archive.writestr("8040101_example.bytes", b"\xff\x00beatmap")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
    )

    extractor.extract_zip_file("RhythmBeatmapData.zip")

    assert logger.info_messages == [
        "Extracted raw rhythm beatmap payloads from RhythmBeatmapData.zip; "
        "semantic parser is not implemented yet."
    ]
    assert logger.warn_messages == []
    assert logger.error_messages == []
    assert (
        Path(context.extract_dir) / "RhythmBeatmapData" / "8040101_example.bytes"
    ).read_bytes() == b"\xff\x00beatmap"


def test_extract_raw_zip_file_reports_entry_progress(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    _create_flat_buffer_data_package(flatbuffer_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "RhythmBeatmapData.zip", "w") as archive:
        archive.writestr("first.bytes", b"first")
        archive.writestr("second.bytes", b"second")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flatbuffer_data_dir),
        logger=logger,
    )
    progress_updates: list[str] = []

    extractor.extract_zip_file(
        "RhythmBeatmapData.zip",
        progress_callback=progress_updates.append,
    )

    assert progress_updates == ["1/2 entries", "2/2 entries"]
