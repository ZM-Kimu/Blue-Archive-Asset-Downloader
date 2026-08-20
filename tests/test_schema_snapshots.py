from __future__ import annotations

import json
from pathlib import Path

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.models.schema import SchemaPurpose
from ba_downloader.infrastructure.schema.snapshots import (
    SCHEMA_TOOL_VERSIONS,
    SchemaSnapshotStore,
)
from support.fixtures import build_execution_context


def _context(tmp_path: Path, version: str = "1.2.3") -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="jp",
        platform="android",
        version=version,
        max_retries=0,
    )


def _runtime(tmp_path: Path, version: str = "1.2.3") -> PreparedRuntimeAssets:
    root = tmp_path / "runtime" / version
    root.mkdir(parents=True)
    binary = root / "libil2cpp.so"
    metadata = root / "global-metadata.dat"
    managers = root / "globalgamemanagers"
    binary.write_bytes(f"binary-{version}".encode())
    metadata.write_bytes(f"metadata-{version}".encode())
    managers.write_bytes(f"managers-{version}".encode())
    return PreparedRuntimeAssets(version, root, binary, metadata, managers)


def _write_artifacts(root: Path, marker: str) -> None:
    for relative in (
        "dumps/dump.cs",
        "schemas/flatbuffers/schema.py",
        "schemas/memorypack/schema.py",
        "diagnostics/memorypack-layouts.json",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(marker, encoding="utf8")


def test_schema_snapshot_publishes_typed_manifest_and_current_pointer(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    runtime = _runtime(tmp_path)
    store = SchemaSnapshotStore()
    fingerprint = store.fingerprint(context, runtime)

    with store.staging(context, fingerprint) as staging:
        _write_artifacts(staging, "current")
        snapshot = store.publish(context, runtime, fingerprint, staging)

    pointer = json.loads(store.current_pointer(context).read_text(encoding="utf8"))
    assert pointer == {
        "schema_version": 2,
        "snapshot_id": fingerprint,
        "purpose": "full",
    }
    assert snapshot.manifest.fingerprint == fingerprint
    assert snapshot.manifest.runtime_version == "1.2.3"
    assert store.load(context, fingerprint) == snapshot


def test_schema_snapshot_cache_invalidates_when_runtime_input_changes(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    runtime = _runtime(tmp_path)
    store = SchemaSnapshotStore()

    first = store.fingerprint(context, runtime)
    runtime.metadata_path.write_bytes(b"changed")
    second = store.fingerprint(context, runtime)

    assert first != second


def test_schema_snapshot_cache_invalidates_previous_memorypack_layouts(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    runtime = _runtime(tmp_path)
    previous_versions = {
        **SCHEMA_TOOL_VERSIONS,
        "memorypack_generator": "1",
        "schema_workflow": "1",
    }

    current = SchemaSnapshotStore().fingerprint(context, runtime)
    previous = SchemaSnapshotStore(tool_versions=previous_versions).fingerprint(
        context,
        runtime,
    )

    assert current != previous


def test_schema_snapshot_retains_current_and_previous_and_cleans_staging(
    tmp_path: Path,
) -> None:
    store = SchemaSnapshotStore(retained_snapshots=2)
    context = _context(tmp_path)
    abandoned = store.staging_root(context) / "abandoned"
    abandoned.mkdir(parents=True)
    store.cleanup(context)
    assert not abandoned.exists()

    snapshot_ids: list[str] = []
    for version in ("1", "2", "3"):
        active_context = _context(tmp_path, version)
        runtime = _runtime(tmp_path, version)
        fingerprint = store.fingerprint(active_context, runtime)
        snapshot_ids.append(fingerprint)
        with store.staging(active_context, fingerprint) as staging:
            _write_artifacts(staging, version)
            store.publish(active_context, runtime, fingerprint, staging)

    retained = {path.name for path in store.snapshots_root(context).iterdir()}
    assert retained == set(snapshot_ids[-2:])


def test_character_index_schema_snapshot_isolated_from_full_and_has_no_dump(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    runtime = _runtime(tmp_path)
    store = SchemaSnapshotStore()
    targets = ("CharacterExcel", "LocalizeCharProfileExcel")
    fingerprint = store.fingerprint(
        context,
        runtime,
        SchemaPurpose.CHARACTER_INDEX,
        targets,
    )
    with store.staging(context, fingerprint, SchemaPurpose.CHARACTER_INDEX) as staging:
        schema_file = staging / "schemas" / "flatbuffers" / "schema.py"
        schema_file.parent.mkdir(parents=True)
        schema_file.write_text("value = 1\n", encoding="utf8")
        (staging / "diagnostics").mkdir()
        snapshot = store.publish(
            context,
            runtime,
            fingerprint,
            staging,
            SchemaPurpose.CHARACTER_INDEX,
            targets,
        )

    assert snapshot.manifest.purpose == "character_index"
    assert snapshot.manifest.target_types == tuple(sorted(targets))
    assert not (snapshot.root / "dumps").exists()
    assert not (snapshot.root / "schemas" / "memorypack").exists()
    assert store.snapshots_root(context, SchemaPurpose.CHARACTER_INDEX) != (
        store.snapshots_root(context, SchemaPurpose.FULL)
    )
