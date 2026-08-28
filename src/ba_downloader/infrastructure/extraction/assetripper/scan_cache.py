from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
    BundleEntryScan,
    SerializedFileScan,
    StreamedResourceScan,
)
from ba_downloader.infrastructure.files.atomic import write_json_atomic

SCAN_CACHE_SCHEMA_VERSION = 0


def dependency_scan_cache_root(context: ExecutionContext) -> Path:
    return context.workspace.cache_state / "assetripper" / "dependency-scans"


class BundleDependencyScanCache:
    def __init__(self, root: Path) -> None:
        self._root = root

    def path_for(self, archive: BundleArchiveInput, *, tool_key: str) -> Path:
        identity = {
            "cache_schema": SCAN_CACHE_SCHEMA_VERSION,
            "tool_key": tool_key,
            "archive": self._identity(archive),
        }
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return self._root / digest[:2] / f"{digest}.json"

    def load(
        self,
        archive: BundleArchiveInput,
        *,
        tool_key: str,
    ) -> BundleArchiveScan | None:
        try:
            payload = json.loads(
                self.path_for(archive, tool_key=tool_key).read_text(encoding="utf8")
            )
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version") != SCAN_CACHE_SCHEMA_VERSION
                or payload.get("tool_key") != tool_key
                or payload.get("identity") != self._identity(archive)
            ):
                return None
            scan_payload = payload.get("scan")
            if not isinstance(scan_payload, dict):
                return None
            scan = self._read_scan(scan_payload)
            if scan.archive_id != archive.archive_id:
                return None
            return scan
        except (KeyError, OSError, TypeError, ValueError):
            return None

    def store(
        self,
        archive: BundleArchiveInput,
        scan: BundleArchiveScan,
        *,
        tool_key: str,
    ) -> None:
        if scan.archive_id != archive.archive_id:
            raise ValueError("Dependency scan result does not match bundle input.")
        path = self.path_for(archive, tool_key=tool_key)
        write_json_atomic(
            path,
            {
                "schema_version": SCAN_CACHE_SCHEMA_VERSION,
                "tool_key": tool_key,
                "identity": self._identity(archive),
                "scan": self._write_scan(scan),
            },
            indent=2,
            sort_keys=True,
        )

    @staticmethod
    def _identity(archive: BundleArchiveInput) -> dict[str, object]:
        if archive.checksum is not None:
            return {
                "kind": "catalog",
                "archive_id": archive.archive_id,
                "size": archive.size,
                "checksum_algorithm": archive.checksum.algorithm,
                "checksum_value": archive.checksum.value,
            }
        return {
            "kind": "local",
            "path": str(archive.path),
            "size": archive.size,
            "mtime_ns": archive.mtime_ns,
        }

    @staticmethod
    def _write_scan(scan: BundleArchiveScan) -> dict[str, object]:
        return {
            "archive_id": scan.archive_id,
            "entries": [
                BundleDependencyScanCache._write_entry(entry) for entry in scan.entries
            ],
            "error": scan.error,
        }

    @staticmethod
    def _write_entry(entry: BundleEntryScan) -> dict[str, object]:
        return {
            "entry_path": entry.entry_path,
            "sha256": entry.sha256,
            "size": entry.size,
            "crc32": entry.crc32,
            "serialized_files": [
                {
                    "logical_name": item.logical_name,
                    "dependencies": list(item.dependencies),
                }
                for item in entry.serialized_files
            ],
            "resource_files": list(entry.resource_files),
            "streamed_resources": [
                {
                    "source_serialized_file": item.source_serialized_file,
                    "resource_path": item.resource_path,
                    "asset_type": item.asset_type,
                }
                for item in entry.streamed_resources
            ],
            "error": entry.error,
        }

    @classmethod
    def _read_scan(cls, payload: dict[str, object]) -> BundleArchiveScan:
        return BundleArchiveScan(
            archive_id=cast(str, payload["archive_id"]),
            entries=tuple(
                cls._read_entry(item) for item in cast(list[object], payload["entries"])
            ),
            error=cast(str | None, payload.get("error")),
        )

    @staticmethod
    def _read_entry(payload: object) -> BundleEntryScan:
        if not isinstance(payload, dict):
            raise ValueError("Bundle entry scan cache is invalid.")
        serialized_files = cast(list[dict[str, object]], payload["serialized_files"])
        streamed_resources = cast(
            list[dict[str, object]], payload["streamed_resources"]
        )
        return BundleEntryScan(
            entry_path=cast(str, payload["entry_path"]),
            sha256=cast(str, payload["sha256"]),
            size=cast(int, payload["size"]),
            crc32=cast(int | None, payload.get("crc32")),
            serialized_files=tuple(
                SerializedFileScan(
                    cast(str, item["logical_name"]),
                    tuple(cast(list[str], item["dependencies"])),
                )
                for item in serialized_files
            ),
            resource_files=tuple(cast(list[str], payload["resource_files"])),
            streamed_resources=tuple(
                StreamedResourceScan(
                    cast(str, item["source_serialized_file"]),
                    cast(str, item["resource_path"]),
                    cast(str, item["asset_type"]),
                )
                for item in streamed_resources
            ),
            error=cast(str | None, payload.get("error")),
        )
