from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleEntryInput,
)
from ba_downloader.infrastructure.extraction.assetripper.entry_store import (
    BundleEntryStore,
)


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


def test_entry_store_extracts_once_and_reuses_verified_content(
    tmp_path: Path,
) -> None:
    store = BundleEntryStore(tmp_path / "cache", reserve_bytes=0)
    entry = _entry(tmp_path)

    first = store.resolve(entry)
    second = store.resolve(entry)

    assert first.path == second.path
    assert first.path.read_bytes() == b"bundle-data"
    assert first.hit is False
    assert first.bytes_written == len(b"bundle-data")
    assert second.hit is True
    assert second.bytes_written == 0


def test_entry_store_rebuilds_corrupted_cache_entry(tmp_path: Path) -> None:
    store = BundleEntryStore(tmp_path / "cache", reserve_bytes=0)
    entry = _entry(tmp_path)
    cached = store.resolve(entry)
    cached.path.write_bytes(b"corrupt")

    rebuilt = store.resolve(entry)

    assert rebuilt.hit is False
    assert rebuilt.path.read_bytes() == b"bundle-data"


def test_entry_store_resolves_archive_entries_with_one_zip_open(
    tmp_path: Path,
    monkeypatch,
) -> None:
    archive_path = tmp_path / "archive.zip"
    payloads = {"a.bundle": b"a", "b.bundle": b"b"}
    with ZipFile(archive_path, "w") as archive_file:
        for name, payload in payloads.items():
            archive_file.writestr(name, payload)
    archive = BundleArchiveInput.from_path(archive_path, archive_id="archive.zip")
    entries = tuple(
        BundleEntryInput(
            archive=archive,
            entry_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
        )
        for name, payload in payloads.items()
    )
    store = BundleEntryStore(tmp_path / "cache", reserve_bytes=0)
    real_zip_file = ZipFile
    opens = 0

    def recording_zip_file(*args, **kwargs):
        nonlocal opens
        opens += 1
        return real_zip_file(*args, **kwargs)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.extraction.assetripper.entry_store.zipfile.ZipFile",
        recording_zip_file,
    )

    result = store.resolve_many(entries)

    assert [item.path.read_bytes() for item in result] == [b"a", b"b"]
    assert opens == 1


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
    store = BundleEntryStore(tmp_path / "cache", reserve_bytes=0)

    with pytest.raises(ValueError):
        store.resolve(entry)
