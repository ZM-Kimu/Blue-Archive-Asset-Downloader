from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleEntryInput,
)
from ba_downloader.infrastructure.extraction.assetripper.entry_store import (
    BundleEntryStore,
    bundle_entry_cache_identity,
)
from ba_downloader.infrastructure.files.atomic import write_json_atomic
from support.fixtures import build_execution_context


class RecordingMaterializer:
    def __init__(self) -> None:
        self.calls = 0

    def materialize_entries(
        self,
        context: ExecutionContext,
        entries: list[BundleEntryInput],
        destinations: dict[str, Path],
        *,
        concurrency: int,
        event_callback=None,
    ) -> dict[str, int]:
        _ = (context, concurrency, event_callback)
        self.calls += 1
        result: dict[str, int] = {}
        for entry in entries:
            destination = destinations[entry.node_id]
            destination.parent.mkdir(parents=True, exist_ok=True)
            with ZipFile(entry.archive.path) as archive:
                payload = archive.read(entry.entry_path)
            destination.write_bytes(payload)
            stat = destination.stat()
            write_json_atomic(
                destination.with_suffix(f"{destination.suffix}.json"),
                {
                    "schema_version": 2,
                    "identity": bundle_entry_cache_identity(entry),
                    "mtime_ns": stat.st_mtime_ns,
                },
                sort_keys=True,
            )
            result[entry.node_id] = len(payload)
        return result


def _entry(tmp_path: Path, payload: bytes = b"bundle-data") -> BundleEntryInput:
    archive_path = tmp_path / "archive.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/asset.bundle", payload)
    archive = BundleArchiveInput.from_path(archive_path, archive_id="archive.zip")
    return BundleEntryInput(
        archive=archive,
        entry_path="nested/asset.bundle",
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )


def test_entry_store_materializes_all_misses_once_and_reuses_verified_content(
    tmp_path: Path,
) -> None:
    materializer = RecordingMaterializer()
    store = BundleEntryStore(
        tmp_path / "cache",
        materializer=materializer,
    )
    context = build_execution_context(tmp_path)
    entry = _entry(tmp_path)

    first = store.resolve_many(context, (entry,), concurrency=4)[0]
    second = store.resolve_many(context, (entry,), concurrency=4)[0]

    assert first.path == second.path
    assert first.path.read_bytes() == b"bundle-data"
    assert first.hit is False
    assert second.hit is True
    assert materializer.calls == 1


def test_entry_store_rebuilds_corrupted_cache_entry(tmp_path: Path) -> None:
    materializer = RecordingMaterializer()
    store = BundleEntryStore(
        tmp_path / "cache",
        materializer=materializer,
    )
    context = build_execution_context(tmp_path)
    entry = _entry(tmp_path)
    cached = store.resolve_many(context, (entry,), concurrency=1)[0]
    cached.path.write_bytes(b"corrupt")

    rebuilt = store.resolve_many(context, (entry,), concurrency=1)[0]

    assert rebuilt.hit is False
    assert rebuilt.path.read_bytes() == b"bundle-data"
    assert materializer.calls == 2


@pytest.mark.parametrize(
    "entry_path",
    [r"..\..\outside.bundle", "unsafe:name.bundle"],
)
def test_entry_store_rejects_platform_unsafe_entry_names(
    tmp_path: Path,
    entry_path: str,
) -> None:
    payload = b"bundle-data"
    archive_path = tmp_path / "archive.zip"
    with ZipFile(archive_path, "w") as archive_file:
        archive_file.writestr(entry_path, payload)
    archive = BundleArchiveInput.from_path(archive_path, archive_id="archive.zip")
    entry = BundleEntryInput(
        archive=archive,
        entry_path=entry_path,
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )
    store = BundleEntryStore(
        tmp_path / "cache",
        materializer=RecordingMaterializer(),
    )

    with pytest.raises(ValueError):
        store.resolve_many(
            build_execution_context(tmp_path),
            (entry,),
            concurrency=1,
        )
