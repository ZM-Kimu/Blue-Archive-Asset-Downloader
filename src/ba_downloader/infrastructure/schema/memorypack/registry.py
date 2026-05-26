from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

from ba_downloader.infrastructure.schema.common.generated_registry import (
    GeneratedSchemaRegistry,
)


@dataclass(frozen=True, slots=True)
class MemoryPackSchemaRegistry:
    types: dict[str, type[Any]]
    enums: dict[str, type[IntEnum]]

    @classmethod
    def from_directory(
        cls, memorypack_data_dir: str | Path
    ) -> MemoryPackSchemaRegistry:
        registry = GeneratedSchemaRegistry.from_directory(
            memorypack_data_dir,
            type_registry_name="MEMORYPACK_TYPES",
            enum_registry_name="MEMORYPACK_ENUMS",
            package_prefix="ba_downloader_generated_memorypackdata",
            registry_values_are_module_names=True,
        )
        return cls(types=registry.types, enums=registry.enums)

    def resolve_type(self, name: str) -> type[Any] | None:
        if schema_type := self.types.get(name):
            return schema_type

        normalized_name = name.lower()
        for full_name, schema_type in self.types.items():
            if full_name.lower() == normalized_name:
                return schema_type
            if schema_type.__name__.lower() == normalized_name:
                return schema_type
        return None

    def resolve_enum(self, name: str) -> type[IntEnum] | None:
        if enum_type := self.enums.get(name):
            return enum_type

        normalized_name = name.lower()
        for full_name, enum_type in self.enums.items():
            if full_name.lower() == normalized_name:
                return enum_type
            if enum_type.__name__.lower() == normalized_name:
                return enum_type
        return None
