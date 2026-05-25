from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MemoryPackFormatterMemberDescriptor:
    name: str
    cs_type: str
    source: str = ""


@dataclass(frozen=True, slots=True)
class MemoryPackFormatterDescriptor:
    target_type: str
    kind: str
    members: tuple[MemoryPackFormatterMemberDescriptor, ...] = ()
    union_tags: dict[int, str] | None = None
    formatter_type: str = ""
    formatter_token: str = ""
    tag_type: str = "int"
    object_header: bool = False
    method_token: str = ""
    method_rva: str = ""
    reason: str = ""

    @property
    def is_available(self) -> bool:
        if self.reason:
            return False
        if self.kind == "object":
            return True
        if self.kind == "union":
            return bool(self.union_tags)
        return False


@dataclass(frozen=True, slots=True)
class MemoryPackFormatterRegistry:
    formatters: dict[str, MemoryPackFormatterDescriptor]

    @classmethod
    def from_file(cls, file_path: str | Path) -> MemoryPackFormatterRegistry:
        path = Path(file_path)
        return cls.from_dict(json.loads(path.read_text(encoding="utf8")))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryPackFormatterRegistry:
        raw_formatters = data.get("formatters", [])
        if isinstance(raw_formatters, dict):
            items = [
                {"target_type": target_type, **raw_formatter}
                for target_type, raw_formatter in raw_formatters.items()
                if isinstance(raw_formatter, dict)
            ]
        elif isinstance(raw_formatters, list):
            items = [item for item in raw_formatters if isinstance(item, dict)]
        else:
            items = []

        formatters: dict[str, MemoryPackFormatterDescriptor] = {}
        for item in items:
            descriptor = cls._parse_formatter(item)
            formatters[descriptor.target_type] = descriptor
        return cls(formatters=formatters)

    @staticmethod
    def _parse_formatter(data: dict[str, Any]) -> MemoryPackFormatterDescriptor:
        members = tuple(
            MemoryPackFormatterMemberDescriptor(
                name=str(member.get("name", "")),
                cs_type=str(member.get("cs_type", "")),
                source=str(member.get("source", "")),
            )
            for member in data.get("members", [])
            if isinstance(member, dict)
        )
        raw_tags = data.get("union_tags")
        union_tags: dict[int, str] | None = None
        if isinstance(raw_tags, dict):
            union_tags = {
                int(tag): str(target_type) for tag, target_type in raw_tags.items()
            }
        return MemoryPackFormatterDescriptor(
            target_type=str(data.get("target_type", "")),
            kind=str(data.get("kind", "unresolved")),
            members=members,
            union_tags=union_tags,
            formatter_type=str(data.get("formatter_type", "")),
            formatter_token=str(data.get("formatter_token", "")),
            tag_type=str(data.get("tag_type", "int")),
            object_header=bool(data.get("object_header", False)),
            method_token=str(data.get("method_token", "")),
            method_rva=str(data.get("method_rva", "")),
            reason=str(data.get("reason", "")),
        )

    def resolve(self, name: str) -> MemoryPackFormatterDescriptor | None:
        if formatter := self.formatters.get(name):
            return formatter

        normalized_name = name.lower()
        for target_type, formatter in self.formatters.items():
            if target_type.lower() == normalized_name:
                return formatter
            if target_type.rsplit(".", maxsplit=1)[-1].lower() == normalized_name:
                return formatter
        return None
