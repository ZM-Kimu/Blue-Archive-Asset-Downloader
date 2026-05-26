from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest


def test_tools_package_no_longer_exports_legacy_flatbuffer_aliases() -> None:
    import ba_downloader.infrastructure.tools as tools

    assert not hasattr(tools, "CSParser")
    assert not hasattr(tools, "CompileToPython")
    assert not hasattr(tools, "CompileFlatBufferToPython")
    assert not hasattr(tools, "CompileMemoryPackToPython")
    assert not hasattr(tools, "FlatBufferCSParser")
    assert not hasattr(tools, "FlatBufferExporter")
    assert not hasattr(tools, "FlatBufferReader")
    assert not hasattr(tools, "MemoryPackCSParser")
    assert not hasattr(tools, "MemoryPackReader")

    removed_schema_modules = (
        "flatbuffer_codegen",
        "flatbuffer_descriptors",
        "flatbuffer_generator",
        "flatbuffer_parser",
        "flatbuffer_reader",
        "flatbuffer_workflow",
        "generated_registry",
        "memorypack_codegen",
        "memorypack_descriptors",
        "memorypack_generator",
        "memorypack_parser",
        "memorypack_reader",
        "schema_codegen",
        "schema_csharp",
    )
    for module_name in removed_schema_modules:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(f"ba_downloader.infrastructure.tools.{module_name}")


def test_schema_package_exposes_flatbuffer_and_memorypack_apis() -> None:
    from ba_downloader.infrastructure.schema.flatbuffer import (
        CompileFlatBufferToPython,
        FlatBufferCSParser,
        FlatBufferExporter,
        FlatBufferReader,
    )
    from ba_downloader.infrastructure.schema.memorypack import (
        CompileMemoryPackToPython,
        MemoryPackCSParser,
        MemoryPackReader,
        MemoryPackSchemaRegistry,
    )

    assert CompileFlatBufferToPython.__name__ == "CompileFlatBufferToPython"
    assert FlatBufferCSParser.__name__ == "FlatBufferCSParser"
    assert FlatBufferExporter.__name__ == "FlatBufferExporter"
    assert FlatBufferReader.__name__ == "FlatBufferReader"
    assert CompileMemoryPackToPython.__name__ == "CompileMemoryPackToPython"
    assert MemoryPackCSParser.__name__ == "MemoryPackCSParser"
    assert MemoryPackReader.__name__ == "MemoryPackReader"
    assert MemoryPackSchemaRegistry.__name__ == "MemoryPackSchemaRegistry"


def test_schema_workflow_no_longer_uses_flatbuffer_only_naming() -> None:
    from ba_downloader.domain.ports import extract
    from ba_downloader.infrastructure import schema
    from ba_downloader.infrastructure.schema import workflow

    assert hasattr(extract, "SchemaWorkflowPort")
    assert not hasattr(extract, "FlatbufferWorkflowPort")
    assert hasattr(schema, "SchemaWorkflow")
    assert hasattr(workflow, "SchemaWorkflow")
    assert not hasattr(schema, "FlatbufferWorkflow")
    assert not hasattr(workflow, "FlatbufferWorkflow")


def test_table_extractor_no_longer_uses_flat_data_dir_name() -> None:
    from ba_downloader.infrastructure.extraction import table
    from ba_downloader.infrastructure.extraction.table.extractor import TableExtractor

    signature = inspect.signature(TableExtractor)

    assert "flat_data_dir" not in signature.parameters
    assert not hasattr(table, "GeneratedDumpWrapperError")


def test_generated_schema_registry_loads_class_and_module_name_registries(
    tmp_path: Path,
) -> None:
    from ba_downloader.infrastructure.schema.common.generated_registry import (
        GeneratedSchemaRegistry,
    )

    class_registry_dir = tmp_path / "FlatBufferData"
    class_registry_dir.mkdir()
    (class_registry_dir / "__init__.py").write_text("", encoding="utf8")
    (class_registry_dir / "Sample.py").write_text(
        "class Sample:\n    pass\n",
        encoding="utf8",
    )
    (class_registry_dir / "_registry.py").write_text(
        "from .Sample import Sample\n"
        'FLATBUFFER_TYPES = {"Sample": Sample}\n'
        "FLATBUFFER_ENUMS = {}\n",
        encoding="utf8",
    )

    class_registry = GeneratedSchemaRegistry.from_directory(
        class_registry_dir,
        type_registry_name="FLATBUFFER_TYPES",
        enum_registry_name="FLATBUFFER_ENUMS",
        package_prefix="test_flatbuffer_schema",
    )

    assert class_registry.types["Sample"].__name__ == "Sample"
    assert class_registry.resolve_type("sample").__name__ == "Sample"

    module_registry_dir = tmp_path / "MemoryPackData"
    module_registry_dir.mkdir()
    (module_registry_dir / "__init__.py").write_text("", encoding="utf8")
    (module_registry_dir / "MediaCatalog.py").write_text(
        "class MediaCatalog:\n    pass\n",
        encoding="utf8",
    )
    (module_registry_dir / "_registry.py").write_text(
        'MEMORYPACK_TYPES = {"Media.Service.MediaCatalog": "MediaCatalog"}\n'
        "MEMORYPACK_ENUMS = {}\n",
        encoding="utf8",
    )

    module_registry = GeneratedSchemaRegistry.from_directory(
        module_registry_dir,
        type_registry_name="MEMORYPACK_TYPES",
        enum_registry_name="MEMORYPACK_ENUMS",
        package_prefix="test_memorypack_schema",
        registry_values_are_module_names=True,
    )

    assert (
        module_registry.types["Media.Service.MediaCatalog"].__name__ == "MediaCatalog"
    )
    assert module_registry.resolve_type("MediaCatalog").__name__ == "MediaCatalog"
