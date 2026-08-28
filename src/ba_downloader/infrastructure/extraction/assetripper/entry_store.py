from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleEntryInput,
)
from ba_downloader.infrastructure.extraction.assetripper.events import (
    AssetRipperProcessEvent,
)
from ba_downloader.infrastructure.files.atomic import write_json_atomic
from ba_downloader.infrastructure.files.checksum import calculate_sha256
from ba_downloader.infrastructure.files.size import format_file_size

_ENTRY_CACHE_SCHEMA_VERSION = 0


def bundle_entry_cache_identity(entry: BundleEntryInput) -> dict[str, object]:
    checksum = entry.archive.checksum
    return {
        "cache_schema": _ENTRY_CACHE_SCHEMA_VERSION,
        "archive_id": entry.archive.archive_id,
        "archive_checksum": (
            {"algorithm": checksum.algorithm, "value": checksum.value}
            if checksum is not None
            else None
        ),
        "entry_path": PurePosixPath(entry.entry_path).as_posix(),
        "sha256": entry.sha256.lower(),
        "size": entry.size,
        "crc32": entry.crc32,
    }


class BundleEntryStoreSpaceError(OSError):
    pass


@dataclass(frozen=True, slots=True)
class BundleEntryStoreResult:
    path: Path
    hit: bool
    bytes_written: int


class BundleEntryMaterializerPort(Protocol):
    def materialize_entries(
        self,
        context: ExecutionContext,
        entries: list[BundleEntryInput],
        destinations: dict[str, Path],
        *,
        concurrency: int,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> dict[str, int]: ...


def bundle_entry_store_root(context: ExecutionContext) -> Path:
    return context.workspace.cache_state / "assetripper" / "entries"


class BundleEntryStore:
    def __init__(
        self,
        root: Path,
        *,
        materializer: BundleEntryMaterializerPort,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self._root = root
        self._materializer = materializer
        self._cancellation = cancellation or NeverCancelled()

    def resolve_many(
        self,
        context: ExecutionContext,
        entries: Sequence[BundleEntryInput],
        *,
        concurrency: int,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> tuple[BundleEntryStoreResult, ...]:
        self._cancellation.raise_if_cancelled()
        results: list[BundleEntryStoreResult | None] = [None] * len(entries)
        misses: list[tuple[int, BundleEntryInput]] = []
        required_bytes = 0
        for index, entry in enumerate(entries):
            destination = self._path_for(entry)
            marker = destination.with_suffix(f"{destination.suffix}.json")
            if self._is_valid_hit(destination, marker, entry):
                results[index] = BundleEntryStoreResult(destination, True, 0)
                continue
            misses.append((index, entry))
            required_bytes += entry.size

        if misses:
            self._root.mkdir(parents=True, exist_ok=True)
            self._ensure_space(required_bytes)
            destination_by_node = {
                entry.node_id: self._path_for(entry) for _, entry in misses
            }
            try:
                written_by_node = self._materializer.materialize_entries(
                    context,
                    [entry for _, entry in misses],
                    destination_by_node,
                    concurrency=concurrency,
                    event_callback=event_callback,
                )
            finally:
                for destination in destination_by_node.values():
                    for temporary in destination.parent.glob(
                        f"{destination.name}.*.tmp"
                    ):
                        temporary.unlink(missing_ok=True)
            for index, entry in misses:
                destination = destination_by_node[entry.node_id]
                marker = destination.with_suffix(f"{destination.suffix}.json")
                if written_by_node.get(entry.node_id) != entry.size:
                    raise RuntimeError(
                        f"Bundle entry cache wrote an unexpected size: {entry.node_id}"
                    )
                self._write_marker(destination, marker, entry)
                if not self._is_valid_hit(destination, marker, entry):
                    raise RuntimeError(
                        f"Bundle entry cache did not publish a valid entry: {entry.node_id}"
                    )
                results[index] = BundleEntryStoreResult(
                    destination,
                    False,
                    written_by_node[entry.node_id],
                )

        if any(result is None for result in results):
            raise RuntimeError("Bundle entry cache did not resolve every input.")
        return tuple(result for result in results if result is not None)

    def path_for(self, entry: BundleEntryInput) -> Path:
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
        identity = bundle_entry_cache_identity(entry)
        cache_key = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return self._root / cache_key[:2] / cache_key / filename

    _path_for = path_for

    def _is_valid_hit(
        self,
        destination: Path,
        marker: Path,
        entry: BundleEntryInput,
    ) -> bool:
        try:
            payload = json.loads(marker.read_text(encoding="utf8"))
            stat = destination.stat()
        except (OSError, ValueError):
            return False
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _ENTRY_CACHE_SCHEMA_VERSION
            or payload.get("identity") != bundle_entry_cache_identity(entry)
            or stat.st_size != entry.size
        ):
            return False
        if payload.get("mtime_ns") == stat.st_mtime_ns:
            return True
        try:
            actual_sha256 = calculate_sha256(
                destination,
                on_chunk=self._cancellation.raise_if_cancelled,
            )
        except OSError:
            return False
        if actual_sha256 != entry.sha256.lower():
            return False
        self._write_marker(destination, marker, entry)
        return True

    @staticmethod
    def _write_marker(
        destination: Path,
        marker: Path,
        entry: BundleEntryInput,
    ) -> None:
        stat = destination.stat()
        if stat.st_size != entry.size:
            raise RuntimeError(
                f"Bundle entry cache wrote an unexpected size: {entry.node_id}"
            )
        write_json_atomic(
            marker,
            {
                "schema_version": _ENTRY_CACHE_SCHEMA_VERSION,
                "identity": bundle_entry_cache_identity(entry),
                "mtime_ns": stat.st_mtime_ns,
            },
            sort_keys=True,
        )

    def _ensure_space(self, required_bytes: int) -> None:
        usage = shutil.disk_usage(self._root)
        if usage.free < required_bytes:
            raise BundleEntryStoreSpaceError(
                "Insufficient disk space for the AssetRipper entry cache: "
                f"requires {format_file_size(required_bytes)} of new data, but only "
                f"{format_file_size(usage.free)} is available."
            )
