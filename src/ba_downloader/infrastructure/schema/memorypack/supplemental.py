from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ba_downloader.infrastructure.schema.memorypack.parser import MemoryPackCSParser
from ba_downloader.infrastructure.schema.memorypack.registry import (
    MemoryPackSchemaRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.schema_reader import (
    schema_members,
)

SIDECAR_VERSION = 1
UNION_ATTR_SIDECAR_NAME = "memorypack_union_attrs.json"


@dataclass(frozen=True, slots=True)
class SupplementalMember:
    name: str
    cs_type: str
    source: str
    wire_type: str = ""


class SupplementalMemoryPackFormatterBuilder:
    def __init__(
        self,
        dump_cs_path: str | Path,
        memorypack_data_dir: str | Path,
        sidecar_path: str | Path,
    ) -> None:
        self.dump_cs_path = Path(dump_cs_path)
        self.memorypack_data_dir = Path(memorypack_data_dir)
        self.sidecar_path = Path(sidecar_path)
        self.union_attr_path = self.sidecar_path.with_name(UNION_ATTR_SIDECAR_NAME)
        self.schema_registry = MemoryPackSchemaRegistry.from_directory(
            self.memorypack_data_dir,
        )

    def build(self) -> bool:
        data = self._load_sidecar()
        formatter_map = self._formatter_map(data)
        changed = self._merge_union_attribute_sidecar(formatter_map)

        for target_type in sorted(self.schema_registry.types):
            formatter = formatter_map.get(target_type)
            if formatter is None:
                continue
            if formatter.get("kind") == "union":
                continue
            if self._set_object_formatter(formatter_map, target_type):
                changed = True

        for formatter in list(formatter_map.values()):
            if formatter.get("kind") != "union":
                continue
            for target_type in self._union_target_types(formatter):
                if self._set_object_formatter(formatter_map, target_type):
                    changed = True

        if not formatter_map:
            return False

        self._write_sidecar(formatter_map)
        return changed

    def _load_sidecar(self) -> dict[str, Any]:
        if not self.sidecar_path.is_file():
            return {"version": SIDECAR_VERSION, "formatters": []}
        payload = json.loads(self.sidecar_path.read_text(encoding="utf8"))
        if not isinstance(payload, dict):
            return {"version": SIDECAR_VERSION, "formatters": []}
        return payload

    @staticmethod
    def _formatter_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw_formatters = data.get("formatters", [])
        if isinstance(raw_formatters, dict):
            return {
                str(target_type): {"target_type": str(target_type), **formatter}
                for target_type, formatter in raw_formatters.items()
                if isinstance(formatter, dict)
            }
        if isinstance(raw_formatters, list):
            return {
                str(formatter.get("target_type", "")): dict(formatter)
                for formatter in raw_formatters
                if isinstance(formatter, dict) and formatter.get("target_type")
            }
        return {}

    def _merge_union_attribute_sidecar(
        self,
        formatter_map: dict[str, dict[str, Any]],
    ) -> bool:
        if not self.union_attr_path.is_file():
            return False

        payload = json.loads(self.union_attr_path.read_text(encoding="utf8"))
        targets = payload.get("targets", []) if isinstance(payload, dict) else []
        changed = False
        for target in targets:
            if not isinstance(target, dict):
                continue
            root_type = str(target.get("full_name", ""))
            if not root_type:
                continue
            union_tags = self._extract_union_tags(target)
            if not union_tags:
                continue
            formatter_map[root_type] = {
                "target_type": root_type,
                "kind": "union",
                "tag_type": "byte",
                "union_tags": {str(tag): union_type for tag, union_type in union_tags},
                "source": "MemoryPackUnionAttribute",
            }
            changed = True
        return changed

    @staticmethod
    def _extract_union_tags(target: dict[str, Any]) -> list[tuple[int, str]]:
        result: list[tuple[int, str]] = []
        attributes = target.get("custom_attributes", [])
        if not isinstance(attributes, list):
            return result

        for attr in attributes:
            if not isinstance(attr, dict):
                continue
            if attr.get("attribute_type") != "MemoryPack.MemoryPackUnionAttribute":
                continue
            tag = attr.get("tag")
            union_type = attr.get("union_type")
            if isinstance(tag, int) and isinstance(union_type, str) and union_type:
                result.append((tag, union_type))
                continue

            rendered = str(attr.get("rendered", ""))
            match = re.search(r"MemoryPackUnion\((\d+), typeof\(([^)]+)\)\)", rendered)
            if match:
                result.append((int(match.group(1)), match.group(2)))
        return result

    @staticmethod
    def _union_target_types(formatter: dict[str, Any]) -> list[str]:
        raw_tags = formatter.get("union_tags", {})
        if not isinstance(raw_tags, dict):
            return []
        return [str(target_type) for target_type in raw_tags.values() if target_type]

    def _set_object_formatter(
        self,
        formatter_map: dict[str, dict[str, Any]],
        target_type: str,
    ) -> bool:
        members = self._wire_members(target_type, seen=set())
        if members is None:
            return self._mark_unavailable(
                formatter_map,
                target_type,
                "Generated MemoryPackData schema is unavailable.",
            )

        formatter_map[target_type] = {
            "target_type": target_type,
            "kind": "object",
            "object_header": True,
            "members": [
                {
                    "name": member.name,
                    "cs_type": member.cs_type,
                    "source": member.source,
                    **({"wire_type": member.wire_type} if member.wire_type else {}),
                }
                for member in members
            ],
            "source": "generated MemoryPackData",
        }
        return True

    def _mark_unavailable(
        self,
        formatter_map: dict[str, dict[str, Any]],
        target_type: str,
        reason: str,
    ) -> bool:
        current = formatter_map.get(target_type)
        if current and current.get("reason") == reason:
            return False
        formatter_map[target_type] = {
            "target_type": target_type,
            "kind": "unresolved",
            "members": [],
            "union_tags": {},
            "reason": reason,
        }
        return True

    def _wire_members(
        self,
        target_type: str,
        *,
        seen: set[str],
    ) -> tuple[SupplementalMember, ...] | None:
        if target_type in seen:
            return ()
        seen.add(target_type)

        schema_type = self.schema_registry.resolve_type(target_type)
        if schema_type is None:
            return None

        metadata = getattr(schema_type, "__memorypack_type__", None)
        inherited: tuple[SupplementalMember, ...] = ()
        base_type = getattr(metadata, "base_type", None)
        if isinstance(base_type, str) and base_type:
            base_members = self._wire_members(base_type, seen=seen)
            if base_members is not None:
                inherited = base_members

        own_members = tuple(
            SupplementalMember(
                name=name,
                cs_type=member.cs_type,
                source="generated MemoryPackData",
                wire_type=self._wire_type(member.cs_type),
            )
            for name, member, _python_type in schema_members(schema_type)
        )
        return inherited + own_members

    def _wire_type(self, cs_type: str) -> str:
        normalized = MemoryPackCSParser._normalize_cs_type(cs_type)
        if self.schema_registry.resolve_enum(normalized) is not None:
            return ""
        if normalized.startswith("FlatData.") or ".FlatData." in normalized:
            return "int32_enum"
        return ""

    def _write_sidecar(self, formatter_map: dict[str, dict[str, Any]]) -> None:
        self.sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SIDECAR_VERSION,
            "formatters": sorted(
                formatter_map.values(),
                key=lambda formatter: str(formatter.get("target_type", "")),
            ),
        }
        self.sidecar_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf8",
        )
