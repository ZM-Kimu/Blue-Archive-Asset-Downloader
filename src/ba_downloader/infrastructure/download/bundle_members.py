from __future__ import annotations

import os
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetRecord,
    AssetType,
    ChecksumSpec,
)
from ba_downloader.domain.models.bundle import bundle_member_cache_resource_path
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.files.checksum import calculate_crc
from ba_downloader.infrastructure.packages.zip_range_reader import ZipEntry

BUNDLE_MEMBER_SOURCE = "jp_bundle_member"


@dataclass(frozen=True, slots=True)
class BundleMemberDownloadPlan:
    primary: AssetCollection
    aliases: Mapping[str, tuple[AssetRecord, ...]]
    all_members: tuple[AssetRecord, ...]


def is_bundle_member_selection(resource: AssetRecord) -> bool:
    return resource.asset_type is AssetType.bundle and bool(
        resource.selected_member_paths
    )


def member_cache_path(
    context: ExecutionContext,
    archive: AssetRecord,
    member_path: str,
) -> Path:
    relative = bundle_member_cache_resource_path(archive.path, member_path)
    destination = context.workspace.raw_resource_path(AssetType.bundle.value, relative)
    root = context.workspace.raw_bundles.resolve(strict=False)
    resolved = destination.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("Bundle member cache path escapes the raw bundle directory.")
    return resolved


def build_member_download_plan(
    archives: Sequence[AssetRecord],
    entries_by_archive: Mapping[str, Sequence[ZipEntry]],
    *,
    range_enabled_by_archive: Mapping[str, bool],
) -> BundleMemberDownloadPlan:
    all_members: list[AssetRecord] = []
    primary_by_identity: dict[tuple[str, int, int], AssetRecord] = {}
    aliases: dict[str, list[AssetRecord]] = {}

    for archive in archives:
        selected = archive.selected_member_paths or ()
        entries = entries_by_archive.get(archive.path.casefold(), ())
        for member_path in selected:
            entry = find_exact_entry(entries, member_path)
            member = _member_record(
                archive,
                entry,
                range_enabled=range_enabled_by_archive.get(
                    archive.path.casefold(), False
                ),
            )
            all_members.append(member)
            identity = (
                entry.path.replace("\\", "/").casefold(),
                entry.crc32,
                entry.uncompressed_size,
            )
            primary = primary_by_identity.get(identity)
            if primary is None:
                primary_by_identity[identity] = member
            else:
                aliases.setdefault(primary.path, []).append(member)

    return BundleMemberDownloadPlan(
        primary=AssetCollection(primary_by_identity.values()),
        aliases={key: tuple(value) for key, value in aliases.items()},
        all_members=tuple(all_members),
    )


def read_local_zip_entries(path: Path) -> tuple[ZipEntry, ...]:
    with zipfile.ZipFile(path) as archive:
        return tuple(_entry_from_zip_info(info) for info in archive.infolist())


def extract_local_bundle_member(
    archive_path: Path,
    entry: ZipEntry,
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            matches = [
                info
                for info in archive.infolist()
                if info.filename.replace("\\", "/").casefold()
                == entry.path.replace("\\", "/").casefold()
            ]
            if len(matches) != 1 or matches[0].is_dir():
                raise RuntimeError(
                    f"Local ZIP member {entry.path!r} is missing or ambiguous."
                )
            with archive.open(matches[0]) as source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output)
        if temporary.stat().st_size != entry.uncompressed_size:
            raise RuntimeError(f"Local ZIP member {entry.path!r} has an invalid size.")
        if calculate_crc(str(temporary)) != entry.crc32:
            raise RuntimeError(
                f"Local ZIP member {entry.path!r} failed CRC validation."
            )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def materialize_member_alias(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        try:
            os.link(source, temporary)
        except OSError:
            shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _member_record(
    archive: AssetRecord,
    entry: ZipEntry,
    *,
    range_enabled: bool,
) -> AssetRecord:
    return AssetRecord(
        url=archive.url,
        path=bundle_member_cache_resource_path(archive.path, entry.path),
        size=entry.uncompressed_size,
        checksum=ChecksumSpec("crc", str(entry.crc32)),
        asset_type=AssetType.bundle,
        metadata={
            "source": BUNDLE_MEMBER_SOURCE,
            "zip_entry": entry,
            "archive_resource": archive,
            "range_enabled": range_enabled,
            "transfer_size": entry.compressed_size + 30,
        },
    )


def find_exact_entry(entries: Sequence[ZipEntry], member_path: str) -> ZipEntry:
    normalized = member_path.replace("\\", "/").casefold()
    matches = [
        entry
        for entry in entries
        if entry.path.replace("\\", "/").casefold() == normalized
    ]
    if len(matches) != 1 or matches[0].path.endswith(("/", "\\")):
        raise RuntimeError(f"ZIP member {member_path!r} is missing or ambiguous.")
    return matches[0]


def _entry_from_zip_info(info: zipfile.ZipInfo) -> ZipEntry:
    return ZipEntry(
        path=info.filename.replace("\\", "/"),
        crc32=info.CRC,
        local_header_offset=info.header_offset,
        compressed_size=info.compress_size,
        uncompressed_size=info.file_size,
        compression_method=info.compress_type,
        file_name_length=len(info.filename.encode("utf8")),
        extra_field_length=len(info.extra),
        flags=info.flag_bits,
    )
