from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
    BundleEntryScan,
    SerializedFileScan,
    StreamedResourceScan,
)
from ba_downloader.infrastructure.files.atomic import write_json_atomic

SCAN_CACHE_SCHEMA_VERSION = 3


def dependency_scan_cache_root(context: ExecutionContext) -> Path:
    return context.workspace.cache_state / "assetripper" / "dependency-scans"


class BundleDependencyScanCache:
    def __init__(self, root: Path) -> None:
        self._root = root

    def path_for(self, archive: BundleArchiveInput) -> Path:
        digest = hashlib.sha256(archive.archive_id.encode("utf8")).hexdigest()
        return self._root / f"{digest}.json"

    def load(
        self,
        archive: BundleArchiveInput,
        *,
        tool_key: str,
    ) -> BundleArchiveScan | None:
        try:
            payload = json.loads(self.path_for(archive).read_text(encoding="utf8"))
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
        path = self.path_for(archive)
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
        archive_id = payload.get("archive_id")
        entries = payload.get("entries")
        error = payload.get("error")
        if (
            not isinstance(archive_id, str)
            or not isinstance(entries, list)
            or (error is not None and not isinstance(error, str))
        ):
            raise ValueError("Dependency scan cache schema is invalid.")
        return BundleArchiveScan(
            archive_id=archive_id,
            entries=tuple(cls._read_entry(item) for item in entries),
            error=error,
        )

    @staticmethod
    def _read_entry(payload: object) -> BundleEntryScan:
        if not isinstance(payload, dict):
            raise ValueError("Bundle entry scan cache is invalid.")
        entry_path = payload.get("entry_path")
        sha256 = payload.get("sha256")
        size = payload.get("size")
        crc32 = payload.get("crc32")
        serialized_files = payload.get("serialized_files")
        resource_files = payload.get("resource_files")
        streamed_resources = payload.get("streamed_resources")
        error = payload.get("error")
        if (
            not isinstance(entry_path, str)
            or not isinstance(sha256, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or (
                crc32 is not None
                and (
                    not isinstance(crc32, int)
                    or isinstance(crc32, bool)
                    or not 0 <= crc32 <= 0xFFFFFFFF
                )
            )
            or not isinstance(serialized_files, list)
            or not isinstance(resource_files, list)
            or not all(isinstance(item, str) for item in resource_files)
            or not isinstance(streamed_resources, list)
            or (error is not None and not isinstance(error, str))
        ):
            raise ValueError("Bundle entry scan cache is invalid.")

        parsed_serialized: list[SerializedFileScan] = []
        for item in serialized_files:
            if not isinstance(item, dict):
                raise ValueError("Serialized file scan cache is invalid.")
            logical_name = item.get("logical_name")
            dependencies = item.get("dependencies")
            if (
                not isinstance(logical_name, str)
                or not isinstance(dependencies, list)
                or not all(isinstance(value, str) for value in dependencies)
            ):
                raise ValueError("Serialized file scan cache is invalid.")
            parsed_serialized.append(
                SerializedFileScan(logical_name, tuple(dependencies))
            )

        parsed_streamed: list[StreamedResourceScan] = []
        for item in streamed_resources:
            if not isinstance(item, dict):
                raise ValueError("Streamed resource scan cache is invalid.")
            source = item.get("source_serialized_file")
            resource_path = item.get("resource_path")
            asset_type = item.get("asset_type")
            if (
                not isinstance(source, str)
                or not isinstance(resource_path, str)
                or not isinstance(asset_type, str)
            ):
                raise ValueError("Streamed resource scan cache is invalid.")
            parsed_streamed.append(
                StreamedResourceScan(source, resource_path, asset_type)
            )

        return BundleEntryScan(
            entry_path=entry_path,
            sha256=sha256,
            size=size,
            crc32=crc32,
            serialized_files=tuple(parsed_serialized),
            resource_files=tuple(resource_files),
            streamed_resources=tuple(parsed_streamed),
            error=error,
        )
