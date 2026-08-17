from __future__ import annotations

import json
import py_compile
import struct
from dataclasses import is_dataclass
from enum import IntEnum
from pathlib import Path
from typing import Annotated, Any, get_args, get_origin, get_type_hints

import pytest

from ba_downloader.infrastructure.schema.memorypack.descriptors import MemoryPackMember
from ba_downloader.infrastructure.schema.memorypack.formatters import (
    MemoryPackFormatterRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.generator import (
    CompileMemoryPackToPython,
)
from ba_downloader.infrastructure.schema.memorypack.parser import MemoryPackCSParser
from ba_downloader.infrastructure.schema.memorypack.reader import (
    MemoryPackReader,
    MemoryPackSchemaRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.supplemental import (
    SupplementalMemoryPackFormatterBuilder,
)
from generated_modules import load_generated_module

CN_MEMORYPACK_SAMPLE = """
// Namespace: MX.AssetBundles
public class TableBundle : MemoryPack.IMemoryPackable<TableBundle>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 3289, Token: 0x02000CD9
{
    // Fields
    private string _Name_k__BackingField; // Token: 0x04002F0C
    private System.Int64 _Size_k__BackingField; // Token: 0x04002F0D
    private System.Collections.Generic.List<System.String> _Includes_k__BackingField; // Token: 0x04002F13
    // Properties
    public string Name { get; set; } // Token: 0x17000FC2
    public System.Int64 Size { get; set; } // Token: 0x17000FC3
    public System.Collections.Generic.List<System.String> Includes { get; set; } // Token: 0x17000FC9
    // Methods
    public static void Serialize(MemoryPack.MemoryPackWriter writer, TableBundle value) { }
    public static void Deserialize(MemoryPack.MemoryPackReader reader, TableBundle value) { }
}
"""


JP_MEMORYPACK_SAMPLE = """
// Namespace: MX.Logic.Battles
public class GroundCommandCameraShake : MX.Logic.Battles.GroundCommand, MemoryPack.IMemoryPackable`1<GroundCommandCameraShake>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 4006 Token: 0x02000FA6
{
    // Fields
    private System.Single _Duration_k__BackingField; // Token: 0x04003850
    private System.Boolean _UseCurve_k__BackingField; // Token: 0x04003851
    // Properties
    public System.Single Duration { get; set; } // Token: 0x17001234
    public System.Boolean UseCurve { get; set; } // Token: 0x17001235
    // Methods
    public static System.Void Serialize(MemoryPack.MemoryPackWriter writer, GroundCommandCameraShake value) { }
    public static System.Void Deserialize(MemoryPack.MemoryPackReader reader, GroundCommandCameraShake value) { }
}
"""

JP_COLLECTION_SAMPLE = """
// Namespace: Media.Service
public class MediaCatalog : MemoryPack.IMemoryPackable`1<Media.Service.MediaCatalog>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 9675 Token: 0x020025CB
{
    // Fields
    private System.Collections.Generic.Dictionary`2<System.String, Media.Service.Media> <Table>k__BackingField; // 0x10 Token: 0x04009011
    private System.Collections.Generic.List`1<System.String> <Names>k__BackingField; // 0x18 Token: 0x04009012

    // Properties
    public System.Collections.Generic.Dictionary`2<System.String, Media.Service.Media> Table { get; set; } // Token: 0x17002B65
    public System.Collections.Generic.List`1<System.String> Names { get; set; } // Token: 0x17002B66
}
"""

JP_FIELD_ONLY_SAMPLE = """
// Namespace: MXBehaviorTree
public class DebugLog : MXBehaviorTree.Task, MemoryPack.IMemoryPackable`1<MXBehaviorTree.DebugLog>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 33790 Token: 0x02000031
{
    // Fields
    private MXBehaviorTree.ConstantPropertyString log; // 0x38 Token: 0x0400004A

    // Methods
    public static System.Void Serialize(MemoryPack.MemoryPackWriter writer, MXBehaviorTree.DebugLog value) { }
    public static System.Void Deserialize(MemoryPack.MemoryPackReader reader, MXBehaviorTree.DebugLog value) { }
}
"""

JP_MEDIA_REFERENCE_SAMPLE = """
// Namespace: Media.Service
public enum MediaType // TypeDefIndex: 9671 Token: 0x020025C8
{
    // Fields
    public System.Int32 value__; // 0x0 Token: 0x0400B0AA
    public static const Media.Service.MediaType None; // 0x0 Token: 0x0400B0AB
    public static const Media.Service.MediaType Audio; // 0x0 Token: 0x0400B0AC
    public static const Media.Service.MediaType Video; // 0x0 Token: 0x0400B0AD
}

// Namespace: Media.Service
public class Media : MemoryPack.IMemoryPackable`1<Media.Service.Media>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 9673 Token: 0x020025C9
{
    // Fields
    private System.String <Path>k__BackingField; // 0x10 Token: 0x0400B0AF
    private Media.Service.MediaType <MediaType>k__BackingField; // 0x58 Token: 0x0400B0B9

    // Properties
    public System.String Path { get; set; } // Token: 0x17002B5E
    public Media.Service.MediaType MediaType { get; set; } // Token: 0x17002B64
}

// Namespace: Media.Service
public class MediaCatalog : MemoryPack.IMemoryPackable`1<Media.Service.MediaCatalog>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 9675 Token: 0x020025CB
{
    // Fields
    private System.Collections.Generic.Dictionary`2<System.String, Media.Service.Media> <Table>k__BackingField; // 0x10 Token: 0x0400B0BA

    // Properties
    public System.Collections.Generic.Dictionary`2<System.String, Media.Service.Media> Table { get; set; } // Token: 0x17002B65
}
"""

JP_CYCLIC_REFERENCE_SAMPLE = """
// Namespace: Sample
public class NodeA : MemoryPack.IMemoryPackable`1<Sample.NodeA>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 10 Token: 0x0200000A
{
    // Fields
    private Sample.NodeB <Child>k__BackingField; // 0x10 Token: 0x0400000A

    // Properties
    public Sample.NodeB Child { get; set; } // Token: 0x1700000A
}

// Namespace: Sample
public class NodeB : MemoryPack.IMemoryPackable`1<Sample.NodeB>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 11 Token: 0x0200000B
{
    // Fields
    private Sample.NodeA <Parent>k__BackingField; // 0x10 Token: 0x0400000B

    // Properties
    public Sample.NodeA Parent { get; set; } // Token: 0x1700000B
}
"""

CN_PROPERTY_MODIFIER_SAMPLE = """
// Namespace: MXBehaviorTree
public class Root : MemoryPack.IMemoryPackable<MXBehaviorTree.Root>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 27182, Token: 0x02000034
{
    // Fields
    private int <childCount>k__BackingField; // Token: 0x04000017
    private string <valueString>k__BackingField; // Token: 0x04000018
    // Properties
    public override int childCount { get; } // Token: 0x17000017
    public virtual string valueString { get; } // Token: 0x17000018
}
"""


def _write_dump(tmp_path: Path, content: str) -> Path:
    dump_path = tmp_path / "dump.cs"
    dump_path.write_text(content, encoding="utf8")
    return dump_path


def _load_generated_module(package_dir: Path, module_name: str) -> Any:
    return load_generated_module(package_dir, module_name, "generated_memorypack")


def test_memorypack_parser_reads_cn_style_imemorypackable_types(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, CN_MEMORYPACK_SAMPLE)

    descriptors = MemoryPackCSParser(str(dump_path)).parse_types()

    assert len(descriptors) == 1
    descriptor = descriptors[0]
    assert descriptor.name == "TableBundle"
    assert descriptor.namespace == "MX.AssetBundles"
    assert descriptor.kind == "class"
    assert descriptor.base_type is None
    assert descriptor.type_def_index == 3289
    assert descriptor.token == "0x02000CD9"
    assert "MemoryPack.IMemoryPackable<TableBundle>" in descriptor.interfaces
    assert [
        (member.index, member.name, member.cs_type, member.backing_field_token)
        for member in descriptor.members
    ] == [
        (0, "Name", "string", "0x04002F0C"),
        (1, "Size", "System.Int64", "0x04002F0D"),
        (
            2,
            "Includes",
            "System.Collections.Generic.List<System.String>",
            "0x04002F13",
        ),
    ]


def test_memorypack_parser_reads_jp_style_imemorypackable_types(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, JP_MEMORYPACK_SAMPLE)

    descriptor = MemoryPackCSParser(str(dump_path)).parse_types()[0]

    assert descriptor.name == "GroundCommandCameraShake"
    assert descriptor.namespace == "MX.Logic.Battles"
    assert descriptor.kind == "class"
    assert descriptor.base_type == "MX.Logic.Battles.GroundCommand"
    assert descriptor.type_def_index == 4006
    assert descriptor.token == "0x02000FA6"
    assert (
        "MemoryPack.IMemoryPackable`1<GroundCommandCameraShake>"
        in descriptor.interfaces
    )
    assert [(member.name, member.python_type) for member in descriptor.members] == [
        ("Duration", "float"),
        ("UseCurve", "bool"),
    ]


def test_memorypack_parser_handles_jp_collection_arity_and_backing_fields(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, JP_COLLECTION_SAMPLE)

    descriptor = MemoryPackCSParser(str(dump_path)).parse_types()[0]

    assert descriptor.name == "MediaCatalog"
    assert [
        (member.name, member.python_type, member.backing_field_token)
        for member in descriptor.members
    ] == [
        ("Table", "dict[str, Any] | None", "0x04009011"),
        ("Names", "list[str] | None", "0x04009012"),
    ]


def test_memorypack_parser_uses_fields_when_type_has_no_properties(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, JP_FIELD_ONLY_SAMPLE)

    descriptor = MemoryPackCSParser(str(dump_path)).parse_types()[0]

    assert descriptor.name == "DebugLog"
    assert descriptor.namespace == "MXBehaviorTree"
    assert [
        (
            member.name,
            member.cs_type,
            member.python_type,
            member.member_token,
            member.backing_field_token,
        )
        for member in descriptor.members
    ] == [
        (
            "log",
            "MXBehaviorTree.ConstantPropertyString",
            "Any",
            "0x0400004A",
            "0x0400004A",
        )
    ]


def test_memorypack_parser_combines_serialized_properties_and_fields(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: Sample
public class MixedLayout : MemoryPack.IMemoryPackable`1<Sample.MixedLayout>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
    // Fields
    private System.Boolean <RandomTargetSelect>k__BackingField; // Token: 0x04000001
    public System.Int32 TargetCount; // Token: 0x04000002
    private System.Int32 runtimeState; // Token: 0x04000003
    // Properties
    public System.Boolean IsValid { get; } // Token: 0x17000001
    public System.Boolean RandomTargetSelect { get; set; } // Token: 0x17000002
}
""",
    )

    descriptor = MemoryPackCSParser(str(dump_path)).parse_types()[0]

    assert [member.name for member in descriptor.members] == [
        "RandomTargetSelect",
        "TargetCount",
    ]


def test_memorypack_parser_excludes_unbacked_computed_properties(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: Sample
public class ComputedLayout : MemoryPack.IMemoryPackable`1<Sample.ComputedLayout>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
    // Fields
    private System.Int32 <Value>k__BackingField; // Token: 0x04000002
    // Properties
    public System.String UIPath { get; } // Token: 0x17000001
    public System.Int32 Value { get; set; } // Token: 0x17000002
    public System.Single FadeOutTimeSecond { get; } // Token: 0x17000003
}
""",
    )

    descriptor = MemoryPackCSParser(str(dump_path)).parse_types()[0]

    assert [member.name for member in descriptor.members] == ["Value"]


def test_memorypack_parser_orders_properties_by_backing_field_token(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: Sample
public class TokenLayout : MemoryPack.IMemoryPackable`1<Sample.TokenLayout>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
    // Fields
    private System.Int32 <First>k__BackingField; // Token: 0x04000001
    private System.Int32 <Second>k__BackingField; // Token: 0x04000002
    // Properties
    public System.Int32 Second { get; set; } // Token: 0x17000001
    public System.Int32 First { get; set; } // Token: 0x17000002
}
""",
    )

    descriptor = MemoryPackCSParser(str(dump_path)).parse_types()[0]

    assert [member.name for member in descriptor.members] == ["First", "Second"]


def test_memorypack_parser_excludes_delegate_fields_from_wire_layout(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: Sample
public class DelegateLayout : MemoryPack.IMemoryPackable`1<Sample.DelegateLayout>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
    public System.String Name; // Token: 0x04000001
    public System.Action Callback; // Token: 0x04000002
    public System.Func<System.Int32, System.Boolean> Predicate; // Token: 0x04000003
    public System.Delegate Handler; // Token: 0x04000004
    public System.MulticastDelegate MulticastHandler; // Token: 0x04000005
}
""",
    )

    descriptor = MemoryPackCSParser(str(dump_path)).parse_types()[0]

    assert [member.name for member in descriptor.members] == ["Name"]


def test_memorypack_parser_reads_keyed_collection_formatter(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: Sample
public class EntityCollection : System.Collections.ObjectModel.KeyedCollection`2<System.String, Sample.Entity>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
}
""",
    )

    descriptors = MemoryPackCSParser(str(dump_path)).parse_collection_formatters()

    assert len(descriptors) == 1
    assert descriptors[0].target_type == "Sample.EntityCollection"
    assert descriptors[0].element_type == "Sample.Entity"


def test_memorypack_parser_resolves_only_declared_formatter_layout_base(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: Sample
public class Root : System.IComparable<Sample.Root>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
    public System.Int32 RootValue; // Token: 0x04000001
}

// Namespace: Sample
public class Child : Sample.Root, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 2 Token: 0x02000002
{
    public System.Int32 ChildValue; // Token: 0x04000002
}
""",
    )

    descriptors = {
        descriptor.full_name: descriptor
        for descriptor in MemoryPackCSParser(
            str(dump_path)
        ).parse_formatter_layout_types()
    }

    assert descriptors["Sample.Root"].base_type is None
    assert descriptors["Sample.Child"].base_type == "Sample.Root"


def test_memorypack_parser_reads_enums_without_explicit_values(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, JP_MEDIA_REFERENCE_SAMPLE)

    enum = MemoryPackCSParser(str(dump_path)).parse_enums()[0]

    assert enum.name == "MediaType"
    assert enum.namespace == "Media.Service"
    assert enum.underlying_type == "System.Int32"
    assert enum.type_def_index == 9671
    assert enum.token == "0x020025C8"
    assert [(member.name, member.value, member.token) for member in enum.members] == [
        ("None", 0, "0x0400B0AB"),
        ("Audio", 1, "0x0400B0AC"),
        ("Video", 2, "0x0400B0AD"),
    ]


def test_memorypack_parser_strips_property_type_modifiers(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, CN_PROPERTY_MODIFIER_SAMPLE)

    descriptor = MemoryPackCSParser(str(dump_path)).parse_types()[0]

    assert [
        (member.name, member.cs_type, member.python_type)
        for member in descriptor.members
    ] == [
        ("childCount", "int", "int"),
        ("valueString", "string", "str | None"),
    ]


def test_memorypack_codegen_creates_importable_annotated_schema(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, CN_MEMORYPACK_SAMPLE)
    output_dir = tmp_path / "MemoryPackData"
    descriptors = MemoryPackCSParser(str(dump_path)).parse_types()

    CompileMemoryPackToPython(descriptors, str(output_dir)).create_schema_files()

    assert (output_dir / "__init__.py").is_file()
    assert (output_dir / "_metadata.py").is_file()
    assert (output_dir / "_registry.py").is_file()
    assert (output_dir / "TableBundle.py").is_file()

    for python_file in output_dir.glob("*.py"):
        py_compile.compile(str(python_file), doraise=True)

    module = _load_generated_module(output_dir, "TableBundle")
    assert is_dataclass(module.TableBundle)

    hints = get_type_hints(module.TableBundle, include_extras=True)
    name_hint = hints["Name"]
    assert get_origin(name_hint) is Annotated
    metadata = get_args(name_hint)[1]
    assert isinstance(metadata, MemoryPackMember)
    assert metadata.index == 0
    assert metadata.cs_type == "string"
    assert metadata.type_name == "TableBundle"
    assert metadata.namespace == "MX.AssetBundles"


def test_memorypack_codegen_exports_enums_and_schema_references(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, JP_MEDIA_REFERENCE_SAMPLE)
    output_dir = tmp_path / "MemoryPackData"
    parser = MemoryPackCSParser(str(dump_path))

    CompileMemoryPackToPython(
        parser.parse_types(),
        str(output_dir),
        parser.parse_enums(),
    ).create_schema_files()

    media_type_source = (output_dir / "MediaType.py").read_text(encoding="utf8")
    media_source = (output_dir / "Media.py").read_text(encoding="utf8")
    media_catalog_source = (output_dir / "MediaCatalog.py").read_text(encoding="utf8")

    assert "class MediaType(IntEnum):" in media_type_source
    assert "None_ = 0" in media_type_source
    assert "Audio = 1" in media_type_source
    assert "from .MediaType import MediaType" in media_source
    assert "MediaType: Annotated[MediaType," in media_source
    assert "from .Media import Media" in media_catalog_source
    assert "Table: Annotated[dict[str, Media] | None," in media_catalog_source

    for python_file in output_dir.glob("*.py"):
        py_compile.compile(str(python_file), doraise=True)

    media_type_module = _load_generated_module(output_dir, "MediaType")
    media_module = _load_generated_module(output_dir, "Media")
    media_catalog_module = _load_generated_module(output_dir, "MediaCatalog")

    assert issubclass(media_type_module.MediaType, IntEnum)
    assert media_type_module.MediaType.None_.value == 0
    assert media_type_module.MediaType.Audio.value == 1

    media_hints = get_type_hints(
        media_module.Media,
        globalns=media_module.__dict__,
        include_extras=True,
    )
    media_type_annotation = get_args(media_hints["MediaType"])[0]
    assert media_type_annotation is media_type_module.MediaType

    catalog_hints = get_type_hints(
        media_catalog_module.MediaCatalog,
        globalns=media_catalog_module.__dict__,
        include_extras=True,
    )
    table_annotation = get_args(catalog_hints["Table"])[0]
    table_type = next(
        arg for arg in get_args(table_annotation) if arg is not type(None)
    )
    assert get_args(table_type)[1] is media_module.Media


def test_memorypack_codegen_keeps_cyclic_schema_references_importable(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(tmp_path, JP_CYCLIC_REFERENCE_SAMPLE)
    output_dir = tmp_path / "MemoryPackData"
    parser = MemoryPackCSParser(str(dump_path))

    CompileMemoryPackToPython(
        parser.parse_types(),
        str(output_dir),
        parser.parse_enums(),
    ).create_schema_files()

    node_a_source = (output_dir / "NodeA.py").read_text(encoding="utf8")
    node_b_source = (output_dir / "NodeB.py").read_text(encoding="utf8")

    assert "TYPE_CHECKING" in node_a_source
    assert "Child: Annotated[NodeB | None," in node_a_source
    assert "Parent: Annotated[NodeA | None," in node_b_source
    assert _load_generated_module(output_dir, "NodeA").NodeA.__name__ == "NodeA"
    assert _load_generated_module(output_dir, "NodeB").NodeB.__name__ == "NodeB"


def test_memorypack_package_exports_reader_api() -> None:
    from ba_downloader.infrastructure.schema.memorypack import (
        MemoryPackReader as PackageMemoryPackReader,
    )
    from ba_downloader.infrastructure.schema.memorypack import (
        MemoryPackSchemaRegistry as PackageMemoryPackSchemaRegistry,
    )

    assert PackageMemoryPackReader is MemoryPackReader
    assert PackageMemoryPackSchemaRegistry is MemoryPackSchemaRegistry


def test_memorypack_reader_decodes_basic_schema_payload() -> None:
    @MemoryPackReader.schema
    class TableBundle:
        Name: Annotated[str | None, MemoryPackMember(index=0, cs_type="string")]
        Size: Annotated[int, MemoryPackMember(index=1, cs_type="System.Int64")]
        Includes: Annotated[
            list[str] | None,
            MemoryPackMember(
                index=2,
                cs_type="System.Collections.Generic.List`1<System.String>",
            ),
        ]

    payload = bytearray()
    payload.extend((3).to_bytes(1, "little"))
    payload.extend((~6).to_bytes(4, "little", signed=True))
    payload.extend((6).to_bytes(4, "little", signed=True))
    payload.extend(b"Bundle")
    payload.extend((123).to_bytes(8, "little", signed=True))
    payload.extend((2).to_bytes(4, "little", signed=True))
    for value in ("A", "B"):
        payload.extend((~len(value)).to_bytes(4, "little", signed=True))
        payload.extend((len(value)).to_bytes(4, "little", signed=True))
        payload.extend(value.encode("utf8"))

    result = MemoryPackReader(bytes(payload)).read_object(TableBundle)

    assert result.Name == "Bundle"
    assert result.Size == 123
    assert result.Includes == ["A", "B"]


def test_memorypack_reader_decodes_nested_dictionary_and_enum_values() -> None:
    class SampleMode(IntEnum):
        Inactive = 0
        Active = 7

    @MemoryPackReader.schema
    class Child:
        Label: Annotated[str | None, MemoryPackMember(index=0, cs_type="string")]

    @MemoryPackReader.schema
    class Parent:
        Mode: Annotated[SampleMode, MemoryPackMember(index=0, cs_type="SampleMode")]
        ChildrenByKey: Annotated[
            dict[str, Child] | None,
            MemoryPackMember(
                index=1,
                cs_type="System.Collections.Generic.Dictionary<System.String, Child>",
            ),
        ]

    payload = bytearray()
    payload.extend((2).to_bytes(1, "little"))
    payload.extend((7).to_bytes(4, "little", signed=True))
    payload.extend((1).to_bytes(4, "little", signed=True))
    payload.extend((~5).to_bytes(4, "little", signed=True))
    payload.extend((5).to_bytes(4, "little", signed=True))
    payload.extend(b"first")
    payload.extend((1).to_bytes(1, "little"))
    payload.extend((~6).to_bytes(4, "little", signed=True))
    payload.extend((6).to_bytes(4, "little", signed=True))
    payload.extend(b"nested")

    result = MemoryPackReader(bytes(payload)).read_object(Parent)

    assert result.Mode is SampleMode.Active
    assert result.ChildrenByKey is not None
    assert result.ChildrenByKey["first"].Label == "nested"


def test_memorypack_reader_decodes_array_schema_members() -> None:
    @MemoryPackReader.schema
    class Child:
        Label: Annotated[str | None, MemoryPackMember(index=0, cs_type="string")]

    @MemoryPackReader.schema
    class Parent:
        Children: Annotated[
            list[Child] | None,
            MemoryPackMember(index=0, cs_type="Child[]"),
        ]

    payload = bytearray()
    payload.extend((1).to_bytes(1, "little"))
    payload.extend((2).to_bytes(4, "little", signed=True))
    for value in ("first", "second"):
        payload.extend((1).to_bytes(1, "little"))
        payload.extend((~len(value)).to_bytes(4, "little", signed=True))
        payload.extend((len(value)).to_bytes(4, "little", signed=True))
        payload.extend(value.encode("utf8"))

    result = MemoryPackReader(bytes(payload)).read_object(Parent)

    assert result.Children is not None
    assert [child.Label for child in result.Children] == ["first", "second"]


def test_memorypack_reader_decodes_formatter_union_payload(
    tmp_path: Path,
) -> None:
    class SampleMode(IntEnum):
        Inactive = 0
        Active = 7

    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.Base",
                        "kind": "union",
                        "method_token": "0x06000001",
                        "union_tags": {"3": "Sample.Derived"},
                    },
                    {
                        "target_type": "Sample.Derived",
                        "kind": "object",
                        "method_token": "0x06000002",
                        "members": [
                            {"name": "Name", "cs_type": "string"},
                            {"name": "Mode", "cs_type": "Sample.Mode"},
                            {"name": "Child", "cs_type": "Sample.Child"},
                        ],
                    },
                    {
                        "target_type": "Sample.Child",
                        "kind": "object",
                        "method_token": "0x06000003",
                        "members": [
                            {"name": "Count", "cs_type": "int"},
                        ],
                    },
                ],
            }
        ),
        encoding="utf8",
    )
    formatter_registry = MemoryPackFormatterRegistry.from_file(sidecar_path)
    schema_registry = MemoryPackSchemaRegistry(
        types={},
        enums={"Sample.Mode": SampleMode},
    )

    payload = bytearray()
    payload.extend((3).to_bytes(4, "little", signed=True))
    payload.extend((~5).to_bytes(4, "little", signed=True))
    payload.extend((5).to_bytes(4, "little", signed=True))
    payload.extend(b"skill")
    payload.extend((7).to_bytes(4, "little", signed=True))
    payload.extend((42).to_bytes(4, "little", signed=True))

    result = MemoryPackReader(bytes(payload)).read_formatter_object(
        "Sample.Base",
        schema_registry,
        formatter_registry,
    )

    assert result == {
        "__type__": "Sample.Derived",
        "Name": "skill",
        "Mode": "Active",
        "Child": {"__type__": "Sample.Child", "Count": 42},
    }


def test_memorypack_formatter_registry_parses_extended_layout_metadata(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.Base",
                        "kind": "union",
                        "formatter_type": "Sample.BaseFormatter",
                        "formatter_token": "0x02000001",
                        "method_token": "0x06000001",
                        "method_rva": "0x1234",
                        "tag_type": "byte",
                        "union_tags": {"2": "Sample.Derived"},
                    },
                    {
                        "target_type": "Sample.Derived",
                        "kind": "object",
                        "formatter_type": "Sample.DerivedFormatter",
                        "formatter_token": "0x02000002",
                        "object_header": True,
                        "members": [
                            {
                                "name": "Name",
                                "cs_type": "string",
                                "source": "verified",
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf8",
    )

    registry = MemoryPackFormatterRegistry.from_file(sidecar_path)

    base_formatter = registry.resolve("Sample.Base")
    assert base_formatter is not None
    assert base_formatter.formatter_type == "Sample.BaseFormatter"
    assert base_formatter.formatter_token == "0x02000001"
    assert base_formatter.tag_type == "byte"
    assert base_formatter.union_tags == {2: "Sample.Derived"}

    derived_formatter = registry.resolve("Sample.Derived")
    assert derived_formatter is not None
    assert derived_formatter.object_header is True
    assert derived_formatter.members[0].source == "verified"


def test_memorypack_reader_decodes_formatter_object_header_and_byte_union_tag(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.Base",
                        "kind": "union",
                        "tag_type": "byte",
                        "union_tags": {"2": "Sample.Derived"},
                    },
                    {
                        "target_type": "Sample.Derived",
                        "kind": "object",
                        "object_header": True,
                        "members": [
                            {"name": "Name", "cs_type": "string"},
                            {"name": "Count", "cs_type": "int"},
                        ],
                    },
                ],
            }
        ),
        encoding="utf8",
    )
    formatter_registry = MemoryPackFormatterRegistry.from_file(sidecar_path)
    schema_registry = MemoryPackSchemaRegistry(types={}, enums={})

    payload = bytearray()
    payload.append(2)
    payload.append(2)
    payload.extend(_mp_utf8_string("skill"))
    payload.extend((42).to_bytes(4, "little", signed=True))

    result = MemoryPackReader(bytes(payload)).read_formatter_object(
        "Sample.Base",
        schema_registry,
        formatter_registry,
    )

    assert result == {
        "__type__": "Sample.Derived",
        "Name": "skill",
        "Count": 42,
    }


def test_memorypack_reader_decodes_formatter_special_wire_types(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.Root",
                        "kind": "object",
                        "object_header": True,
                        "members": [
                            {
                                "name": "MaybeId",
                                "cs_type": "System.Nullable`1<System.Int64>",
                            },
                            {"name": "Position2D", "cs_type": "UnityEngine.Vector2"},
                            {"name": "Position3D", "cs_type": "UnityEngine.Vector3"},
                            {"name": "Marker", "cs_type": "System.Char"},
                            {"name": "HashedId", "cs_type": "MX.Core.Services.Hash64"},
                            {
                                "name": "UnknownEnum",
                                "cs_type": "FlatData.UnknownEnum",
                                "wire_type": "int32_enum",
                            },
                            {
                                "name": "Shape",
                                "cs_type": "MX.Logic.Battles.ShapeSpecification",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf8",
    )
    formatter_registry = MemoryPackFormatterRegistry.from_file(sidecar_path)
    schema_registry = MemoryPackSchemaRegistry(types={}, enums={})

    payload = bytearray()
    payload.append(7)
    payload.extend(b"\x01\x00\x00\x00\x00\x00\x00\x00")
    payload.extend((123).to_bytes(8, "little", signed=True))
    payload.extend(_f32(1.5))
    payload.extend(_f32(2.5))
    payload.extend(_f32(3.5))
    payload.extend(_f32(4.5))
    payload.extend(_f32(5.5))
    payload.extend(ord("Z").to_bytes(2, "little"))
    payload.extend((0xFEDCBA9876543210).to_bytes(8, "little"))
    payload.extend((7).to_bytes(4, "little", signed=True))
    payload.extend((2).to_bytes(4, "little", signed=True))
    payload.extend(_f32(10.0))
    payload.extend(_f32(20.0))
    payload.extend((30).to_bytes(4, "little", signed=True))
    payload.extend(_f32(40.0))
    payload.extend(_f32(50.0))
    payload.extend(_f32(60.0))
    payload.extend((70).to_bytes(4, "little", signed=True))
    payload.extend(_f32(80.0))
    payload.extend((90).to_bytes(4, "little", signed=True))
    payload.extend(_f32(100.0))
    payload.extend(_f32(110.0))

    result = MemoryPackReader(bytes(payload)).read_formatter_object(
        "Sample.Root",
        schema_registry,
        formatter_registry,
    )

    assert result["MaybeId"] == 123
    assert result["Position2D"] == {"x": 1.5, "y": 2.5}
    assert result["Position3D"] == {"x": 3.5, "y": 4.5, "z": 5.5}
    assert result["Marker"] == "Z"
    assert result["HashedId"] == {"Hash": 0xFEDCBA9876543210}
    assert result["UnknownEnum"] == 7
    assert result["Shape"] == {
        "__type__": "ShapeSpecification",
        "__unmanaged__": True,
        "Type": 2,
        "PositionOffset": {"x": 10.0, "y": 20.0},
        "AngleOffset": 30,
        "CircleRadius": 40.0,
        "DonutOuterRadius": 50.0,
        "DonutInnerRadius": 60.0,
        "DonutAngle": 70,
        "FanRadius": 80.0,
        "FanAngle": 90,
        "OBBWidth": 100.0,
        "OBBHeight": 110.0,
    }


def test_memorypack_reader_decodes_null_formatter_union(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.Base",
                        "kind": "union",
                        "tag_type": "byte",
                        "union_tags": {"1": "Sample.Child"},
                    }
                ],
            }
        ),
        encoding="utf8",
    )

    result = MemoryPackReader(b"\xff\xff").read_formatter_object(
        "Sample.Base",
        MemoryPackSchemaRegistry(types={}, enums={}),
        MemoryPackFormatterRegistry.from_file(sidecar_path),
    )

    assert result == {
        "__union_root__": "Sample.Base",
        "__union_tag__": 255,
        "__value__": None,
    }


def test_supplemental_formatter_builder_merges_union_and_wire_members(
    tmp_path: Path,
) -> None:
    dump_path = tmp_path / "dump.cs"
    dump_path.write_text(
        """
// Namespace: MX.GameData.DAO.Battle
public abstract class LogicEffectDAO : MemoryPack.IMemoryPackable`1<MX.GameData.DAO.Battle.LogicEffectDAO>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
    // Fields
    public System.Int32 Level; // Token: 0x04000001
    public System.String GroupId; // Token: 0x04000002
    public FlatData.LogicEffectCategory Category; // Token: 0x04000003
    public System.String TemplateId; // Token: 0x04000004
    public System.Int32 Channel; // Token: 0x04000005
    public System.Int64 ApplyRate; // Token: 0x04000006
    public System.String CommonVisualId; // Token: 0x04000007
    public System.UInt32 CommonVisualHash; // Token: 0x04000008
    public System.Int32 PriorityWhenSameFrame; // Token: 0x04000009
    public System.Boolean CanTargetTSAInteractingCharacter; // Token: 0x0400000A
}

// Namespace: MX.GameData.DAO.Battle
public class DamageEffectDAO : MX.GameData.DAO.Battle.LogicEffectDAO, MemoryPack.IMemoryPackable`1<MX.GameData.DAO.Battle.DamageEffectDAO>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 2 Token: 0x02000002
{
    // Fields
    public System.Int64 Amount; // Token: 0x0400000B
}

// Namespace: MX.Logic.Battles
public class GroundCommandSetLimitBreakGauge : MX.Logic.Battles.GroundCommand, MemoryPack.IMemoryPackable`1<MX.Logic.Battles.GroundCommandSetLimitBreakGauge>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 3 Token: 0x02000003
{
    // Fields
    public System.String PrefabPath; // Token: 0x0400000C
}
""".strip(),
        encoding="utf8",
    )
    memorypack_data_dir = tmp_path / "MemoryPackData"
    parser = MemoryPackCSParser(str(dump_path))
    CompileMemoryPackToPython(
        parser.parse_types(),
        str(memorypack_data_dir),
        parser.parse_enums(),
    ).create_schema_files()
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "MX.GameData.DAO.Battle.LogicEffectDAO",
                        "kind": "union",
                        "tag_type": "byte",
                        "union_tags": {"17": "MX.GameData.DAO.Battle.DamageEffectDAO"},
                    },
                    {
                        "target_type": "MX.Logic.Battles.GroundCommand",
                        "kind": "union",
                        "tag_type": "byte",
                        "union_tags": {
                            "34": "MX.Logic.Battles.GroundCommandSetLimitBreakGauge"
                        },
                    },
                ],
            }
        ),
        encoding="utf8",
    )

    SupplementalMemoryPackFormatterBuilder(
        dump_cs_path=dump_path,
        memorypack_data_dir=memorypack_data_dir,
        sidecar_path=sidecar_path,
    ).build()
    registry = MemoryPackFormatterRegistry.from_file(sidecar_path)

    damage = registry.resolve("MX.GameData.DAO.Battle.DamageEffectDAO")
    assert damage is not None
    assert [member.name for member in damage.members[:11]] == [
        "Level",
        "GroupId",
        "Category",
        "TemplateId",
        "Channel",
        "ApplyRate",
        "CommonVisualId",
        "CommonVisualHash",
        "PriorityWhenSameFrame",
        "CanTargetTSAInteractingCharacter",
        "Amount",
    ]
    assert damage.members[2].wire_type == "int32_enum"

    command = registry.resolve("MX.Logic.Battles.GroundCommandSetLimitBreakGauge")
    assert command is not None
    assert [member.name for member in command.members] == ["PrefabPath"]


def test_supplemental_formatter_builder_merges_collection_and_custom_base_layout(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: Sample
public class EntityCollection : System.Collections.ObjectModel.KeyedCollection`2<System.String, Sample.Entity>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
}

// Namespace: Sample
public class Root : System.IComparable<Sample.Root>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 2 Token: 0x02000002
{
    public System.Int32 RootValue; // Token: 0x04000001
}

// Namespace: Sample
public class Child : Sample.Root, MemoryPack.IMemoryPackable`1<Sample.Child>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 3 Token: 0x02000003
{
    public System.Int32 ChildValue; // Token: 0x04000002
}
""",
    )
    memorypack_data_dir = tmp_path / "MemoryPackData"
    parser = MemoryPackCSParser(str(dump_path))
    CompileMemoryPackToPython(
        parser.parse_types(),
        str(memorypack_data_dir),
        parser.parse_enums(),
    ).create_schema_files()
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.Root",
                        "kind": "union",
                        "tag_type": "byte",
                        "union_tags": {"1": "Sample.Child"},
                    }
                ],
            }
        ),
        encoding="utf8",
    )

    SupplementalMemoryPackFormatterBuilder(
        dump_cs_path=dump_path,
        memorypack_data_dir=memorypack_data_dir,
        sidecar_path=sidecar_path,
    ).build()
    registry = MemoryPackFormatterRegistry.from_file(sidecar_path)

    collection = registry.resolve("Sample.EntityCollection")
    assert collection is not None
    assert collection.kind == "collection"
    assert collection.element_type == "Sample.Entity"

    child = registry.resolve("Sample.Child")
    assert child is not None
    assert [member.name for member in child.members] == ["RootValue", "ChildValue"]


def test_supplemental_formatter_builder_excludes_inherited_delegate_members(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: Sample
public class Root : MemoryPack.IMemoryPackable`1<Sample.Root>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 1 Token: 0x02000001
{
    public System.String BaseName; // Token: 0x04000001
    public System.Action Callback; // Token: 0x04000002
}

// Namespace: Sample
public class Child : Sample.Root, MemoryPack.IMemoryPackable`1<Sample.Child>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 2 Token: 0x02000002
{
    public System.Int32 Count; // Token: 0x04000003
    public System.Func<System.Int32, System.Boolean> Predicate; // Token: 0x04000004
}
""",
    )
    memorypack_data_dir = tmp_path / "MemoryPackData"
    parser = MemoryPackCSParser(str(dump_path))
    CompileMemoryPackToPython(
        parser.parse_types(),
        str(memorypack_data_dir),
        parser.parse_enums(),
    ).create_schema_files()
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.Root",
                        "kind": "union",
                        "tag_type": "byte",
                        "union_tags": {"1": "Sample.Child"},
                    }
                ],
            }
        ),
        encoding="utf8",
    )

    SupplementalMemoryPackFormatterBuilder(
        dump_cs_path=dump_path,
        memorypack_data_dir=memorypack_data_dir,
        sidecar_path=sidecar_path,
    ).build()
    registry = MemoryPackFormatterRegistry.from_file(sidecar_path)

    child = registry.resolve("Sample.Child")
    assert child is not None
    assert [member.name for member in child.members] == ["BaseName", "Count"]


def test_memorypack_reader_decodes_formatter_collection(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.EntityCollection",
                        "kind": "collection",
                        "element_type": "Sample.Entity",
                    },
                    {
                        "target_type": "Sample.Entity",
                        "kind": "object",
                        "object_header": True,
                        "members": [{"name": "Id", "cs_type": "int"}],
                    },
                ],
            }
        ),
        encoding="utf8",
    )
    payload = bytearray((2).to_bytes(4, "little", signed=True))
    for value in (11, 22):
        payload.append(1)
        payload.extend(value.to_bytes(4, "little", signed=True))

    result = MemoryPackReader(bytes(payload)).read_formatter_object(
        "Sample.EntityCollection",
        MemoryPackSchemaRegistry(types={}, enums={}),
        MemoryPackFormatterRegistry.from_file(sidecar_path),
    )

    assert result == [
        {"__type__": "Sample.Entity", "Id": 11},
        {"__type__": "Sample.Entity", "Id": 22},
    ]


def test_supplemental_formatter_builder_requires_runtime_union_sidecar(
    tmp_path: Path,
) -> None:
    dump_path = _write_dump(
        tmp_path,
        """// Namespace: MX.GameData.DAO.Battle
public abstract class LogicEffectDAO : MemoryPack.IMemoryPackable`1<MX.GameData.DAO.Battle.LogicEffectDAO>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 10 Token: 0x0200000A
{
}

// Namespace: MX.GameData.DAO.Battle
public class DamageEffectDAO : MX.GameData.DAO.Battle.LogicEffectDAO, MemoryPack.IMemoryPackable`1<MX.GameData.DAO.Battle.DamageEffectDAO>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 11 Token: 0x0200000B
{
    // Fields
    private System.String <TemplateId>k__BackingField; // Token: 0x04000001
    // Properties
    public System.String TemplateId { get; set; } // Token: 0x17000001
}
""",
    )
    data_dir = tmp_path / "MemoryPackData"
    parser = MemoryPackCSParser(str(dump_path))
    CompileMemoryPackToPython(
        parser.parse_types(),
        str(data_dir),
        parser.parse_enums(),
    ).create_schema_files()
    sidecar_path = tmp_path / "memorypack_formatters.json"

    assert not SupplementalMemoryPackFormatterBuilder(
        dump_cs_path=dump_path,
        memorypack_data_dir=data_dir,
        sidecar_path=sidecar_path,
    ).build()
    assert not sidecar_path.exists()

    union_attrs_path = tmp_path / "memorypack_union_attrs.json"
    union_attrs_path.write_text(
        json.dumps(
            {
                "version": 1,
                "targets": [
                    {
                        "full_name": "MX.GameData.DAO.Battle.LogicEffectDAO",
                        "custom_attributes": [
                            {
                                "attribute_type": (
                                    "MemoryPack.MemoryPackUnionAttribute"
                                ),
                                "tag": 17,
                                "union_type": (
                                    "MX.GameData.DAO.Battle.DamageEffectDAO"
                                ),
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf8",
    )

    assert SupplementalMemoryPackFormatterBuilder(
        dump_cs_path=dump_path,
        memorypack_data_dir=data_dir,
        sidecar_path=sidecar_path,
    ).build()

    registry = MemoryPackFormatterRegistry.from_file(sidecar_path)
    root = registry.resolve("MX.GameData.DAO.Battle.LogicEffectDAO")
    damage = registry.resolve("MX.GameData.DAO.Battle.DamageEffectDAO")
    assert root is not None
    assert root.union_tags is not None
    assert root.union_tags[17] == "MX.GameData.DAO.Battle.DamageEffectDAO"
    assert damage is not None
    assert [member.name for member in damage.members] == ["TemplateId"]


def test_memorypack_reader_rejects_unconsumed_formatter_payload(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "memorypack_formatters.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "Sample.Value",
                        "kind": "object",
                        "members": [{"name": "Count", "cs_type": "int"}],
                    }
                ],
            }
        ),
        encoding="utf8",
    )
    formatter_registry = MemoryPackFormatterRegistry.from_file(sidecar_path)
    schema_registry = MemoryPackSchemaRegistry(types={}, enums={})
    payload = (42).to_bytes(4, "little", signed=True) + b"extra"

    with pytest.raises(ValueError, match="not fully consumed"):
        MemoryPackReader(payload).read_formatter_object(
            "Sample.Value",
            schema_registry,
            formatter_registry,
        )


def _mp_utf8_string(value: str) -> bytes:
    raw = value.encode("utf8")
    if not raw:
        return (0).to_bytes(4, "little", signed=True)
    payload = bytearray()
    payload.extend((~len(raw)).to_bytes(4, "little", signed=True))
    payload.extend(len(raw).to_bytes(4, "little", signed=True))
    payload.extend(raw)
    return bytes(payload)


def _f32(value: float) -> bytes:
    return struct.pack("<f", value)


def _mp_empty_collection() -> bytes:
    return (0).to_bytes(4, "little", signed=True)


def test_memorypack_reader_partially_decodes_skill_visual_dao_payloads() -> None:
    first = bytearray()
    first.append(8)
    first.extend(_mp_utf8_string("Buff_AttackPower_Ally_10s_150_Ratio_SkillVisual01"))
    first.extend(
        _mp_utf8_string("EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio")
    )
    first.extend(_mp_utf8_string(""))
    first.extend(_mp_empty_collection() * 5)

    second = bytearray()
    second.append(8)
    second.extend(_mp_utf8_string("Buff_AttackPower_Ally_10s_175_Ratio_SkillVisual01"))
    second.extend(
        _mp_utf8_string("EventChallenge_Buff_StatChange_AttackPower_Ally_10s_175_Ratio")
    )
    second.extend(_mp_utf8_string(""))
    second.extend(_mp_empty_collection() * 5)

    first_result = MemoryPackReader(bytes(first)).read_cn_table_dao_partial(
        "MX.AppData.DAO.Battle.SkillVisualDAO"
    )
    second_result = MemoryPackReader(bytes(second)).read_cn_table_dao_partial(
        "MX.AppData.DAO.Battle.SkillVisualDAO"
    )

    assert first_result["name"] == "Buff_AttackPower_Ally_10s_150_Ratio_SkillVisual01"
    assert first_result["VisualDataKey"] == (
        "EventChallenge_Buff_StatChange_AttackPower_Ally_10s_150_Ratio"
    )
    assert first_result["GuidePrefabPath"] == ""
    assert first_result["__partial_memorypack__"] is False
    assert first_result["__payload_sha256__"] != second_result["__payload_sha256__"]
    assert second_result["name"] == "Buff_AttackPower_Ally_10s_175_Ratio_SkillVisual01"


def test_memorypack_reader_partially_decodes_skill_logic_dao_prefix() -> None:
    payload = bytearray()
    payload.append(2)
    payload.append(24)
    payload.extend(_mp_utf8_string("AEV_Yoheki_Vulcan01_Ex01_TimelineSkillAction01"))
    payload.extend(_mp_utf8_string("AEVYohekiVulcan01Ex01"))
    payload.extend(b"unknown-tail")

    result = MemoryPackReader(bytes(payload)).read_cn_table_dao_partial(
        "MX.GameData.DAO.Battle.SkillLogicDAO"
    )

    assert result["__type__"] == "MX.GameData.DAO.Battle.SkillLogicDAO"
    assert result["__union_tag__"] == 2
    assert result["__object_header__"] == 24
    assert result["name"] == "AEV_Yoheki_Vulcan01_Ex01_TimelineSkillAction01"
    assert result["SkillDataKey"] == "AEVYohekiVulcan01Ex01"
    assert result["__partial_memorypack__"] is True
    assert result["__remaining_size__"] == len(b"unknown-tail")


def test_memorypack_reader_partially_decodes_logic_effect_dao_common_fields() -> None:
    payload = bytearray()
    payload.append(59)
    payload.append(25)
    payload.extend((1).to_bytes(4, "little", signed=True))
    payload.extend(_mp_utf8_string("Pina_Ex01_Effect01"))
    payload.extend((3).to_bytes(4, "little", signed=True))
    payload.extend(_mp_utf8_string("Buff_StatChange_IgnoreDelayCount_Self"))
    payload.extend((17).to_bytes(4, "little", signed=True))
    payload.extend((10000).to_bytes(8, "little", signed=True))
    payload.extend((0).to_bytes(8, "little", signed=True))
    payload.extend((1).to_bytes(8, "little", signed=True))
    payload.extend((20).to_bytes(4, "little", signed=True))
    payload.extend(b"derived-tail")

    result = MemoryPackReader(bytes(payload)).read_cn_table_dao_partial(
        "MX.GameData.DAO.Battle.LogicEffectDAO"
    )

    assert result["__union_tag__"] == 59
    assert result["__object_header__"] == 25
    assert result["Level"] == 1
    assert result["GroupId"] == "Pina_Ex01_Effect01"
    assert result["Category"] == 3
    assert result["TemplateId"] == "Buff_StatChange_IgnoreDelayCount_Self"
    assert result["Channel"] == 17
    assert result["ApplyRate"] == 10000
    assert result["CommonVisualId"] == 0
    assert result["CommonVisualHash"] == 1
    assert result["PriorityWhenSameFrame"] == 20
    assert result["__partial_memorypack__"] is True


def test_memorypack_reader_partial_decode_rejects_unknown_cn_root_type() -> None:
    with pytest.raises(ValueError, match="Unsupported CN table MemoryPack root type"):
        MemoryPackReader(b"").read_cn_table_dao_partial("Sample.Unknown")
