from __future__ import annotations

import hashlib
import shutil
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from importlib import import_module, invalidate_caches, util
from pathlib import Path
from threading import RLock
from types import ModuleType
from typing import Any


@dataclass(frozen=True, slots=True)
class _GeneratedSchemaCacheKey:
    package_dir: str
    content_digest: str
    type_registry_name: str
    enum_registry_name: str
    package_prefix: str
    registry_values_are_module_names: bool


_GENERATED_SCHEMA_LOAD_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class GeneratedSchemaRegistry:
    types: Mapping[str, type[Any]]
    enums: Mapping[str, type[Any]]
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
        cache_identity: str | None = None,
    ) -> GeneratedSchemaRegistry:
        package_path = Path(package_dir)
        with _GENERATED_SCHEMA_LOAD_LOCK:
            content_digest = cache_identity or _generated_schema_content_digest(
                package_path
            )
            cache_key = _GeneratedSchemaCacheKey(
                package_dir=str(package_path.resolve()),
                content_digest=content_digest,
                type_registry_name=type_registry_name,
                enum_registry_name=enum_registry_name,
                package_prefix=package_prefix,
                registry_values_are_module_names=registry_values_are_module_names,
            )
            cached_registry = _GENERATED_SCHEMA_REGISTRY_CACHE.get(cache_key)
            if cached_registry is not None:
                return cached_registry

            registry = load_generated_registry_module(
                package_path,
                package_prefix,
                content_digest=content_digest,
            )
            package_name = registry.__package__
            if not package_name:
                raise ImportError(
                    "Unable to resolve generated schema package name for "
                    f"{package_path}."
                )

            raw_types = getattr(registry, type_registry_name, {})
            raw_enums = getattr(registry, enum_registry_name, {})
            if not isinstance(raw_types, dict) or not isinstance(raw_enums, dict):
                raise TypeError(
                    f"Generated schema registry has an invalid shape: {package_path}."
                )

            if registry_values_are_module_names:
                types: Mapping[str, type[Any]] = _LazyGeneratedSymbolMap(
                    package_name,
                    raw_types,
                )
                enums: Mapping[str, type[Any]] = _LazyGeneratedSymbolMap(
                    package_name,
                    raw_enums,
                )
            else:
                types = dict(raw_types)
                enums = dict(raw_enums)

            generated_registry = cls(
                types=types,
                enums=enums,
                package_name=package_name,
            )
            _GENERATED_SCHEMA_REGISTRY_CACHE[cache_key] = generated_registry
            return generated_registry

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


_GENERATED_SCHEMA_REGISTRY_CACHE: dict[
    _GeneratedSchemaCacheKey,
    GeneratedSchemaRegistry,
] = {}


class _LazyGeneratedSymbolMap(Mapping[str, type[Any]]):
    def __init__(self, package_name: str, modules: dict[object, object]) -> None:
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in modules.items()
        ):
            raise TypeError("Generated lazy registry values must be module names.")
        self._package_name = package_name
        self._modules = {str(key): str(value) for key, value in modules.items()}
        self._loaded: dict[str, type[Any]] = {}

    def __getitem__(self, key: str) -> type[Any]:
        if key not in self._loaded:
            module_name = self._modules[key]
            symbol = load_generated_symbol(self._package_name, module_name)
            if not isinstance(symbol, type):
                raise TypeError(
                    f"Generated schema symbol is not a type: {module_name}."
                )
            self._loaded[key] = symbol
        return self._loaded[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._modules)

    def __len__(self) -> int:
        return len(self._modules)


def load_generated_registry_module(
    package_dir: Path,
    package_prefix: str,
    *,
    content_digest: str | None = None,
) -> ModuleType:
    with _GENERATED_SCHEMA_LOAD_LOCK:
        return _load_generated_registry_module(
            package_dir,
            package_prefix,
            content_digest=content_digest,
        )


def _load_generated_registry_module(
    package_dir: Path,
    package_prefix: str,
    *,
    content_digest: str | None,
) -> ModuleType:
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
    module_prefix = f"{package_prefix}_{path_digest}"
    _clear_generated_modules(module_prefix)
    _clear_generated_bytecode(package_dir)
    if content_digest is None:
        content_digest = _generated_schema_content_digest(package_dir)
    package_name = f"{module_prefix}_{content_digest}"
    spec = util.spec_from_file_location(
        package_name,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to create generated schema import spec for {package_dir}."
        )

    module = sys.modules.get(package_name)
    if module is None:
        module = util.module_from_spec(spec)
        sys.modules[package_name] = module
        previous_bytecode_setting = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous_bytecode_setting

    return import_module(f"{package_name}._registry")


def load_generated_symbol(package_name: str, module_name: str) -> Any:
    module = import_module(f"{package_name}.{module_name}")
    return getattr(module, module_name)


def _clear_generated_modules(module_prefix: str) -> None:
    for module_name in tuple(sys.modules):
        if module_name == module_prefix or module_name.startswith(f"{module_prefix}_"):
            sys.modules.pop(module_name, None)


def _generated_schema_content_digest(package_dir: Path) -> str:
    digest = hashlib.sha1()
    for file_path in sorted(package_dir.glob("*.py")):
        digest.update(file_path.name.encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()[:12]


def _clear_generated_bytecode(package_dir: Path) -> None:
    pycache_dir = package_dir / "__pycache__"
    if pycache_dir.exists():
        try:
            shutil.rmtree(pycache_dir)
        except OSError:
            return
