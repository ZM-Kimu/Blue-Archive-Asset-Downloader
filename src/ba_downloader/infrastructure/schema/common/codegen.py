from __future__ import annotations

from pathlib import Path
from typing import Any


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
