from __future__ import annotations

import os
from pathlib import Path

import pytest

from ba_downloader.api.files import (
    CleanupPreviewLimitError,
    FileBoundaryError,
    FileRegistry,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.storage.cleanup import (
    BoundedStorageCleanup,
    StorageBoundaryError,
)
from support.fixtures import build_execution_context


def _context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="cn",
        version="",
        max_retries=1,
    )


def test_file_registry_lists_only_configured_roots(tmp_path: Path) -> None:
    context = _context(tmp_path)
    raw = context.workspace.raw
    raw.mkdir(parents=True)
    (raw / "asset.bin").write_bytes(b"payload")
    registry = FileRegistry()

    entries = registry.list_entries(context, "raw")

    assert [entry.relative_path for entry in entries] == ["asset.bin"]
    assert registry.resolve(entries[0].id, context) == (raw / "asset.bin").resolve()


def test_file_registry_reuses_ids_and_evicts_old_entries(tmp_path: Path) -> None:
    context = _context(tmp_path)
    raw = context.workspace.raw
    raw.mkdir(parents=True)
    (raw / "a.bin").write_bytes(b"a")
    registry = FileRegistry(file_limit=1)

    first = registry.list_entries(context, "raw")[0]
    repeated = registry.list_entries(context, "raw")[0]
    (raw / "b.bin").write_bytes(b"b")
    registry.list_entries(context, "raw")

    assert repeated.id == first.id
    with pytest.raises(KeyError):
        registry.resolve(first.id, context)


def test_cleanup_preview_limit_is_enforced(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.workspace.raw.mkdir(parents=True)
    registry = FileRegistry(preview_limit=1)
    registry.preview_cleanup(context, "context-1", ["raw"])

    with pytest.raises(CleanupPreviewLimitError):
        registry.preview_cleanup(context, "context-1", ["raw"])


def test_cleanup_targets_are_relative_and_revalidated(tmp_path: Path) -> None:
    context = _context(tmp_path)
    raw = context.workspace.raw
    raw.mkdir(parents=True)
    target_path = raw / "asset.bin"
    target_path.write_bytes(b"payload")
    preview = FileRegistry().preview_cleanup(context, "context-1", ["raw"])

    assert preview.targets[0].relative_path == "asset.bin"
    BoundedStorageCleanup().delete(context, preview.targets[0])
    assert not target_path.exists()


def test_file_registry_rejects_path_traversal(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.workspace.raw.mkdir(parents=True)

    with pytest.raises(FileBoundaryError):
        FileRegistry().list_entries(context, "raw", "../outside")


def test_file_registry_rejects_symlink_escape(tmp_path: Path) -> None:
    context = _context(tmp_path)
    raw = context.workspace.raw
    outside = tmp_path / "outside"
    raw.mkdir(parents=True)
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = raw / "escape"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable in this environment.")

    with pytest.raises(FileBoundaryError):
        FileRegistry().list_entries(context, "raw")


def test_cleanup_rejects_symlink_replaced_after_preview(tmp_path: Path) -> None:
    context = _context(tmp_path)
    raw = context.workspace.raw
    outside = tmp_path / "outside.txt"
    raw.mkdir(parents=True)
    outside.write_text("secret", encoding="utf-8")
    target = raw / "asset.bin"
    target.write_text("payload", encoding="utf-8")
    preview = FileRegistry().preview_cleanup(context, "context-1", ["raw"])
    target.unlink()
    try:
        os.symlink(outside, target)
    except OSError:
        pytest.skip("File symlinks are unavailable in this environment.")

    with pytest.raises(StorageBoundaryError):
        BoundedStorageCleanup().delete(context, preview.targets[0])
    assert outside.read_text(encoding="utf-8") == "secret"


def test_old_snapshot_preview_protects_current_runtime_and_schema(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path).resolve_resource_version("current-runtime")
    state = context.workspace.state
    for version in ("current-runtime", "old-runtime"):
        root = state / "runtime" / version
        root.mkdir(parents=True)
        (root / "version.json").write_text("{}", encoding="utf-8")
    schema = state / "schema"
    (schema / "snapshots" / "current-schema").mkdir(parents=True)
    (schema / "snapshots" / "old-schema").mkdir(parents=True)
    (schema / "current.json").write_text(
        '{"snapshot_id":"current-schema"}', encoding="utf-8"
    )

    preview = FileRegistry().preview_cleanup(context, "context-1", ["old-snapshots"])
    paths = {target.relative_path for target in preview.targets}

    assert any("old-runtime" in path for path in paths)
    assert any("old-schema" in path for path in paths)
    assert all("current-runtime" not in path for path in paths)
    assert all("current-schema" not in path for path in paths)
