from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass as make_dataclass
from dataclasses import fields, is_dataclass
from enum import IntEnum
from inspect import currentframe
from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

from ba_downloader.infrastructure.schema.memorypack.cursor import (
    INTEGER_READERS,
    PRIMITIVE_READERS,
    MemoryPackCursor,
)
from ba_downloader.infrastructure.schema.memorypack.descriptors import MemoryPackMember
from ba_downloader.infrastructure.schema.memorypack.parser import MemoryPackCSParser

LIST_GENERIC_NAMES = (
    "System.Collections.Generic.List",
    "System.Collections.Generic.IReadOnlyList",
    "System.Collections.Generic.IList",
    "List",
)
DICTIONARY_GENERIC_NAMES = (
    "System.Collections.Generic.Dictionary",
    "System.Collections.Generic.IReadOnlyDictionary",
    "Dictionary",
)
_UNHANDLED = object()


def memorypack_schema(cls: type[Any]) -> type[Any]:
    caller_frame = currentframe()
    parent_frame = caller_frame.f_back if caller_frame is not None else None
    if parent_frame is not None:
        try:
            resolved_hints = get_type_hints(
                cls,
                globalns=parent_frame.f_globals,
                localns=parent_frame.f_locals,
                include_extras=True,
            )
            cls.__memorypack_type_hints__ = resolved_hints
        except (NameError, TypeError, AttributeError):
            pass

    if is_dataclass(cls):
        return cls
    return make_dataclass(cls)


def read_enum_value(cursor: MemoryPackCursor, enum_type: type[IntEnum]) -> int:
    enum_metadata = getattr(enum_type, "__memorypack_enum__", None)
    underlying_type = getattr(enum_metadata, "underlying_type", "System.Int32")
    normalized = MemoryPackCSParser._normalize_cs_type(underlying_type)
    reader = INTEGER_READERS.get(normalized, MemoryPackCursor.read_int32)
    return int(reader(cursor))


class SchemaObjectReader:
    def __init__(self, cursor: MemoryPackCursor) -> None:
        self._cursor = cursor

    def read_object(self, schema_type: type[Any]) -> Any | None:
        member_count = self._cursor.read_object_header()
        if member_count is None:
            return None

        values: dict[str, Any] = {}
        for field_name, member, annotation in schema_members(schema_type):
            if member.index >= member_count:
                values[field_name] = None
                continue
            values[field_name] = self.read_member_value(member.cs_type, annotation)
        return schema_type(**values)

    def read_member_value(self, cs_type: str, annotation: Any) -> Any:
        normalized = MemoryPackCSParser._normalize_cs_type(cs_type)
        collection_value = self._read_collection_value(normalized, annotation)
        if collection_value is not _UNHANDLED:
            return collection_value

        if primitive_reader := PRIMITIVE_READERS.get(normalized):
            return primitive_reader(self._cursor)

        object_type = object_type_from_annotation(annotation)
        if fallback_reader := PYTHON_TYPE_READERS.get(object_type):
            return fallback_reader(self._cursor)
        if isinstance(object_type, type) and issubclass(object_type, IntEnum):
            enum_value = read_enum_value(self._cursor, object_type)
            return object_type(enum_value)
        if isinstance(object_type, type) and is_dataclass(object_type):
            return self.read_object(object_type)
        raise TypeError(f"Unsupported MemoryPack member type: {cs_type}.")

    def _read_collection_value(self, normalized: str, annotation: Any) -> Any:
        list_inner = MemoryPackCSParser._extract_generic_inner(
            normalized,
            LIST_GENERIC_NAMES,
        )
        if list_inner:
            return self._read_sequence(list_inner, list_arg(annotation))

        if normalized.endswith("[]"):
            array_inner = normalized.removesuffix("[]")
            return self._read_sequence(array_inner, list_arg(annotation))

        dictionary_inner = MemoryPackCSParser._extract_generic_inner(
            normalized,
            DICTIONARY_GENERIC_NAMES,
        )
        if dictionary_inner:
            return self._read_dictionary(dictionary_inner, annotation)

        return _UNHANDLED

    def _read_sequence(self, inner_type: str, annotation: Any) -> list[Any] | None:
        length = self._cursor.read_collection_header()
        if length is None:
            return None
        return [self.read_member_value(inner_type, annotation) for _ in range(length)]

    def _read_dictionary(self, inner: str, annotation: Any) -> dict[Any, Any] | None:
        length = self._cursor.read_collection_header()
        if length is None:
            return None
        key_type, value_type = MemoryPackCSParser._split_generic_arguments(inner)
        key_annotation, value_annotation = dict_args(annotation)
        return {
            self.read_member_value(key_type, key_annotation): self.read_member_value(
                value_type,
                value_annotation,
            )
            for _ in range(length)
        }


def schema_members(schema_type: type[Any]) -> list[tuple[str, MemoryPackMember, Any]]:
    hints = getattr(schema_type, "__memorypack_type_hints__", None)
    if hints is None:
        hints = get_type_hints(schema_type, include_extras=True)
    result: list[tuple[str, MemoryPackMember, Any]] = []
    field_names = {field.name for field in fields(schema_type)}
    for field_name, annotation in hints.items():
        if field_name not in field_names:
            continue
        origin = get_origin(annotation)
        if origin is not Annotated:
            continue
        args = get_args(annotation)
        member = next(
            (item for item in args[1:] if isinstance(item, MemoryPackMember)),
            None,
        )
        if member is not None:
            result.append((field_name, member, args[0]))
    return sorted(result, key=lambda item: item[1].index)


def list_arg(annotation: Any) -> Any:
    object_type = object_type_from_annotation(annotation)
    origin = get_origin(object_type)
    if origin is list:
        return get_args(object_type)[0]
    return Any


def dict_args(annotation: Any) -> tuple[Any, Any]:
    object_type = object_type_from_annotation(annotation)
    origin = get_origin(object_type)
    if origin is dict:
        args = get_args(object_type)
        return args[0], args[1]
    return Any, Any


def object_type_from_annotation(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin in {UnionType, Union}:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if args:
            return args[0]
    return annotation


PYTHON_TYPE_READERS: dict[Any, Callable[[MemoryPackCursor], Any]] = {
    int: MemoryPackCursor.read_int32,
    float: MemoryPackCursor.read_float32,
    bool: MemoryPackCursor.read_bool,
    str: MemoryPackCursor.read_string,
}
