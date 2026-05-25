from __future__ import annotations

import py_compile
import sys
from dataclasses import is_dataclass
from enum import IntEnum
from importlib import util
from pathlib import Path
from typing import Annotated, Any, get_args, get_origin, get_type_hints

import flatbuffers
import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.schema.flatbuffer import (
    reader as flatbuffer_reader_module,
)
from ba_downloader.infrastructure.schema.flatbuffer.descriptors import FlatBufferField
from ba_downloader.infrastructure.schema.flatbuffer.generator import (
    CompileFlatBufferToPython,
)
from ba_downloader.infrastructure.schema.flatbuffer.parser import FlatBufferCSParser
from ba_downloader.infrastructure.schema.flatbuffer.reader import FlatBufferReader
from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow
from ba_downloader.shared.crypto.encryption import convert_int, create_key


class DummyHttpClient:
    def close(self) -> None:
        return None


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
        threads=1,
        version="",
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


def _sample_dump_cs() -> str:
    return """// Namespace: FlatData
public enum AttackType // TypeDefIndex: 1, Token: 0x02000001
{
    // Fields
    public System.Int32 value__; // 0x0 Token: 0x04000001
    public const FlatData.AttackType Normal = 0; // Token: 0x04000002
    public const FlatData.AttackType Special = 7; // Token: 0x04000003
}

// Namespace: FlatData
public enum ProductionStep // TypeDefIndex: 2 Token: 0x02000002
{
    // Fields
    public System.Int32 value__; // 0x0 Token: 0x04000004
    public static const FlatData.ProductionStep ToDo; // 0x0 Token: 0x04000005
    public static const FlatData.ProductionStep Doing; // 0x0 Token: 0x04000006
}

// Namespace: FlatData
public struct SampleEntry : FlatBuffers.IFlatbufferObject // TypeDefIndex: 3 Token: 0x02000003
{
    public System.Single X { get; } // Token: 0x17000001
    public FlatData.AttackType AttackType { get; } // Token: 0x17000002
    public string Name { get; } // Token: 0x17000003
}

// Namespace: FlatData
public struct SampleTable : FlatBuffers.IFlatbufferObject // TypeDefIndex: 4 Token: 0x02000004
{
    public System.Nullable`1<FlatData.SampleEntry> OptionalEntry { get; } // Token: 0x17000004
    public FlatBuffers.Offset`1<FlatData.SampleEntry> DirectEntry { get; } // Token: 0x17000005
    public System.Int32 DataListLength { get; } // Token: 0x17000006
    public System.Nullable`1<FlatData.SampleEntry> DataList(System.Int32 j) { }
}

// Namespace: MX.AssetBundles
public class TableBundle : MemoryPack.IMemoryPackable`1<TableBundle>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 5 Token: 0x02000005
{
    // Fields
    private string _Name_k__BackingField; // Token: 0x04000007
    // Properties
    public string Name { get; set; } // Token: 0x17000007
    // Methods
    public static System.Void Serialize(MemoryPack.MemoryPackWriter writer, TableBundle value) { }
    public static System.Void Deserialize(MemoryPack.MemoryPackReader reader, TableBundle value) { }
}
"""


def _cn_recovered_flatbuffer_dump_cs() -> str:
    return """// Namespace: FlatData
public struct AniEventData : FlatBuffers.IFlatbufferObject // TypeDefIndex: 10 Token: 0x0200000A
{
    public System.Int32 Frame { get; } // Token: 0x17000010
}

// Namespace: FlatData
public struct AniStateData : FlatBuffers.IFlatbufferObject // TypeDefIndex: 11 Token: 0x0200000B
{
    public System.Int32 EventsLength { get; } // Token: 0x17000011
    public System.Nullable`1<FlatData.AniEventData> Events(System.Int32 j) { }
}

// Namespace: FlatData
public struct AnimatorData : FlatBuffers.IFlatbufferObject // TypeDefIndex: 12 Token: 0x0200000C
{
    public System.Int32 DataListLength { get; } // Token: 0x17000012
    public System.Nullable`1<FlatData.AniStateData> DataList(System.Int32 j) { }
}

// Namespace: FlatData
public struct BlendInfo : FlatBuffers.IFlatbufferObject // TypeDefIndex: 13 Token: 0x0200000D
{
    public System.Single Weight { get; } // Token: 0x17000013
}

// Namespace: FlatData
public struct BlendData : FlatBuffers.IFlatbufferObject // TypeDefIndex: 14 Token: 0x0200000E
{
    public System.Int32 InfoListLength { get; } // Token: 0x17000014
    public System.Nullable`1<FlatData.BlendInfo> InfoList(System.Int32 j) { }
}

// Namespace: FlatData
public struct AnimationBlendTable : FlatBuffers.IFlatbufferObject // TypeDefIndex: 15 Token: 0x0200000F
{
    public System.Int32 DataListLength { get; } // Token: 0x17000015
    public System.Nullable`1<FlatData.BlendData> DataList(System.Int32 j) { }
}

// Namespace: FlatData
public struct Position : FlatBuffers.IFlatbufferObject // TypeDefIndex: 16 Token: 0x02000010
{
    public System.Single X { get; } // Token: 0x17000016
}

// Namespace: FlatData
public struct Motion : FlatBuffers.IFlatbufferObject // TypeDefIndex: 17 Token: 0x02000011
{
    public System.Int32 PositionsLength { get; } // Token: 0x17000017
    public System.Nullable`1<FlatData.Position> Positions(System.Int32 j) { }
}

// Namespace: FlatData
public struct Form : FlatBuffers.IFlatbufferObject // TypeDefIndex: 18 Token: 0x02000012
{
    public System.Nullable`1<FlatData.Motion> PublicSkill { get; } // Token: 0x17000018
}

// Namespace: FlatData
public struct MoveEnd : FlatBuffers.IFlatbufferObject // TypeDefIndex: 19 Token: 0x02000013
{
    public System.Nullable`1<FlatData.Motion> Normal { get; } // Token: 0x17000019
}

// Namespace: FlatData
public struct RootMotionFlat : FlatBuffers.IFlatbufferObject // TypeDefIndex: 20 Token: 0x02000014
{
    public System.Int32 FormsLength { get; } // Token: 0x1700001A
    public System.Nullable`1<FlatData.Form> Forms(System.Int32 j) { }
    public System.Int32 ExSkillsLength { get; } // Token: 0x1700001B
    public System.Nullable`1<FlatData.Motion> ExSkills(System.Int32 j) { }
    public System.Nullable`1<FlatData.Motion> MoveLeft { get; } // Token: 0x1700001C
    public System.Nullable`1<FlatData.Motion> MoveRight { get; } // Token: 0x1700001D
}

// Namespace: FlatData
public struct PropVector3 : FlatBuffers.IFlatbufferObject // TypeDefIndex: 21 Token: 0x02000015
{
    public System.Single X { get; } // Token: 0x1700001E
}

// Namespace: FlatData
public struct PropMotion : FlatBuffers.IFlatbufferObject // TypeDefIndex: 22 Token: 0x02000016
{
    public System.Int32 PositionsLength { get; } // Token: 0x1700001F
    public System.Nullable`1<FlatData.PropVector3> Positions(System.Int32 j) { }
    public System.Int32 RotationsLength { get; } // Token: 0x17000020
    public System.Nullable`1<FlatData.PropVector3> Rotations(System.Int32 j) { }
}

// Namespace: FlatData
public struct PropRootMotionFlat : FlatBuffers.IFlatbufferObject // TypeDefIndex: 23 Token: 0x02000017
{
    public System.Int32 RootMotionsLength { get; } // Token: 0x17000021
    public System.Nullable`1<FlatData.PropMotion> RootMotions(System.Int32 j) { }
}

// Namespace: -
public struct GroundVector3 : FlatBuffers.IFlatbufferObject // TypeDefIndex: 24 Token: 0x02000018
{
    public System.Single X { get; } // Token: 0x17000022
}

// Namespace: FlatData
public struct GroundNodeFlat : FlatBuffers.IFlatbufferObject // TypeDefIndex: 25 Token: 0x02000019
{
    public System.Nullable`1<GroundVector3> Position { get; } // Token: 0x17000023
}

// Namespace: FlatData
public struct GroundGridFlat : FlatBuffers.IFlatbufferObject // TypeDefIndex: 26 Token: 0x0200001A
{
    public System.Int32 NodesLength { get; } // Token: 0x17000024
    public System.Nullable`1<FlatData.GroundNodeFlat> Nodes(System.Int32 j) { }
}
"""


def _write_dump(tmp_path: Path, content: str) -> Path:
    dump_path = tmp_path / "dump.cs"
    dump_path.write_text(content, encoding="utf8")
    return dump_path


def _load_generated_module(package_dir: Path, module_name: str) -> Any:
    package_name = f"generated_flatbuffer_{abs(hash(str(package_dir)))}"
    if package_name not in sys.modules:
        package_spec = util.spec_from_file_location(
            package_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
        assert package_spec is not None and package_spec.loader is not None
        package = util.module_from_spec(package_spec)
        sys.modules[package_name] = package
        package_spec.loader.exec_module(package)

    spec = util.spec_from_file_location(
        f"{package_name}.{module_name}",
        package_dir / f"{module_name}.py",
    )
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_sample_entry(builder: flatbuffers.Builder, name: str, attack_type: int) -> int:
    name_offset = builder.CreateString(name)
    builder.StartObject(3)
    builder.PrependUOffsetTRelativeSlot(2, name_offset, 0)
    builder.PrependInt32Slot(1, attack_type, 0)
    builder.PrependFloat32Slot(0, 1.5, 0)
    return builder.EndObject()


def _build_sample_table_payload() -> bytes:
    builder = flatbuffers.Builder(0)
    first = _build_sample_entry(builder, "First", 7)
    second = _build_sample_entry(builder, "Second", 0)
    builder.StartVector(4, 2, 4)
    builder.PrependUOffsetTRelative(second)
    builder.PrependUOffsetTRelative(first)
    data_list = builder.EndVector()
    direct_entry = _build_sample_entry(builder, "Direct", 7)
    builder.StartObject(3)
    builder.PrependUOffsetTRelativeSlot(2, data_list, 0)
    builder.PrependUOffsetTRelativeSlot(1, direct_entry, 0)
    root = builder.EndObject()
    builder.Finish(root)
    return bytes(builder.Output())


def _build_encrypted_score_payload(password: bytes) -> bytes:
    builder = flatbuffers.Builder(0)
    encrypted_value = convert_int(12345, password)
    builder.StartObject(1)
    builder.PrependInt32Slot(0, encrypted_value, 0)
    root = builder.EndObject()
    builder.Finish(root)
    return bytes(builder.Output())


def _build_unresolved_vector_payload() -> bytes:
    builder = flatbuffers.Builder(0)
    builder.StartVector(4, 1, 4)
    builder.PrependInt32(0)
    vector = builder.EndVector()
    builder.StartObject(1)
    builder.PrependUOffsetTRelativeSlot(0, vector, 0)
    root = builder.EndObject()
    builder.Finish(root)
    return bytes(builder.Output())


def _build_recovered_root_motion_payload() -> bytes:
    builder = flatbuffers.Builder(0)

    builder.StartObject(1)
    builder.PrependFloat32Slot(0, 3.5, 0)
    position = builder.EndObject()

    builder.StartVector(4, 1, 4)
    builder.PrependUOffsetTRelative(position)
    positions = builder.EndVector()

    builder.StartObject(1)
    builder.PrependUOffsetTRelativeSlot(0, positions, 0)
    move_left = builder.EndObject()

    builder.StartVector(4, 1, 4)
    builder.PrependUOffsetTRelative(move_left)
    ex_skills = builder.EndVector()

    builder.StartObject(4)
    builder.PrependUOffsetTRelativeSlot(2, move_left, 0)
    builder.PrependUOffsetTRelativeSlot(1, ex_skills, 0)
    root = builder.EndObject()
    builder.Finish(root)
    return bytes(builder.Output())


def _assert_optional_schema_hint(hint: Any, expected_schema: type[Any]) -> None:
    assert expected_schema in get_args(get_args(hint)[0])


def test_flatbuffer_parser_reads_descriptors_and_implicit_enums(tmp_path: Path) -> None:
    dump_path = _write_dump(tmp_path, _sample_dump_cs())

    parser = FlatBufferCSParser(str(dump_path))
    enums = parser.parse_enums()
    descriptors = parser.parse_types()

    assert [(enum.name, enum.underlying_type, enum.type_def_index) for enum in enums] == [
        ("AttackType", "System.Int32", 1),
        ("ProductionStep", "System.Int32", 2),
    ]
    assert [(member.name, member.value, member.token) for member in enums[1].members] == [
        ("ToDo", 0, "0x04000005"),
        ("Doing", 1, "0x04000006"),
    ]

    sample_table = next(item for item in descriptors if item.name == "SampleTable")
    assert sample_table.namespace == "FlatData"
    assert sample_table.type_def_index == 4
    assert sample_table.token == "0x02000004"
    assert [
        (
            field.index,
            field.name,
            field.cs_type,
            field.is_vector,
            field.member_token,
        )
        for field in sample_table.fields
    ] == [
        (0, "OptionalEntry", "FlatData.SampleEntry", False, "0x17000004"),
        (1, "DirectEntry", "FlatData.SampleEntry", False, "0x17000005"),
        (2, "DataList", "FlatData.SampleEntry", True, "0x17000006"),
    ]


def test_flatbuffer_parser_keeps_plain_fields_ending_with_length(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: FlatData
public struct AniStateData : FlatBuffers.IFlatbufferObject // TypeDefIndex: 20 Token: 0x02000014
{
    public System.String ClipName { get; } // Token: 0x17000020
    public System.Single Length { get; } // Token: 0x17000021
    public System.Int32 EventsLength { get; } // Token: 0x17000022
    public System.Nullable`1<FlatData.AniEventData> Events(System.Int32 j) { }
}
""",
    )

    descriptor = FlatBufferCSParser(str(dump_path)).parse_types()[0]

    assert [
        (field.index, field.name, field.cs_type, field.is_vector)
        for field in descriptor.fields
    ] == [
        (0, "ClipName", "System.String", False),
        (1, "Length", "System.Single", False),
        (2, "Events", "FlatData.AniEventData", True),
    ]


def test_flatbuffer_codegen_creates_importable_schema_registry(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, _sample_dump_cs())
    output_dir = tmp_path / "FlatBufferData"
    parser = FlatBufferCSParser(str(dump_path))

    CompileFlatBufferToPython(
        parser.parse_types(),
        str(output_dir),
        parser.parse_enums(),
    ).create_schema_files()

    assert (output_dir / "__init__.py").is_file()
    assert (output_dir / "_metadata.py").is_file()
    assert (output_dir / "_registry.py").is_file()
    assert (output_dir / "SampleEntry.py").is_file()
    assert (output_dir / "SampleTable.py").is_file()
    assert (output_dir / "AttackType.py").is_file()

    for python_file in output_dir.glob("*.py"):
        py_compile.compile(str(python_file), doraise=True)

    entry_module = _load_generated_module(output_dir, "SampleEntry")
    table_module = _load_generated_module(output_dir, "SampleTable")
    attack_type_module = _load_generated_module(output_dir, "AttackType")
    registry_module = _load_generated_module(output_dir, "_registry")

    assert is_dataclass(entry_module.SampleEntry)
    assert issubclass(attack_type_module.AttackType, IntEnum)
    assert attack_type_module.AttackType.Special.value == 7
    assert registry_module.FLATBUFFER_TYPES["SampleTable"] is table_module.SampleTable
    assert registry_module.FLATBUFFER_ENUMS["FlatData.AttackType"] is attack_type_module.AttackType

    hints = get_type_hints(
        table_module.SampleTable,
        globalns=table_module.__dict__,
        include_extras=True,
    )
    data_list_hint = hints["DataList"]
    assert get_origin(data_list_hint) is Annotated
    assert get_args(get_args(data_list_hint)[0])[0] is entry_module.SampleEntry
    metadata = get_args(data_list_hint)[1]
    assert isinstance(metadata, FlatBufferField)
    assert metadata.index == 2
    assert metadata.is_vector is True
    assert metadata.cs_type == "FlatData.SampleEntry"


def test_flatbuffer_codegen_renames_sunder_enum_members(tmp_path: Path) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: FlatData
public enum CostSign // TypeDefIndex: 10 Token: 0x0200000A
{
    // Fields
    public System.Int32 value__; // 0x0 Token: 0x04000001
    public static const FlatData.CostSign Plus; // 0x0 Token: 0x04000002
    public static const FlatData.CostSign _MAX_; // 0x0 Token: 0x04000003
}
""",
    )
    output_dir = tmp_path / "FlatBufferData"
    parser = FlatBufferCSParser(str(dump_path))

    CompileFlatBufferToPython(
        parser.parse_types(),
        str(output_dir),
        parser.parse_enums(),
    ).create_schema_files()

    source = (output_dir / "CostSign.py").read_text(encoding="utf8")
    assert "_MAX_ = 1" not in source
    assert "MAX_ = 1" in source
    module = _load_generated_module(output_dir, "CostSign")
    assert module.CostSign.MAX_.value == 1


def test_flatbuffer_codegen_preserves_cn_recovered_flatdata_references(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, _cn_recovered_flatbuffer_dump_cs())
    output_dir = tmp_path / "FlatBufferData"
    parser = FlatBufferCSParser(str(dump_path))

    CompileFlatBufferToPython(
        parser.parse_types(),
        str(output_dir),
        parser.parse_enums(),
    ).create_schema_files()

    root_motion_module = _load_generated_module(output_dir, "RootMotionFlat")
    animator_module = _load_generated_module(output_dir, "AnimatorData")
    animation_blend_module = _load_generated_module(output_dir, "AnimationBlendTable")
    ground_grid_module = _load_generated_module(output_dir, "GroundGridFlat")
    ground_node_module = _load_generated_module(output_dir, "GroundNodeFlat")

    root_hints = get_type_hints(
        root_motion_module.RootMotionFlat,
        globalns=root_motion_module.__dict__,
        include_extras=True,
    )
    _assert_optional_schema_hint(root_hints["MoveLeft"], root_motion_module.Motion)
    assert get_args(get_args(root_hints["Forms"])[0])[0] is root_motion_module.Form
    assert get_args(get_args(root_hints["ExSkills"])[0])[0] is root_motion_module.Motion

    animator_hints = get_type_hints(
        animator_module.AnimatorData,
        globalns=animator_module.__dict__,
        include_extras=True,
    )
    assert get_args(get_args(animator_hints["DataList"])[0])[0] is animator_module.AniStateData

    blend_hints = get_type_hints(
        animation_blend_module.AnimationBlendTable,
        globalns=animation_blend_module.__dict__,
        include_extras=True,
    )
    assert get_args(get_args(blend_hints["DataList"])[0])[0] is animation_blend_module.BlendData

    ground_grid_hints = get_type_hints(
        ground_grid_module.GroundGridFlat,
        globalns=ground_grid_module.__dict__,
        include_extras=True,
    )
    assert (
        get_args(get_args(ground_grid_hints["Nodes"])[0])[0]
        is ground_grid_module.GroundNodeFlat
    )

    ground_node_hints = get_type_hints(
        ground_node_module.GroundNodeFlat,
        globalns=ground_node_module.__dict__,
        include_extras=True,
    )
    _assert_optional_schema_hint(
        ground_node_hints["Position"],
        ground_node_module.GroundVector3,
    )


def test_flatbuffer_reader_decodes_cn_recovered_nested_motion_references(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, _cn_recovered_flatbuffer_dump_cs())
    output_dir = tmp_path / "FlatBufferData"
    parser = FlatBufferCSParser(str(dump_path))
    CompileFlatBufferToPython(
        parser.parse_types(),
        str(output_dir),
        parser.parse_enums(),
    ).create_schema_files()
    root_motion_module = _load_generated_module(output_dir, "RootMotionFlat")

    result = FlatBufferReader(_build_recovered_root_motion_payload()).read_root(
        root_motion_module.RootMotionFlat
    )

    assert result == {
        "Forms": [],
        "ExSkills": [{"Positions": [{"X": 3.5}]}],
        "MoveLeft": {"Positions": [{"X": 3.5}]},
        "MoveRight": None,
    }


def test_flatbuffer_reader_decodes_table_root_vector_and_nested_enums(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, _sample_dump_cs())
    output_dir = tmp_path / "FlatBufferData"
    parser = FlatBufferCSParser(str(dump_path))
    CompileFlatBufferToPython(
        parser.parse_types(),
        str(output_dir),
        parser.parse_enums(),
    ).create_schema_files()
    table_module = _load_generated_module(output_dir, "SampleTable")

    result = FlatBufferReader(_build_sample_table_payload()).read_root(
        table_module.SampleTable
    )

    assert result["OptionalEntry"] is None
    assert result["DirectEntry"] == {
        "X": 1.5,
        "AttackType": "Special",
        "Name": "Direct",
    }
    assert result["DataList"] == [
        {"X": 1.5, "AttackType": "Special", "Name": "First"},
        {"X": 1.5, "AttackType": "Normal", "Name": "Second"},
    ]


def test_flatbuffer_reader_applies_field_decryption() -> None:
    @FlatBufferReader.schema
    class ScoreExcel:
        Score: Annotated[int, FlatBufferField(index=0, cs_type="System.Int32")]

    password = create_key("Score")

    result = FlatBufferReader(_build_encrypted_score_payload(password)).read_root(
        ScoreExcel,
        password=password,
    )

    assert result == {"Score": 12345}


def test_flatbuffer_reader_deduplicates_unresolved_vector_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @FlatBufferReader.schema
    class UnresolvedVectorTable:
        Items: Annotated[
            list[Any],
            FlatBufferField(
                index=0,
                cs_type="Unknown.Item",
                original_name="Items",
                is_vector=True,
            ),
        ]

    logger = RecordingLogger()
    monkeypatch.setattr(flatbuffer_reader_module, "LOGGER", logger)
    FlatBufferReader.reset_warning_cache()

    payload = _build_unresolved_vector_payload()
    FlatBufferReader(payload).read_root(UnresolvedVectorTable)
    FlatBufferReader(payload).read_root(UnresolvedVectorTable)

    assert logger.warn_messages == [
        "Unresolved FlatBuffer vector field skipped: UnresolvedVectorTable.Items (Unknown.Item)."
    ]


def test_schema_workflow_compile_generates_flatbuffer_and_memorypack_data(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    dumps_dir = Path(context.extract_dir) / "Dumps"
    dumps_dir.mkdir(parents=True, exist_ok=True)
    (dumps_dir / "dump.cs").write_text(_sample_dump_cs(), encoding="utf8")

    logger = RecordingLogger()
    workflow = SchemaWorkflow(DummyHttpClient(), logger)
    workflow.compile(context)

    flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
    assert (flatbuffer_data_dir / "SampleEntry.py").is_file()
    assert (flatbuffer_data_dir / "_registry.py").is_file()
    for python_file in flatbuffer_data_dir.glob("*.py"):
        py_compile.compile(str(python_file), doraise=True)

    memorypack_data_dir = Path(context.extract_dir) / "MemoryPackData"
    assert (memorypack_data_dir / "TableBundle.py").is_file()
    assert (memorypack_data_dir / "_registry.py").is_file()
    for python_file in memorypack_data_dir.glob("*.py"):
        py_compile.compile(str(python_file), doraise=True)
    assert logger.info_messages.count("Parsing dump.cs...") == 1
    assert logger.info_messages.count("Generating FlatBufferData schema files...") == 1
    assert logger.info_messages.count("Generating MemoryPackData schema files...") == 1


def test_schema_workflow_warns_when_memorypack_codegen_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    dumps_dir = Path(context.extract_dir) / "Dumps"
    dumps_dir.mkdir(parents=True, exist_ok=True)
    (dumps_dir / "dump.cs").write_text(_sample_dump_cs(), encoding="utf8")

    def fail_memorypack_generation(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        raise RuntimeError("memorypack unavailable")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.schema.workflow.CompileMemoryPackToPython",
        fail_memorypack_generation,
    )
    logger = RecordingLogger()

    SchemaWorkflow(DummyHttpClient(), logger).compile(context)

    assert (Path(context.extract_dir) / "FlatBufferData" / "SampleEntry.py").is_file()
    assert any("MemoryPackData generation failed" in item for item in logger.warn_messages)
