from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleEntryInput,
)
from ba_downloader.infrastructure.files.atomic import write_json_atomic

DEFAULT_ENTRY_CACHE_RESERVE_BYTES = 8 * 1024 * 1024 * 1024
MIN_ENTRY_CACHE_RESERVE_BYTES = 512 * 1024 * 1024


class BundleEntryStoreSpaceError(OSError):
    pass


@dataclass(frozen=True, slots=True)
class BundleEntryStoreResult:
    path: Path
    hit: bool
    bytes_written: int


def bundle_entry_store_root(context: ExecutionContext) -> Path:
    return context.workspace.cache_state / "assetripper" / "entries"


class BundleEntryStore:
    def __init__(
        self,
        root: Path,
        *,
        cancellation: CancellationPort | None = None,
        reserve_bytes: int = DEFAULT_ENTRY_CACHE_RESERVE_BYTES,
    ) -> None:
        if reserve_bytes < 0:
            raise ValueError("Bundle entry cache reserve must not be negative.")
        self._root = root
        self._cancellation = cancellation or NeverCancelled()
        self._reserve_bytes = reserve_bytes

    def resolve(self, entry: BundleEntryInput) -> BundleEntryStoreResult:
        return self.resolve_many((entry,))[0]

    def resolve_many(
        self,
        entries: Sequence[BundleEntryInput],
    ) -> tuple[BundleEntryStoreResult, ...]:
        self._cancellation.raise_if_cancelled()
        results: list[BundleEntryStoreResult | None] = [None] * len(entries)
        misses_by_archive: dict[Path, list[tuple[int, BundleEntryInput]]] = defaultdict(
            list
        )
        required_bytes = 0
        for index, entry in enumerate(entries):
            destination = self._path_for(entry)
            marker = destination.with_suffix(f"{destination.suffix}.json")
            if self._is_valid_hit(destination, marker, entry):
                results[index] = BundleEntryStoreResult(destination, True, 0)
                continue
            misses_by_archive[entry.archive.path].append((index, entry))
            required_bytes += entry.size

        if misses_by_archive:
            self._root.mkdir(parents=True, exist_ok=True)
            self._ensure_space(required_bytes)
        for archive_path, misses in misses_by_archive.items():
            self._cancellation.raise_if_cancelled()
            with zipfile.ZipFile(archive_path) as archive:
                for index, entry in misses:
                    results[index] = self._materialize(archive, entry)

        if any(result is None for result in results):
            raise RuntimeError("Bundle entry cache did not resolve every input.")
        return tuple(result for result in results if result is not None)

    def _materialize(
        self,
        archive: zipfile.ZipFile,
        entry: BundleEntryInput,
    ) -> BundleEntryStoreResult:
        self._cancellation.raise_if_cancelled()
        destination = self._path_for(entry)
        marker = destination.with_suffix(f"{destination.suffix}.json")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            digest = hashlib.sha256()
            written = 0
            info = archive.getinfo(entry.entry_path)
            if info.is_dir() or info.file_size != entry.size:
                raise ValueError(
                    f"Bundle entry changed after dependency scanning: {entry.node_id}"
                )
            with archive.open(info) as source, temporary.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    self._cancellation.raise_if_cancelled()
                    target.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)
            if written != entry.size or digest.hexdigest() != entry.sha256:
                raise ValueError(
                    f"Bundle entry changed after dependency scanning: {entry.node_id}"
                )
            temporary.replace(destination)
            stat = destination.stat()
            write_json_atomic(
                marker,
                {
                    "sha256": entry.sha256,
                    "size": entry.size,
                    "mtime_ns": stat.st_mtime_ns,
                },
                sort_keys=True,
            )
            return BundleEntryStoreResult(destination, False, written)
        finally:
            temporary.unlink(missing_ok=True)

    def _path_for(self, entry: BundleEntryInput) -> Path:
        digest = entry.sha256.lower()
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError("Bundle entry SHA-256 is invalid.")
        filename = PurePosixPath(entry.entry_path).name
        if (
            not filename
            or filename in {".", ".."}
            or any(character in filename for character in ("\\", ":", "\0"))
            or filename.endswith((" ", "."))
            or any(ord(character) < 32 for character in filename)
        ):
            raise ValueError(f"Bundle entry has an unsafe filename: {entry.node_id}")
        return self._root / digest[:2] / digest / filename

    @staticmethod
    def _is_valid_hit(
        destination: Path,
        marker: Path,
        entry: BundleEntryInput,
    ) -> bool:
        try:
            payload = json.loads(marker.read_text(encoding="utf8"))
            stat = destination.stat()
        except (OSError, ValueError):
            return False
        return (
            isinstance(payload, dict)
            and payload.get("sha256") == entry.sha256
            and payload.get("size") == entry.size
            and payload.get("mtime_ns") == stat.st_mtime_ns
            and stat.st_size == entry.size
        )

    def _ensure_space(self, required_bytes: int) -> None:
        usage = shutil.disk_usage(self._root)
        effective_reserve = (
            0
            if self._reserve_bytes == 0
            else min(
                self._reserve_bytes,
                max(MIN_ENTRY_CACHE_RESERVE_BYTES, usage.free // 10),
            )
        )
        free = usage.free
        required = effective_reserve + required_bytes
        if free < required:
            raise BundleEntryStoreSpaceError(
                "Insufficient disk space for the AssetRipper entry cache: "
                f"requires {required} free bytes including the safety reserve, "
                f"but only {free} bytes are available."
            )
