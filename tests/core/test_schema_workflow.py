from __future__ import annotations

from pathlib import Path

from ba_downloader.infrastructure.schema.flatbuffer.generator import (
    CompileFlatBufferToPython,
)
from ba_downloader.infrastructure.schema.flatbuffer.parser import FlatBufferCSParser
from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow


def test_character_index_schema_selects_all_enrichment_targets_and_dependencies(
    tmp_path: Path,
) -> None:
    dump_path = tmp_path / "dump.cs"
    dump_path.write_text(_minimal_dump(), encoding="utf8")
    parser = FlatBufferCSParser(str(dump_path))

    selected_types, selected_enums = SchemaWorkflow._select_flatbuffer_closure(
        parser.parse_types(),
        parser.parse_enums(),
        SchemaWorkflow.CHARACTER_INDEX_TARGET_TYPES,
    )

    names = {descriptor.name for descriptor in selected_types}
    assert set(SchemaWorkflow.CHARACTER_INDEX_TARGET_TYPES) <= names
    assert "GachaText" in names
    assert {enum.name for enum in selected_enums} == {"LanguageKind"}
    output = tmp_path / "generated"
    CompileFlatBufferToPython(
        selected_types,
        str(output),
        selected_enums,
    ).create_schema_files()
    for source in output.glob("*.py"):
        compile(source.read_text(encoding="utf8"), str(source), "exec")


def _minimal_dump() -> str:
    targets = [
        "CharacterExcel",
        "CostumeExcel",
        "LocalizeCharProfileExcel",
        "ScenarioCharacterNameExcel",
        "ShopRecruitExcel",
    ]
    blocks = [_struct(name, index + 1, "") for index, name in enumerate(targets)]
    blocks.append(
        _struct(
            "LocalizeGachaShopExcel",
            10,
            "    public GachaText Text { get; set; } // Token: 0x06000001\n"
            "    public LanguageKind Language { get; set; } // Token: 0x06000002",
        )
    )
    blocks.append(_struct("GachaText", 11, ""))
    blocks.append(
        "// Namespace: Game\n"
        "public enum LanguageKind // TypeDefIndex: 12, Token: 0x0200000C\n"
        "{\n"
        "    public int value__; // 0x0\n"
        "    public const LanguageKind Japanese = 0; // Token: 0x04000001\n"
        "}\n"
    )
    return "\n".join(blocks)


def _struct(name: str, index: int, body: str) -> str:
    return (
        "// Namespace: Game\n"
        f"public struct {name} : FlatBuffers.IFlatbufferObject "
        f"// TypeDefIndex: {index}, Token: 0x{index:08X}\n"
        "{\n"
        f"{body}\n"
        "}\n"
    )
