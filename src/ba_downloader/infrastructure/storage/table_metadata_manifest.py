from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ba_downloader.domain.models.asset import AssetCollection, AssetRecord, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext


class JpTableMetadataManifestStore:
    SCHEMA_VERSION = 1

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

        resources = AssetCollection()
        for entry in tables:
            if isinstance(entry, dict):
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
        payload: dict[str, Any] = {
            "schema_version": self.SCHEMA_VERSION,
            "region": context.region,
            "platform": context.platform,
            "version": context.version,
            "tables": tables,
        }
        manifest_path = self.manifest_path(context)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = manifest_path.with_suffix(f"{manifest_path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temp_path.replace(manifest_path)

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
            "path": resource.path,
            "size": resource.size,
            "crc": resource.checksum.value,
            "includes": cls._string_list(resource.metadata.get("includes")),
        }

    @classmethod
    def _add_manifest_entry(
        cls,
        resources: AssetCollection,
        entry: dict[object, object],
    ) -> None:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            return

        size = cls._coerce_size(entry.get("size", 0))
        crc = entry.get("crc", "")
        resources.add(
            "",
            path,
            size,
            str(crc),
            "crc",
            AssetType.table,
            {"includes": cls._string_list(entry.get("includes"))},
        )

    @staticmethod
    def _coerce_size(value: object) -> int:
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, str):
            try:
                return max(int(value), 0)
            except ValueError:
                return 0
        return 0

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]
