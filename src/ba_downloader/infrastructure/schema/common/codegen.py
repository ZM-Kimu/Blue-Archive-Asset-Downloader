from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypeVar


class FullNameItem(Protocol):
    @property
    def full_name(self) -> str: ...


T = TypeVar("T", bound=FullNameItem)


def resolve_unique_python_name(
    base_name: str,
    type_def_index: int,
    used_names: dict[str, int],
) -> str:
    used_names.setdefault(base_name, 0)
    if used_names[base_name] == 0:
        used_names[base_name] += 1
        return base_name
    used_names[base_name] += 1
    return f"{base_name}_{type_def_index}"


def build_simple_refs(
    refs: dict[str, tuple[str, Any]],
) -> dict[str, tuple[str, Any]]:
    grouped: dict[str, list[tuple[str, Any]]] = {}
    for full_name, ref in refs.items():
        simple_name = full_name.rsplit(".", maxsplit=1)[-1]
        grouped.setdefault(simple_name, []).append(ref)
    return {
        simple_name: values[0]
        for simple_name, values in grouped.items()
        if len(values) == 1
    }


def graph_has_path(
    graph: dict[str, set[str]],
    start_name: str,
    target_name: str,
) -> bool:
    visited: set[str] = set()
    pending = [start_name]
    while pending:
        current = pending.pop()
        if current == target_name:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph.get(current, set()) - visited)
    return False


def import_names(python_name: str, current_python_name: str) -> frozenset[str]:
    if python_name == current_python_name:
        return frozenset()
    return frozenset({python_name})


def build_python_name_maps(
    descriptors: list[Any],
    enums: list[Any],
    *,
    descriptor_key: Callable[[Any], str],
    enum_key: Callable[[Any], str],
) -> tuple[dict[str, str], dict[str, str]]:
    used_names: dict[str, int] = {}
    type_names: dict[str, str] = {}
    enum_names: dict[str, str] = {}
    for enum in enums:
        enum_names[enum_key(enum)] = resolve_unique_python_name(
            enum.python_name,
            enum.type_def_index,
            used_names,
        )
    for descriptor in descriptors:
        type_names[descriptor_key(descriptor)] = resolve_unique_python_name(
            descriptor.python_name,
            descriptor.type_def_index,
            used_names,
        )
    return type_names, enum_names


def build_refs(
    items: list[T],
    python_names: dict[str, str],
    item_key: Callable[[T], str],
) -> dict[str, tuple[str, T]]:
    refs: dict[str, tuple[str, T]] = {}
    for item in items:
        python_name = python_names[item_key(item)]
        refs[item.full_name] = (python_name, item)
    return refs


def build_cyclic_imports(
    descriptors: list[Any],
    type_python_names: dict[str, str],
    *,
    descriptor_key: Callable[[Any], str],
    collect_imports: Callable[[Any, str], set[str]],
) -> set[tuple[str, str]]:
    graph: dict[str, set[str]] = {
        python_name: set() for python_name in type_python_names.values()
    }
    all_type_names = set(type_python_names.values())
    for descriptor in descriptors:
        source_name = type_python_names[descriptor_key(descriptor)]
        graph[source_name].update(
            collect_imports(descriptor, source_name) & all_type_names
        )

    cyclic_imports: set[tuple[str, str]] = set()
    for source_name, targets in graph.items():
        for target_name in targets:
            if graph_has_path(graph, target_name, source_name):
                cyclic_imports.add((source_name, target_name))
    return cyclic_imports


def resolve_reference(
    cs_type: str,
    current_namespace: str,
    refs: dict[str, tuple[str, Any]],
    simple_refs: dict[str, tuple[str, Any]],
) -> tuple[str, Any] | None:
    candidates = [cs_type]
    if "." not in cs_type and current_namespace:
        candidates.insert(0, f"{current_namespace}.{cs_type}")
    for candidate in candidates:
        if candidate in refs:
            return refs[candidate]
    if "." not in cs_type:
        return simple_refs.get(cs_type)
    return None


def render_relative_imports(
    imports: list[str],
    cyclic_imports: set[tuple[str, str]],
    current_python_name: str,
) -> tuple[list[str], list[str], str]:
    runtime_imports = [
        import_name
        for import_name in imports
        if (current_python_name, import_name) not in cyclic_imports
    ]
    type_checking_imports = [
        import_name
        for import_name in imports
        if (current_python_name, import_name) in cyclic_imports
    ]
    typing_import = "from typing import Annotated, Any"
    if type_checking_imports:
        typing_import = "from typing import Annotated, Any, TYPE_CHECKING"
    return runtime_imports, type_checking_imports, typing_import


def write_text_file(output_dir: str | Path, file_name: str, content: str) -> None:
    Path(output_dir, file_name).write_text(content, encoding="utf8")


def escape_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def string_or_none(value: str | None) -> str:
    if value is None:
        return "None"
    return f'"{escape_string(value)}"'


def tuple_literal(values: tuple[str, ...]) -> str:
    if not values:
        return "()"
    return "(" + ", ".join(f'"{escape_string(value)}"' for value in values) + ",)"
