from __future__ import annotations

import py_compile
from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.tools.flatbuffer_codegen import CSParser
from ba_downloader.infrastructure.tools.flatbuffer_workflow import FlatbufferWorkflow


class DummyHttpClient:
    def close(self) -> None:
        return None


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
public enum AttackType // TypeDefIndex: 1
{
\t// Fields
\tpublic System.Int32 value__; // 0x0
\tpublic const FlatData.AttackType Normal = 0;
}
public struct SampleEntry : FlatBuffers.IFlatbufferObject // TypeDefIndex: 2
{
    public System.Single X { get; } // Token: 0x17000001
    public FlatData.AttackType AttackType { get; } // Token: 0x17000002
}
public struct SampleTable : FlatBuffers.IFlatbufferObject // TypeDefIndex: 3
{
    public System.Nullable`1<FlatData.SampleEntry> OptionalEntry { get; } // Token: 0x17000003
    public FlatBuffers.Offset`1<FlatData.SampleEntry> DirectEntry { get; } // Token: 0x17000004
    public System.Int32 DataListLength { get; } // Token: 0x17000005
    public Nullable<FlatData.SampleEntry> DataList(int j) { }
}
"""


def test_csparser_normalizes_system_and_flatdata_type_names(tmp_path: Path) -> None:
    dump_cs_path = tmp_path / "dump.cs"
    dump_cs_path.write_text(_sample_dump_cs(), encoding="utf8")

    parser = CSParser(str(dump_cs_path))
    enums = parser.parse_enum()
    structs = parser.parse_struct()

    assert enums[0].name == "AttackType"
    assert enums[0].underlying_type == "int"

    sample_entry = next(struct for struct in structs if struct.name == "SampleEntry")
    sample_table = next(struct for struct in structs if struct.name == "SampleTable")

    assert [(prop.name, prop.data_type, prop.is_list) for prop in sample_entry.properties] == [
        ("X", "float", False),
        ("AttackType", "AttackType", False),
    ]
    assert [(prop.name, prop.data_type, prop.is_list) for prop in sample_table.properties] == [
        ("OptionalEntry", "SampleEntry", False),
        ("DirectEntry", "SampleEntry", False),
        ("DataList", "SampleEntry", True),
    ]


def test_flatbuffer_workflow_compile_generates_valid_python_for_normalized_types(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    dumps_dir = Path(context.extract_dir) / "Dumps"
    dumps_dir.mkdir(parents=True, exist_ok=True)
    (dumps_dir / "dump.cs").write_text(_sample_dump_cs(), encoding="utf8")

    workflow = FlatbufferWorkflow(DummyHttpClient(), NullLogger())
    workflow.compile(context)

    flat_data_dir = Path(context.extract_dir) / "FlatData"
    sample_entry_source = (flat_data_dir / "SampleEntry.py").read_text(encoding="utf8")

    assert "System.Single" not in sample_entry_source
    assert "FlatData.AttackType" not in sample_entry_source
    assert "Nullable`1" not in sample_entry_source
    assert "Float32Flags" in sample_entry_source

    sample_table_source = (flat_data_dir / "SampleTable.py").read_text(encoding="utf8")
    assert "System.Nullable`1" not in sample_table_source
    assert "FlatBuffers.Offset`1" not in sample_table_source
    assert "from .SampleEntry import SampleEntry" in sample_table_source

    for python_file in flat_data_dir.glob("*.py"):
        py_compile.compile(str(python_file), doraise=True)
