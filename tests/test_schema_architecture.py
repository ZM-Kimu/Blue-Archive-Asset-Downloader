from __future__ import annotations

from pathlib import Path


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


def test_generated_schema_registry_reloads_same_directory_after_regeneration(
    tmp_path: Path,
) -> None:
    from ba_downloader.infrastructure.schema.common.generated_registry import (
        GeneratedSchemaRegistry,
    )

    registry_dir = tmp_path / "FlatBufferData"
    registry_dir.mkdir()
    (registry_dir / "__init__.py").write_text("", encoding="utf8")
    (registry_dir / "Sample.py").write_text(
        "class Sample:\n    version = 'old'\n",
        encoding="utf8",
    )
    (registry_dir / "_registry.py").write_text(
        "from .Sample import Sample\n"
        'FLATBUFFER_TYPES = {"Sample": Sample}\n'
        "FLATBUFFER_ENUMS = {}\n",
        encoding="utf8",
    )

    old_registry = GeneratedSchemaRegistry.from_directory(
        registry_dir,
        type_registry_name="FLATBUFFER_TYPES",
        enum_registry_name="FLATBUFFER_ENUMS",
        package_prefix="test_reload_schema",
    )
    assert old_registry.types["Sample"].version == "old"

    (registry_dir / "Sample.py").write_text(
        "class Sample:\n    version = 'new'\n",
        encoding="utf8",
    )

    new_registry = GeneratedSchemaRegistry.from_directory(
        registry_dir,
        type_registry_name="FLATBUFFER_TYPES",
        enum_registry_name="FLATBUFFER_ENUMS",
        package_prefix="test_reload_schema",
    )

    assert new_registry.types["Sample"].version == "new"
