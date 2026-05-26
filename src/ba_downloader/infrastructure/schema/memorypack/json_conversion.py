from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import IntEnum
from typing import Any


def to_json_value(value: Any) -> Any:
    if isinstance(value, IntEnum):
        return value.name
    if is_dataclass(value):
        metadata = getattr(value, "__memorypack_type__", None)
        type_name = getattr(metadata, "name", value.__class__.__name__)
        namespace = getattr(metadata, "namespace", "")
        full_name = f"{namespace}.{type_name}" if namespace else type_name
        result: dict[str, Any] = {"__type__": full_name}
        for field in fields(value):
            result[field.name] = to_json_value(getattr(value, field.name))
        return result
    if isinstance(value, list):
        return [to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {to_json_value(key): to_json_value(item) for key, item in value.items()}
    return value
