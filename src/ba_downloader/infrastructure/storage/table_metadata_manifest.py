from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ba_downloader.domain.models.asset import AssetCollection, AssetRecord, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext


class JpTableMetadataManifestStore:
    SCHEMA_VERSION = 2

    def manifest_path(self, context: RuntimeContext) -> Path:
        return (
            Path(context.temp_dir)
            / "catalog"
            / "jp"
            / context.platform
            / f"{context.version}.table-metadata.json"
        )

    def load(self, context: RuntimeContext) -> AssetCollection | None:
        if context.region != "jp" or not context.version:
            return None

        manifest_path = self.manifest_path(context)
        if not manifest_path.is_file():
            return None

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not self._is_current_payload(payload, context):
            return None

        tables = payload.get("tables")
        if not isinstance(tables, list):
            return None

        try:
            normalized_tables = self._validate_tables(tables)
        except ValueError:
            return None

        resources = AssetCollection()
        for entry in normalized_tables:
            self._add_manifest_entry(resources, entry)
        return resources

    def write(self, context: RuntimeContext, resources: AssetCollection) -> None:
        if context.region != "jp" or not context.version:
            return

        tables = [
            item
            for resource in resources
            if (item := self._serialize_table_resource(resource)) is not None
        ]
        normalized_tables = self._validate_tables(tables)
        payload: dict[str, Any] = {
            "schema_version": self.SCHEMA_VERSION,
            "region": context.region,
            "platform": context.platform,
            "version": context.version,
            "tables": normalized_tables,
        }
        manifest_path = self.manifest_path(context)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{manifest_path.name}.",
            suffix=".tmp",
            dir=manifest_path.parent,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, manifest_path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

    @classmethod
    def _is_current_payload(
        cls,
        payload: object,
        context: RuntimeContext,
    ) -> bool:
        if not isinstance(payload, dict):
            return False
        return (
            payload.get("schema_version") == cls.SCHEMA_VERSION
            and payload.get("region") == context.region
            and payload.get("platform") == context.platform
            and payload.get("version") == context.version
        )

    @classmethod
    def _serialize_table_resource(
        cls,
        resource: AssetRecord,
    ) -> dict[str, object] | None:
        if resource.asset_type is not AssetType.table:
            return None
        return {
            "url": resource.url,
            "path": resource.path,
            "size": resource.size,
            "crc": resource.checksum.value,
            "includes": resource.metadata.get("includes"),
        }

    @classmethod
    def _add_manifest_entry(
        cls,
        resources: AssetCollection,
        entry: dict[str, object],
    ) -> None:
        path = entry.get("path")
        url = entry.get("url")
        assert isinstance(path, str)
        assert isinstance(url, str)
        size = entry["size"]
        crc = entry["crc"]
        includes = entry["includes"]
        assert isinstance(size, int)
        assert isinstance(crc, str)
        assert isinstance(includes, list)
        resources.add(
            url,
            path,
            size,
            crc,
            "crc",
            AssetType.table,
            {"includes": includes},
        )

    @classmethod
    def _validate_tables(cls, tables: Sequence[object]) -> list[dict[str, object]]:
        if not tables:
            raise ValueError("JP table metadata must contain at least one resource.")
        normalized: list[dict[str, object]] = []
        seen_paths: set[str] = set()
        for entry in tables:
            if not isinstance(entry, dict):
                raise ValueError("JP table metadata entry must be an object.")
            path = entry.get("path")
            url = entry.get("url")
            size = entry.get("size")
            crc = entry.get("crc")
            includes = entry.get("includes")
            if not isinstance(path, str) or not path or path in seen_paths:
                raise ValueError(
                    "JP table metadata paths must be non-empty and unique."
                )
            parsed_url = urlparse(url) if isinstance(url, str) else None
            if (
                parsed_url is None
                or parsed_url.scheme not in {"http", "https"}
                or not parsed_url.netloc
            ):
                raise ValueError(
                    f"JP table metadata URL is invalid for resource {path}."
                )
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ValueError(
                    f"JP table metadata size is invalid for resource {path}."
                )
            try:
                normalized_crc = str(int(str(crc), 10))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"JP table metadata CRC is invalid for resource {path}."
                ) from exc
            if not isinstance(includes, list) or not all(
                isinstance(item, str) for item in includes
            ):
                raise ValueError(
                    f"JP table metadata includes are invalid for resource {path}."
                )
            seen_paths.add(path)
            normalized.append(
                {
                    "url": url,
                    "path": path,
                    "size": size,
                    "crc": normalized_crc,
                    "includes": list(includes),
                }
            )
        return normalized

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]
