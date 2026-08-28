from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from ba_downloader.domain.models.asset import AssetRecord, AssetType, ChecksumSpec
from ba_downloader.infrastructure.download.bundle_members import (
    build_member_download_plan,
    extract_local_bundle_member,
    read_local_zip_entries,
)


def test_member_plan_deduplicates_identical_patch_content_with_aliases(
    tmp_path: Path,
) -> None:
    archive_bytes = _zip_bytes({"characters/ibuki.bundle": b"same"})
    first_path = tmp_path / "FullPatch_001.zip"
    second_path = tmp_path / "FullPatch_002.zip"
    first_path.write_bytes(archive_bytes)
    second_path.write_bytes(archive_bytes)
    first = _archive("Bundle/FullPatch_001.zip")
    second = _archive("Bundle/FullPatch_002.zip")
    first_entries = read_local_zip_entries(first_path)
    second_entries = read_local_zip_entries(second_path)

    plan = build_member_download_plan(
        [first, second],
        {
            first.path.casefold(): first_entries,
            second.path.casefold(): second_entries,
        },
        range_enabled_by_archive={
            first.path.casefold(): True,
            second.path.casefold(): True,
        },
    )

    assert len(plan.primary) == 1
    assert len(plan.all_members) == 2
    assert list(plan.aliases) == [plan.primary[0].path]
    assert len(plan.aliases[plan.primary[0].path]) == 1


def test_local_member_extraction_validates_before_replacing_destination(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "FullPatch.zip"
    archive_path.write_bytes(_zip_bytes({"characters/ibuki.bundle": b"payload"}))
    entry = read_local_zip_entries(archive_path)[0]
    destination = tmp_path / "cache" / "ibuki.bundle"
    destination.parent.mkdir()
    destination.write_bytes(b"old")

    extract_local_bundle_member(archive_path, entry, destination)

    assert destination.read_bytes() == b"payload"
    assert not tuple(destination.parent.glob(".ibuki.bundle.*.tmp"))


def _archive(path: str) -> AssetRecord:
    return AssetRecord(
        "https://cdn.example/" + path,
        path,
        100,
        ChecksumSpec("crc", "0"),
        AssetType.bundle,
        member_paths=("characters/ibuki.bundle",),
        selected_member_paths=("characters/ibuki.bundle",),
    )


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return stream.getvalue()
