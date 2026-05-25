from __future__ import annotations

from typing import Any

from ba_downloader.infrastructure.schema.memorypack.cursor import (
    INTEGER_READERS,
    PRIMITIVE_READERS,
    MemoryPackCursor,
)
from ba_downloader.infrastructure.schema.memorypack.formatters import (
    MemoryPackFormatterDescriptor,
    MemoryPackFormatterMemberDescriptor,
    MemoryPackFormatterRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.json_conversion import to_json_value
from ba_downloader.infrastructure.schema.memorypack.parser import MemoryPackCSParser
from ba_downloader.infrastructure.schema.memorypack.registry import (
    MemoryPackSchemaRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.schema_reader import (
    DICTIONARY_GENERIC_NAMES,
    LIST_GENERIC_NAMES,
    SchemaObjectReader,
    read_enum_value,
)

FORMATTER_KIND_HANDLERS = {
    "union": "_read_formatter_union",
    "object": "_read_formatter_members",
}
_UNHANDLED = object()


class FormatterDrivenReader:
    def __init__(
        self,
        cursor: MemoryPackCursor,
        schema_reader: SchemaObjectReader,
    ) -> None:
        self._cursor = cursor
        self._schema_reader = schema_reader

    def read_object(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
        *,
        ensure_consumed: bool = True,
    ) -> dict[str, Any]:
        result = self._read_formatter_object(
            root_type,
            schema_registry,
            formatter_registry,
        )
        if ensure_consumed and self._cursor.offset != len(self._cursor.payload):
            raise ValueError(
                "MemoryPack formatter payload was not fully consumed: "
                f"{self._cursor.offset}/{len(self._cursor.payload)} bytes."
            )
        return result

    def _read_formatter_object(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> dict[str, Any]:
        formatter = formatter_registry.resolve(root_type)
        if formatter is None or not formatter.is_available:
            raise ValueError(
                f"MemoryPack formatter layout is unavailable for {root_type}."
            )

        handler_name = FORMATTER_KIND_HANDLERS.get(formatter.kind)
        if handler_name is None:
            raise ValueError(
                f"Unsupported MemoryPack formatter kind: {formatter.kind}."
            )
        handler = getattr(self, handler_name)
        return handler(formatter, schema_registry, formatter_registry)

    def _read_formatter_union(
        self,
        formatter: MemoryPackFormatterDescriptor,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> dict[str, Any]:
        tag = self._read_formatter_tag(formatter)
        if not formatter.union_tags or tag not in formatter.union_tags:
            raise ValueError(
                f"Unknown MemoryPack formatter tag {tag} for {formatter.target_type}."
            )
        return self._read_formatter_object(
            formatter.union_tags[tag],
            schema_registry,
            formatter_registry,
        )

    def _read_formatter_tag(self, formatter: MemoryPackFormatterDescriptor) -> int:
        normalized = MemoryPackCSParser._normalize_cs_type(formatter.tag_type)
        reader = INTEGER_READERS.get(normalized, MemoryPackCursor.read_int32)
        return int(reader(self._cursor))

    def _read_formatter_members(
        self,
        formatter: MemoryPackFormatterDescriptor,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"__type__": formatter.target_type}
        member_count: int | None = None
        if formatter.object_header:
            member_count = self._cursor.read_object_header()
            if member_count is None:
                return result | {"__value__": None}
            if member_count > len(formatter.members):
                raise ValueError(
                    "MemoryPack formatter layout is incomplete for "
                    f"{formatter.target_type}: object header has {member_count} "
                    f"members, sidecar covers {len(formatter.members)}."
                )
        for index, member in enumerate(formatter.members):
            if member_count is not None and index >= member_count:
                result[member.name] = None
                continue
            result[member.name] = self._read_formatter_member(
                member,
                schema_registry,
                formatter_registry,
            )
        return result

    def _read_formatter_member(
        self,
        member: MemoryPackFormatterMemberDescriptor,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> Any:
        return self._read_formatter_value(
            member.cs_type,
            schema_registry,
            formatter_registry,
        )

    def _read_formatter_value(
        self,
        cs_type: str,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> Any:
        normalized = MemoryPackCSParser._normalize_cs_type(cs_type)
        collection_value = self._read_collection_value(
            normalized,
            schema_registry,
            formatter_registry,
        )
        if collection_value is not _UNHANDLED:
            return collection_value

        if primitive_reader := PRIMITIVE_READERS.get(normalized):
            return primitive_reader(self._cursor)

        if enum_type := schema_registry.resolve_enum(normalized):
            enum_value = read_enum_value(self._cursor, enum_type)
            try:
                return enum_type(enum_value).name
            except ValueError:
                return enum_value

        if formatter_registry.resolve(normalized):
            return self._read_formatter_object(
                normalized,
                schema_registry,
                formatter_registry,
            )

        if schema_type := schema_registry.resolve_type(normalized):
            return to_json_value(self._schema_reader.read_object(schema_type))

        raise TypeError(f"Unsupported MemoryPack formatter member type: {cs_type}.")

    def _read_collection_value(
        self,
        normalized: str,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> Any:
        list_inner = MemoryPackCSParser._extract_generic_inner(
            normalized,
            LIST_GENERIC_NAMES,
        )
        if list_inner:
            return self._read_sequence(list_inner, schema_registry, formatter_registry)

        if normalized.endswith("[]"):
            array_inner = normalized.removesuffix("[]")
            return self._read_sequence(array_inner, schema_registry, formatter_registry)

        dictionary_inner = MemoryPackCSParser._extract_generic_inner(
            normalized,
            DICTIONARY_GENERIC_NAMES,
        )
        if dictionary_inner:
            return self._read_dictionary(
                dictionary_inner,
                schema_registry,
                formatter_registry,
            )

        return _UNHANDLED

    def _read_sequence(
        self,
        inner_type: str,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> list[Any] | None:
        length = self._cursor.read_collection_header()
        if length is None:
            return None
        return [
            self._read_formatter_value(inner_type, schema_registry, formatter_registry)
            for _ in range(length)
        ]

    def _read_dictionary(
        self,
        inner: str,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> dict[Any, Any] | None:
        length = self._cursor.read_collection_header()
        if length is None:
            return None
        key_type, value_type = MemoryPackCSParser._split_generic_arguments(inner)
        return {
            self._read_formatter_value(
                key_type,
                schema_registry,
                formatter_registry,
            ): self._read_formatter_value(
                value_type,
                schema_registry,
                formatter_registry,
            )
            for _ in range(length)
        }
