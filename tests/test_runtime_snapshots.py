from pathlib import Path

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.infrastructure.runtime import (
    RuntimeSnapshotError,
    RuntimeSnapshotStore,
)
from support import build_runtime_context


def _publish_snapshot(
    store: RuntimeSnapshotStore,
    context: RuntimeContext,
    version: str,
    *,
    marker: bytes,
) -> PreparedRuntimeAssets:
    with store.staging_runtime(context, version) as runtime_dir:
        (runtime_dir / "libil2cpp.so").write_bytes(b"binary-" + marker)
        (runtime_dir / "global-metadata.dat").write_bytes(b"metadata-" + marker)
        (runtime_dir / "globalgamemanagers").write_bytes(b"unity-" + marker)
        return store.publish(
            context,
            version,
            runtime_dir,
            binary_name="libil2cpp.so",
            metadata_name="global-metadata.dat",
            globalgamemanagers_name="globalgamemanagers",
        )


def test_runtime_snapshot_validates_manifest_hashes(tmp_path: Path) -> None:
    context = build_runtime_context(tmp_path, region="gl", version="1.2.3")
    store = RuntimeSnapshotStore()
    prepared = _publish_snapshot(store, context, "1.2.3", marker=b"current")

    assert store.load(context, "1.2.3") == prepared

    prepared.binary_path.write_bytes(b"corrupted")

    assert store.load(context, "1.2.3") is None


def test_runtime_snapshot_failed_publish_preserves_same_version(
    tmp_path: Path,
) -> None:
    context = build_runtime_context(tmp_path, region="gl", version="1.2.3")
    store = RuntimeSnapshotStore()
    original = _publish_snapshot(store, context, "1.2.3", marker=b"original")

    with (
        pytest.raises(RuntimeSnapshotError, match="required metadata"),
        store.staging_runtime(context, "1.2.3") as runtime_dir,
    ):
        (runtime_dir / "libil2cpp.so").write_bytes(b"replacement")
        store.publish(
            context,
            "1.2.3",
            runtime_dir,
            binary_name="libil2cpp.so",
            metadata_name="global-metadata.dat",
        )

    assert store.load(context, "1.2.3") == original


def test_runtime_snapshot_retains_current_and_previous_versions(
    tmp_path: Path,
) -> None:
    context = build_runtime_context(tmp_path, region="cn", version="2.1.2")
    store = RuntimeSnapshotStore(retained_versions=2)

    _publish_snapshot(store, context, "2.1.0", marker=b"oldest")
    _publish_snapshot(store, context, "2.1.1", marker=b"previous")
    _publish_snapshot(store, context, "2.1.2", marker=b"current")

    assert not (Path(context.temp_dir) / "2.1.0").exists()
    assert (Path(context.temp_dir) / "2.1.1" / "Runtime").is_dir()
    assert (Path(context.temp_dir) / "2.1.2" / "Runtime").is_dir()


def test_versioned_package_directories_use_the_same_retention_policy(
    tmp_path: Path,
) -> None:
    context = build_runtime_context(tmp_path, region="jp", version="1.2.3")
    store = RuntimeSnapshotStore(retained_versions=2)

    for version in ("1.2.1", "1.2.2", "1.2.3"):
        with store.staging_directory(
            context,
            version,
            directory_name="Package",
        ) as package_dir:
            (package_dir / "release.xapk").write_bytes(version.encode("ascii"))
            store.publish_directory(
                context,
                version,
                package_dir,
                directory_name="Package",
            )

    assert not (Path(context.temp_dir) / "1.2.1").exists()
    assert (Path(context.temp_dir) / "1.2.2" / "Package").is_dir()
    assert (Path(context.temp_dir) / "1.2.3" / "Package").is_dir()


def test_v3_runtime_snapshots_use_dedicated_state_directory(tmp_path: Path) -> None:
    temp_dir = tmp_path / "cn" / "android" / ".state" / "temp"
    context = build_runtime_context(
        tmp_path,
        region="cn",
        version="2.1.2",
        temp_dir=str(temp_dir),
        workspace_mode="v3",
    )

    prepared = _publish_snapshot(
        RuntimeSnapshotStore(), context, "2.1.2", marker=b"current"
    )

    assert prepared.root_dir == (temp_dir.parent / "runtime" / "2.1.2" / "Runtime")
