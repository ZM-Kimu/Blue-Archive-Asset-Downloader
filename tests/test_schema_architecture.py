from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


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


def test_generated_schema_registry_serializes_parallel_schema_loads(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from ba_downloader.infrastructure.schema.common import generated_registry
    from ba_downloader.infrastructure.schema.common.generated_registry import (
        GeneratedSchemaRegistry,
    )

    registry_dir = tmp_path / "FlatBufferData"
    registry_dir.mkdir()
    (registry_dir / "__init__.py").write_text("", encoding="utf8")
    (registry_dir / "Sample.py").write_text(
        "class Sample:\n    pass\n",
        encoding="utf8",
    )
    (registry_dir / "_registry.py").write_text(
        "from .Sample import Sample\n"
        'FLATBUFFER_TYPES = {"Sample": Sample}\n'
        "FLATBUFFER_ENUMS = {}\n",
        encoding="utf8",
    )

    active_cleanups = 0
    max_active_cleanups = 0
    cleanup_calls = 0
    cleanup_lock = threading.Lock()

    def slow_clear_generated_bytecode(package_dir: Path) -> None:
        nonlocal active_cleanups, max_active_cleanups, cleanup_calls
        _ = package_dir
        with cleanup_lock:
            active_cleanups += 1
            cleanup_calls += 1
            max_active_cleanups = max(max_active_cleanups, active_cleanups)
        time.sleep(0.05)
        with cleanup_lock:
            active_cleanups -= 1

    monkeypatch.setattr(
        generated_registry,
        "_clear_generated_bytecode",
        slow_clear_generated_bytecode,
    )

    def load_registry() -> str:
        registry = GeneratedSchemaRegistry.from_directory(
            registry_dir,
            type_registry_name="FLATBUFFER_TYPES",
            enum_registry_name="FLATBUFFER_ENUMS",
            package_prefix="test_parallel_schema",
        )
        return registry.types["Sample"].__name__

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: load_registry(), range(8)))

    assert results == ["Sample"] * 8
    assert max_active_cleanups == 1
    assert cleanup_calls == 1


def test_generated_schema_registry_ignores_blocked_bytecode_cleanup(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import shutil

    from ba_downloader.infrastructure.schema.common.generated_registry import (
        GeneratedSchemaRegistry,
    )

    registry_dir = tmp_path / "FlatBufferData"
    registry_dir.mkdir()
    (registry_dir / "__init__.py").write_text("", encoding="utf8")
    (registry_dir / "Sample.py").write_text(
        "class Sample:\n    pass\n",
        encoding="utf8",
    )
    (registry_dir / "_registry.py").write_text(
        "from .Sample import Sample\n"
        'FLATBUFFER_TYPES = {"Sample": Sample}\n'
        "FLATBUFFER_ENUMS = {}\n",
        encoding="utf8",
    )
    pycache_dir = registry_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "Sample.cpython-313.pyc").write_bytes(b"locked")

    def blocked_rmtree(path: Path) -> None:
        _ = path
        raise PermissionError("locked pycache")

    monkeypatch.setattr(shutil, "rmtree", blocked_rmtree)

    registry = GeneratedSchemaRegistry.from_directory(
        registry_dir,
        type_registry_name="FLATBUFFER_TYPES",
        enum_registry_name="FLATBUFFER_ENUMS",
        package_prefix="test_blocked_pycache_schema",
    )

    assert registry.types["Sample"].__name__ == "Sample"
