from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from importlib import import_module, invalidate_caches, util
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass(frozen=True, slots=True)
class GeneratedSchemaRegistry:
    types: dict[str, type[Any]]
    enums: dict[str, type[Any]]
    package_name: str

    @classmethod
    def from_directory(
        cls,
        package_dir: str | Path,
        *,
        type_registry_name: str,
        enum_registry_name: str,
        package_prefix: str,
        registry_values_are_module_names: bool = False,
    ) -> GeneratedSchemaRegistry:
        package_path = Path(package_dir)
        registry = load_generated_registry_module(package_path, package_prefix)
        package_name = registry.__package__
        if not package_name:
            raise ImportError(
                f"Unable to resolve generated schema package name for {package_path}."
            )

        raw_types = getattr(registry, type_registry_name, {})
        raw_enums = getattr(registry, enum_registry_name, {})
        if not isinstance(raw_types, dict) or not isinstance(raw_enums, dict):
            raise TypeError(
                f"Generated schema registry has an invalid shape: {package_path}."
            )

        if registry_values_are_module_names:
            types = {
                key: load_generated_symbol(package_name, module_name)
                for key, module_name in raw_types.items()
            }
            enums = {
                key: load_generated_symbol(package_name, module_name)
                for key, module_name in raw_enums.items()
            }
        else:
            types = dict(raw_types)
            enums = dict(raw_enums)

        return cls(types=types, enums=enums, package_name=package_name)

    def resolve_type(self, name: str) -> type[Any] | None:
        if schema_type := self.types.get(name):
            return schema_type

        normalized_name = name.removesuffix(".bytes").lower()
        for full_name, schema_type in self.types.items():
            if full_name.lower() == normalized_name:
                return schema_type
            if full_name.rsplit(".", maxsplit=1)[-1].lower() == normalized_name:
                return schema_type
            if schema_type.__name__.lower() == normalized_name:
                return schema_type
        return None

    @property
    def lower_type_registry(self) -> dict[str, type[Any]]:
        return {
            key.rsplit(".", maxsplit=1)[-1].lower(): value
            for key, value in self.types.items()
        }


def load_generated_registry_module(package_dir: Path, package_prefix: str) -> ModuleType:
    init_file = package_dir / "__init__.py"
    registry_file = package_dir / "_registry.py"
    if not package_dir.is_dir():
        raise FileNotFoundError(
            f"Generated schema directory does not exist: {package_dir}."
        )
    if not init_file.is_file():
        raise FileNotFoundError(
            f"Generated schema package initializer is missing: {init_file}."
        )
    if not registry_file.is_file():
        raise FileNotFoundError(
            f"Generated schema registry is missing: {registry_file}."
        )

    invalidate_caches()
    path_digest = hashlib.sha1(str(package_dir.resolve()).encode("utf-8")).hexdigest()
    package_name = f"{package_prefix}_{path_digest}"
    spec = util.spec_from_file_location(
        package_name,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create generated schema import spec for {package_dir}.")

    module = sys.modules.get(package_name)
    if module is None:
        module = util.module_from_spec(spec)
        sys.modules[package_name] = module
        spec.loader.exec_module(module)

    return import_module(f"{package_name}._registry")


def load_generated_symbol(package_name: str, module_name: str) -> Any:
    module = import_module(f"{package_name}.{module_name}")
    return getattr(module, module_name)
