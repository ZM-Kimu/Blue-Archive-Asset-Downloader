from __future__ import annotations

import re
from collections.abc import Collection

PRIMITIVE_PYTHON_TYPES: dict[str, str] = {
    "bool": "bool",
    "System.Boolean": "bool",
    "byte": "int",
    "System.Byte": "int",
    "sbyte": "int",
    "System.SByte": "int",
    "short": "int",
    "System.Int16": "int",
    "ushort": "int",
    "System.UInt16": "int",
    "int": "int",
    "System.Int32": "int",
    "uint": "int",
    "System.UInt32": "int",
    "long": "int",
    "System.Int64": "int",
    "ulong": "int",
    "System.UInt64": "int",
    "float": "float",
    "System.Single": "float",
    "double": "float",
    "System.Double": "float",
}


def strip_generic_arity(type_name: str) -> str:
    return type_name.split("`", maxsplit=1)[0]


def strip_member_type_modifiers(cs_type: str, modifiers: Collection[str]) -> str:
    parts = cs_type.strip().split()
    while len(parts) > 1 and parts[0] in modifiers:
        parts.pop(0)
    return " ".join(parts)


def normalize_cs_type(
    cs_type: str,
    *,
    modifiers: Collection[str] | None = None,
    unwrap_generic_names: tuple[str, ...] = (),
) -> str:
    normalized = (
        strip_member_type_modifiers(cs_type, modifiers or set())
        .strip()
        .removeprefix("global::")
        .removesuffix("?")
    )
    normalized = re.sub(
        r"(?P<name>[A-Za-z_][\w.]*)`\d+<",
        r"\g<name><",
        normalized,
    )
    if inner := extract_generic_inner(normalized, unwrap_generic_names):
        return normalize_cs_type(
            inner,
            modifiers=modifiers,
            unwrap_generic_names=unwrap_generic_names,
        )
    return normalized


def primitive_python_type(cs_type: str, *, extra: dict[str, str] | None = None) -> str:
    if extra and cs_type in extra:
        return extra[cs_type]
    return PRIMITIVE_PYTHON_TYPES.get(cs_type, "")


def extract_generic_inner(value: str, names: tuple[str, ...]) -> str:
    for name in names:
        prefix = f"{name}<"
        if value.startswith(prefix) and value.endswith(">"):
            return value[len(prefix) : -1].strip()
    return ""


def split_generic_arguments(value: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth = 0
    for char in value:
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items
