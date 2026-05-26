from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass as make_dataclass
from dataclasses import fields, is_dataclass
from enum import IntEnum
from inspect import currentframe
from types import UnionType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

import flatbuffers

from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
from ba_downloader.infrastructure.schema.crypto import (
    convert_double,
    convert_float,
    convert_int,
    convert_long,
    convert_short,
    convert_string,
    convert_uint,
    convert_ulong,
    convert_ushort,
)
from ba_downloader.infrastructure.schema.flatbuffer.descriptors import FlatBufferField
from ba_downloader.infrastructure.schema.flatbuffer.parser import FlatBufferCSParser

LOGGER = ConsoleLogger()


class FlatBufferReader:
    _warning_cache: ClassVar[set[tuple[str, str, str, str]]] = set()
    SCALAR_SPECS: ClassVar[dict[str, tuple[Any, int, str | None]]] = {
        "bool": (flatbuffers.number_types.BoolFlags, 1, None),
        "System.Boolean": (flatbuffers.number_types.BoolFlags, 1, None),
        "byte": (flatbuffers.number_types.Uint8Flags, 1, None),
        "System.Byte": (flatbuffers.number_types.Uint8Flags, 1, None),
        "sbyte": (flatbuffers.number_types.Int8Flags, 1, None),
        "System.SByte": (flatbuffers.number_types.Int8Flags, 1, None),
        "short": (flatbuffers.number_types.Int16Flags, 2, "short"),
        "System.Int16": (flatbuffers.number_types.Int16Flags, 2, "short"),
        "ushort": (flatbuffers.number_types.Uint16Flags, 2, "ushort"),
        "System.UInt16": (flatbuffers.number_types.Uint16Flags, 2, "ushort"),
        "int": (flatbuffers.number_types.Int32Flags, 4, "int"),
        "System.Int32": (flatbuffers.number_types.Int32Flags, 4, "int"),
        "uint": (flatbuffers.number_types.Uint32Flags, 4, "uint"),
        "System.UInt32": (flatbuffers.number_types.Uint32Flags, 4, "uint"),
        "long": (flatbuffers.number_types.Int64Flags, 8, "long"),
        "System.Int64": (flatbuffers.number_types.Int64Flags, 8, "long"),
        "ulong": (flatbuffers.number_types.Uint64Flags, 8, "ulong"),
        "System.UInt64": (flatbuffers.number_types.Uint64Flags, 8, "ulong"),
        "float": (flatbuffers.number_types.Float32Flags, 4, "float"),
        "System.Single": (flatbuffers.number_types.Float32Flags, 4, "float"),
        "double": (flatbuffers.number_types.Float64Flags, 8, "double"),
        "System.Double": (flatbuffers.number_types.Float64Flags, 8, "double"),
    }

    CONVERTERS: ClassVar[dict[str, Callable[[Any, bytes], Any]]] = {
        "short": convert_short,
        "ushort": convert_ushort,
        "int": convert_int,
        "uint": convert_uint,
        "long": convert_long,
        "ulong": convert_ulong,
        "float": convert_float,
        "double": convert_double,
    }

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    @classmethod
    def reset_warning_cache(cls) -> None:
        cls._warning_cache.clear()

    @staticmethod
    def schema(cls: type[Any]) -> type[Any]:

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
                cls.__flatbuffer_type_hints__ = resolved_hints
            except (NameError, TypeError, AttributeError):
                pass

        if is_dataclass(cls):
            return cls
        return make_dataclass(cls)

    def read_root(
        self, schema_type: type[Any], *, password: bytes = b""
    ) -> dict[str, Any]:
        root_pos = flatbuffers.encode.Get(flatbuffers.packer.uoffset, self.payload, 0)
        root_table = flatbuffers.table.Table(self.payload, root_pos)
        return self.read_object(schema_type, root_table, password=password)

    def read_object(
        self,
        schema_type: type[Any],
        table: flatbuffers.table.Table,
        *,
        password: bytes = b"",
    ) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field_name, field, annotation in self._schema_fields(schema_type):
            if field.is_vector:
                values[field_name] = self._read_vector(
                    schema_type,
                    table,
                    field,
                    annotation,
                    password,
                )
            else:
                values[field_name] = self._read_value(
                    schema_type,
                    table,
                    field,
                    annotation,
                    password,
                )
        return values

    def _read_value(
        self,
        schema_type: type[Any],
        table: flatbuffers.table.Table,
        field: FlatBufferField,
        annotation: Any,
        password: bytes,
    ) -> Any:
        offset = self._field_offset(table, field.index)
        normalized = FlatBufferCSParser._normalize_cs_type(field.cs_type)
        if offset == 0:
            return self._default_value(normalized, annotation)

        if normalized in {"string", "System.String"}:
            value = table.String(offset + table.Pos)
            return self._convert_string(value, password)

        if enum_type := self._enum_type(annotation):
            raw_value = self._read_enum_scalar(table, offset, enum_type)
            raw_value = self._convert_enum_value(raw_value, enum_type, password)
            return self._enum_name_or_value(enum_type, raw_value)

        if normalized in self.SCALAR_SPECS:
            return self._convert_scalar(
                table.Get(self.SCALAR_SPECS[normalized][0], offset + table.Pos),
                normalized,
                password,
            )

        if object_type := self._schema_type(annotation):
            child_pos = table.Indirect(offset + table.Pos)
            child_table = flatbuffers.table.Table(table.Bytes, child_pos)
            return self.read_object(object_type, child_table, password=password)

        self._warn_unresolved_field_once(schema_type, field, is_vector=False)
        return None

    def _read_vector(
        self,
        schema_type: type[Any],
        table: flatbuffers.table.Table,
        field: FlatBufferField,
        annotation: Any,
        password: bytes,
    ) -> list[Any] | None:
        offset = self._field_offset(table, field.index)
        if offset == 0:
            return []

        normalized = FlatBufferCSParser._normalize_cs_type(field.cs_type)
        vector_start = table.Vector(offset)
        length = table.VectorLen(offset)
        item_annotation = self._list_arg(annotation)

        if normalized in {"string", "System.String"}:
            return [
                self._convert_string(
                    table.String(
                        vector_start
                        + flatbuffers.number_types.UOffsetTFlags.py_type(index * 4)
                    ),
                    password,
                )
                for index in range(length)
            ]

        if enum_type := self._enum_type(item_annotation):
            return [
                self._enum_name_or_value(
                    enum_type,
                    self._convert_enum_value(
                        self._read_enum_scalar_at(vector_start, index, enum_type),
                        enum_type,
                        password,
                    ),
                )
                for index in range(length)
            ]

        if normalized in self.SCALAR_SPECS:
            flags, size, _ = self.SCALAR_SPECS[normalized]
            return [
                self._convert_scalar(
                    table.Get(
                        flags,
                        vector_start
                        + flatbuffers.number_types.UOffsetTFlags.py_type(index * size),
                    ),
                    normalized,
                    password,
                )
                for index in range(length)
            ]

        if object_type := self._schema_type(item_annotation):
            values: list[Any] = []
            for index in range(length):
                item_pos = (
                    vector_start
                    + flatbuffers.number_types.UOffsetTFlags.py_type(index * 4)
                )
                child_table = flatbuffers.table.Table(
                    table.Bytes, table.Indirect(item_pos)
                )
                values.append(
                    self.read_object(object_type, child_table, password=password)
                )
            return values

        self._warn_unresolved_field_once(schema_type, field, is_vector=True)
        return None

    @classmethod
    def _warn_unresolved_field_once(
        cls,
        schema_type: type[Any],
        field: FlatBufferField,
        *,
        is_vector: bool,
    ) -> None:
        schema_name = field.type_name or schema_type.__name__
        field_name = field.original_name or ""
        kind = "vector" if is_vector else "field"
        warning_key = (kind, schema_name, field_name, field.cs_type)
        if warning_key in cls._warning_cache:
            return
        cls._warning_cache.add(warning_key)
        LOGGER.warn(
            f"Unresolved FlatBuffer {kind} field skipped: "
            f"{schema_name}.{field_name} ({field.cs_type})."
        )

    @staticmethod
    def _field_offset(table: flatbuffers.table.Table, index: int) -> int:
        return flatbuffers.number_types.UOffsetTFlags.py_type(
            table.Offset(4 + index * 2)
        )

    @classmethod
    def _default_value(cls, normalized: str, annotation: Any) -> Any:
        if normalized in {"string", "System.String"}:
            return None
        if cls._enum_type(annotation):
            return cls._enum_name_or_value(cls._enum_type(annotation), 0)
        if normalized in cls.SCALAR_SPECS:
            if normalized in {"bool", "System.Boolean"}:
                return False
            if normalized in {
                "float",
                "System.Single",
                "double",
                "System.Double",
            }:
                return 0.0
            return 0
        if cls._schema_type(annotation):
            return None
        return None

    @classmethod
    def _read_enum_scalar(
        cls,
        table: flatbuffers.table.Table,
        offset: int,
        enum_type: type[IntEnum],
    ) -> int:
        normalized = cls._enum_underlying_type(enum_type)
        flags = cls.SCALAR_SPECS.get(normalized, cls.SCALAR_SPECS["System.Int32"])[0]
        return int(table.Get(flags, offset + table.Pos))

    def _read_enum_scalar_at(
        self,
        vector_start: int,
        index: int,
        enum_type: type[IntEnum],
    ) -> int:
        normalized = self._enum_underlying_type(enum_type)
        scalar_spec = self.SCALAR_SPECS.get(
            normalized,
            self.SCALAR_SPECS["System.Int32"],
        )
        flags = scalar_spec[0]
        size = scalar_spec[1]
        return int(
            flatbuffers.table.Table(self.payload, 0).Get(
                flags,
                vector_start
                + flatbuffers.number_types.UOffsetTFlags.py_type(index * size),
            )
        )

    @classmethod
    def _convert_enum_value(
        cls,
        value: int,
        enum_type: type[IntEnum],
        password: bytes,
    ) -> int:
        normalized = cls._enum_underlying_type(enum_type)
        return int(cls._convert_scalar(value, normalized, password))

    @classmethod
    def _convert_scalar(cls, value: Any, normalized: str, password: bytes) -> Any:
        if not password:
            return value
        converter_key = cls.SCALAR_SPECS.get(normalized, (None, 0, None))[2]
        if converter_key is None:
            return value
        return cls.CONVERTERS[converter_key](value, password)

    @staticmethod
    def _convert_string(value: bytes | str, password: bytes) -> str | None:
        if password:
            return convert_string(value, password)
        if isinstance(value, bytes):
            return value.decode("utf8")
        return value

    @staticmethod
    def _enum_underlying_type(enum_type: type[IntEnum]) -> str:
        metadata = getattr(enum_type, "__flatbuffer_enum__", None)
        underlying_type = getattr(metadata, "underlying_type", "System.Int32")
        return FlatBufferCSParser._normalize_cs_type(underlying_type)

    @staticmethod
    def _enum_name_or_value(enum_type: type[IntEnum] | None, value: int) -> str | int:
        if enum_type is None:
            return value
        try:
            return enum_type(value).name
        except ValueError:
            return value

    @classmethod
    def _schema_fields(
        cls,
        schema_type: type[Any],
    ) -> list[tuple[str, FlatBufferField, Any]]:
        hints = getattr(schema_type, "__flatbuffer_type_hints__", None)
        if hints is None:
            hints = get_type_hints(schema_type, include_extras=True)
        members: list[tuple[str, FlatBufferField, Any]] = []
        for dataclass_field in fields(schema_type):
            hint = hints.get(dataclass_field.name, dataclass_field.type)
            origin = get_origin(hint)
            if origin is not Annotated:
                continue
            args = get_args(hint)
            annotation = args[0]
            field_metadata = next(
                item for item in args[1:] if isinstance(item, FlatBufferField)
            )
            members.append((dataclass_field.name, field_metadata, annotation))
        return members

    @classmethod
    def _list_arg(cls, annotation: Any) -> Any:
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin in {list, tuple} and args:
            return args[0]
        if origin in {UnionType, Union}:
            for arg in args:
                if arg is type(None):
                    continue
                return cls._list_arg(arg)
        return Any

    @classmethod
    def _schema_type(cls, annotation: Any) -> type[Any] | None:
        object_type = cls._object_type(annotation)
        if isinstance(object_type, type) and hasattr(
            object_type, "__flatbuffer_type__"
        ):
            return object_type
        return None

    @classmethod
    def _enum_type(cls, annotation: Any) -> type[IntEnum] | None:
        object_type = cls._object_type(annotation)
        if isinstance(object_type, type) and issubclass(object_type, IntEnum):
            return object_type
        return None

    @classmethod
    def _object_type(cls, annotation: Any) -> Any:
        origin = get_origin(annotation)
        if origin is Annotated:
            return cls._object_type(get_args(annotation)[0])
        if origin in {UnionType, Union}:
            for arg in get_args(annotation):
                if arg is not type(None):
                    return cls._object_type(arg)
            return Any
        return annotation


class FlatBufferExporter:
    def __init__(
        self,
        type_registry: dict[str, type[Any]],
        enum_registry: dict[str, type[IntEnum]] | None = None,
    ) -> None:
        self.type_registry = type_registry
        self.enum_registry = enum_registry or {}
        self.lower_type_registry = {
            key.rsplit(".", maxsplit=1)[-1].lower(): value
            for key, value in type_registry.items()
        }

    def resolve_schema(self, file_name: str) -> type[Any] | None:
        stem = file_name.removesuffix(".bytes")
        return self.lower_type_registry.get(stem.lower())

    def export_payload(
        self,
        schema_type: type[Any],
        data: bytes,
        *,
        password: bytes = b"",
    ) -> dict[str, Any] | list[Any]:
        decoded = FlatBufferReader(data).read_root(schema_type, password=password)
        data_list_key = self._data_list_key(schema_type)
        if data_list_key is not None:
            value = decoded.get(data_list_key)
            return value if isinstance(value, list) else []
        return decoded

    @staticmethod
    def _data_list_key(schema_type: type[Any]) -> str | None:
        for field_name, field, _ in FlatBufferReader._schema_fields(schema_type):
            if field.original_name == "DataList" and field.is_vector:
                return field_name
        return None
