from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, fields, is_dataclass
from dataclasses import dataclass as make_dataclass
from enum import IntEnum
from inspect import currentframe
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

from ba_downloader.infrastructure.schema.common.generated_registry import (
    GeneratedSchemaRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.descriptors import MemoryPackMember
from ba_downloader.infrastructure.schema.memorypack.formatters import (
    MemoryPackFormatterDescriptor,
    MemoryPackFormatterMemberDescriptor,
    MemoryPackFormatterRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.parser import MemoryPackCSParser

NULL_OBJECT_HEADER = 255
NULL_COLLECTION_HEADER = -1


@dataclass(frozen=True, slots=True)
class MemoryPackSchemaRegistry:
    types: dict[str, type[Any]]
    enums: dict[str, type[IntEnum]]

    @classmethod
    def from_directory(cls, memorypack_data_dir: str | Path) -> MemoryPackSchemaRegistry:
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

class MemoryPackReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

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
                cls.__memorypack_type_hints__ = resolved_hints
            except (NameError, TypeError, AttributeError):
                pass

        if is_dataclass(cls):
            return cls
        return make_dataclass(cls)

    def read_object(self, schema_type: type[Any]) -> Any | None:
        member_count = self.read_object_header()
        if member_count is None:
            return None

        members = self._schema_members(schema_type)
        values: dict[str, Any] = {}
        for field_name, member, annotation in members:
            if member.index >= member_count:
                values[field_name] = None
                continue
            values[field_name] = self._read_member_value(member.cs_type, annotation)
        return schema_type(**values)

    def read_formatter_object(
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
        if ensure_consumed and self.offset != len(self.payload):
            raise ValueError(
                "MemoryPack formatter payload was not fully consumed: "
                f"{self.offset}/{len(self.payload)} bytes."
            )
        return result

    def read_cn_table_dao_partial(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry | None = None,
    ) -> dict[str, Any]:
        if root_type == "MX.AppData.DAO.Battle.SkillVisualDAO":
            return self._read_skill_visual_dao_partial(root_type)
        if root_type == "MX.GameData.DAO.Battle.SkillLogicDAO":
            return self._read_skill_logic_dao_partial(root_type)
        if root_type == "MX.GameData.DAO.Battle.LogicEffectDAO":
            return self._read_logic_effect_dao_partial(root_type, schema_registry)
        raise ValueError(f"Unsupported CN table MemoryPack root type: {root_type}.")

    def read_object_header(self) -> int | None:
        header = self.read_uint8()
        if header == NULL_OBJECT_HEADER:
            return None
        return header

    def read_collection_header(self) -> int | None:
        length = self.read_int32()
        if length == NULL_COLLECTION_HEADER:
            return None
        return length

    def peek_int32(self) -> int:
        return struct.unpack("<i", self.payload[self.offset : self.offset + 4])[0]

    def read_string(self) -> str | None:
        length = self.read_collection_header()
        if length is None:
            return None
        if length == 0:
            return ""
        if length > 0:
            return self._read_exact(length * 2).decode("utf-16-le")

        utf8_length = ~length
        self.read_int32()
        return self._read_exact(utf8_length).decode("utf8")

    def read_bool(self) -> bool:
        return struct.unpack("<?", self._read_exact(1))[0]

    def read_uint8(self) -> int:
        return struct.unpack("<B", self._read_exact(1))[0]

    def read_int16(self) -> int:
        return struct.unpack("<h", self._read_exact(2))[0]

    def read_uint16(self) -> int:
        return struct.unpack("<H", self._read_exact(2))[0]

    def read_int32(self) -> int:
        return struct.unpack("<i", self._read_exact(4))[0]

    def read_uint32(self) -> int:
        return struct.unpack("<I", self._read_exact(4))[0]

    def read_int64(self) -> int:
        return struct.unpack("<q", self._read_exact(8))[0]

    def read_uint64(self) -> int:
        return struct.unpack("<Q", self._read_exact(8))[0]

    def read_float32(self) -> float:
        return struct.unpack("<f", self._read_exact(4))[0]

    def read_float64(self) -> float:
        return struct.unpack("<d", self._read_exact(8))[0]

    def _read_exact(self, size: int) -> bytes:
        end_offset = self.offset + size
        if end_offset > len(self.payload):
            raise EOFError("Unexpected end of MemoryPack payload.")
        data = self.payload[self.offset : end_offset]
        self.offset = end_offset
        return data

    def _read_skill_visual_dao_partial(self, root_type: str) -> dict[str, Any]:
        object_header = self._read_required_object_header(root_type)
        result = self._partial_base(root_type)
        result["__object_header__"] = object_header
        result["name"] = self.read_string()
        result["VisualDataKey"] = self.read_string()
        result["GuidePrefabPath"] = self.read_string()
        for field_name in (
            "ActionEffects",
            "EntityEffects",
            "LogicEffectVisuals",
            "BattleItems",
            "ParticleEffectDatas",
        ):
            consumed, value = self._try_read_empty_collection()
            if not consumed:
                break
            result[field_name] = value
        self._finish_partial_result(result, known_member_count=8)
        return result

    def _read_skill_logic_dao_partial(self, root_type: str) -> dict[str, Any]:
        union_tag = self.read_uint8()
        object_header = self._read_required_object_header(root_type)
        result = self._partial_base(root_type)
        result["__union_tag__"] = union_tag
        result["__object_header__"] = object_header
        result["name"] = self.read_string()
        result["SkillDataKey"] = self.read_string()
        self._finish_partial_result(result, known_member_count=2)
        return result

    def _read_logic_effect_dao_partial(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry | None,
    ) -> dict[str, Any]:
        union_tag = self.read_uint8()
        object_header = self._read_required_object_header(root_type)
        result = self._partial_base(root_type)
        result["__union_tag__"] = union_tag
        result["__object_header__"] = object_header
        result["Level"] = self.read_int32()
        result["GroupId"] = self.read_string()
        category_value = self.read_int32()
        result["Category"] = self._enum_name_or_raw(
            "FlatData.LogicEffectCategory",
            category_value,
            schema_registry,
        )
        result["TemplateId"] = self.read_string()
        result["Channel"] = self.read_int32()
        result["ApplyRate"] = self.read_int64()
        result["CommonVisualId"] = self.read_int64()
        result["CommonVisualHash"] = self.read_int64()
        result["PriorityWhenSameFrame"] = self.read_int32()
        self._finish_partial_result(result, known_member_count=9)
        return result

    def _read_required_object_header(self, root_type: str) -> int:
        object_header = self.read_object_header()
        if object_header is None:
            raise ValueError(f"Unexpected null MemoryPack object for {root_type}.")
        return object_header

    def _try_read_empty_collection(self) -> tuple[bool, list[Any] | None]:
        if len(self.payload) - self.offset < 4:
            return False, None
        length = self.peek_int32()
        if length == NULL_COLLECTION_HEADER:
            self.read_int32()
            return True, None
        if length == 0:
            self.read_int32()
            return True, []
        return False, None

    def _finish_partial_result(
        self,
        result: dict[str, Any],
        *,
        known_member_count: int,
    ) -> None:
        remaining_size = len(self.payload) - self.offset
        object_header = result.get("__object_header__")
        result["__remaining_offset__"] = self.offset
        result["__remaining_size__"] = remaining_size
        result["__partial_memorypack__"] = bool(
            remaining_size or (
                isinstance(object_header, int) and object_header > known_member_count
            )
        )

    def _partial_base(self, root_type: str) -> dict[str, Any]:
        return {
            "__type__": root_type,
            "__root_type__": root_type,
            "__payload_size__": len(self.payload),
            "__payload_sha256__": hashlib.sha256(self.payload).hexdigest(),
            "__payload_head__": self.payload[:64].hex(),
        }

    @staticmethod
    def _enum_name_or_raw(
        enum_name: str,
        value: int,
        schema_registry: MemoryPackSchemaRegistry | None,
    ) -> str | int:
        if schema_registry is None:
            return value
        enum_type = schema_registry.resolve_enum(enum_name)
        if enum_type is None:
            return value
        try:
            return enum_type(value).name
        except ValueError:
            return value

    def _read_member_value(self, cs_type: str, annotation: Any) -> Any:
        normalized = MemoryPackCSParser._normalize_cs_type(cs_type)
        if inner := MemoryPackCSParser._extract_generic_inner(
            normalized,
            (
                "System.Collections.Generic.List",
                "System.Collections.Generic.IReadOnlyList",
                "System.Collections.Generic.IList",
                "List",
            ),
        ):
            length = self.read_collection_header()
            if length is None:
                return None
            return [self._read_member_value(inner, self._list_arg(annotation)) for _ in range(length)]

        if normalized.endswith("[]"):
            length = self.read_collection_header()
            if length is None:
                return None
            inner = normalized.removesuffix("[]")
            return [
                self._read_member_value(inner, self._list_arg(annotation))
                for _ in range(length)
            ]

        if inner := MemoryPackCSParser._extract_generic_inner(
            normalized,
            (
                "System.Collections.Generic.Dictionary",
                "System.Collections.Generic.IReadOnlyDictionary",
                "Dictionary",
            ),
        ):
            length = self.read_collection_header()
            if length is None:
                return None
            key_type, value_type = MemoryPackCSParser._split_generic_arguments(inner)
            key_annotation, value_annotation = self._dict_args(annotation)
            return {
                self._read_member_value(key_type, key_annotation): self._read_member_value(
                    value_type, value_annotation
                )
                for _ in range(length)
            }

        if normalized in {"string", "System.String"}:
            return self.read_string()
        if normalized in {"bool", "System.Boolean"}:
            return self.read_bool()
        if normalized in {"byte", "System.Byte"}:
            return self.read_uint8()
        if normalized in {"sbyte", "System.SByte"}:
            return struct.unpack("<b", self._read_exact(1))[0]
        if normalized in {"short", "System.Int16"}:
            return self.read_int16()
        if normalized in {"ushort", "System.UInt16"}:
            return self.read_uint16()
        if normalized in {"int", "System.Int32"}:
            return self.read_int32()
        if normalized in {"uint", "System.UInt32"}:
            return self.read_uint32()
        if normalized in {"long", "System.Int64"}:
            return self.read_int64()
        if normalized in {"ulong", "System.UInt64"}:
            return self.read_uint64()
        if normalized in {"float", "System.Single"}:
            return self.read_float32()
        if normalized in {"double", "System.Double"}:
            return self.read_float64()

        object_type = self._object_type(annotation)
        if object_type is int:
            return self.read_int32()
        if object_type is float:
            return self.read_float32()
        if object_type is bool:
            return self.read_bool()
        if object_type is str:
            return self.read_string()
        if isinstance(object_type, type) and issubclass(object_type, IntEnum):
            enum_value = self._read_enum_value(object_type)
            return object_type(enum_value)
        if isinstance(object_type, type) and is_dataclass(object_type):
            return self.read_object(object_type)
        raise TypeError(f"Unsupported MemoryPack member type: {cs_type}.")

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

        if formatter.kind == "union":
            return self._read_formatter_union(
                formatter,
                schema_registry,
                formatter_registry,
            )
        if formatter.kind == "object":
            return self._read_formatter_members(
                formatter,
                schema_registry,
                formatter_registry,
            )
        raise ValueError(f"Unsupported MemoryPack formatter kind: {formatter.kind}.")

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
        if normalized in {"byte", "System.Byte"}:
            return self.read_uint8()
        if normalized in {"sbyte", "System.SByte"}:
            return struct.unpack("<b", self._read_exact(1))[0]
        if normalized in {"short", "System.Int16"}:
            return self.read_int16()
        if normalized in {"ushort", "System.UInt16"}:
            return self.read_uint16()
        if normalized in {"uint", "System.UInt32"}:
            return self.read_uint32()
        if normalized in {"long", "System.Int64"}:
            return self.read_int64()
        if normalized in {"ulong", "System.UInt64"}:
            return self.read_uint64()
        return self.read_int32()

    def _read_formatter_members(
        self,
        formatter: MemoryPackFormatterDescriptor,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"__type__": formatter.target_type}
        member_count: int | None = None
        if formatter.object_header:
            member_count = self.read_object_header()
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
        if inner := MemoryPackCSParser._extract_generic_inner(
            normalized,
            (
                "System.Collections.Generic.List",
                "System.Collections.Generic.IReadOnlyList",
                "System.Collections.Generic.IList",
                "List",
            ),
        ):
            length = self.read_collection_header()
            if length is None:
                return None
            return [
                self._read_formatter_value(
                    inner,
                    schema_registry,
                    formatter_registry,
                )
                for _ in range(length)
            ]

        if normalized.endswith("[]"):
            length = self.read_collection_header()
            if length is None:
                return None
            inner = normalized.removesuffix("[]")
            return [
                self._read_formatter_value(
                    inner,
                    schema_registry,
                    formatter_registry,
                )
                for _ in range(length)
            ]

        if inner := MemoryPackCSParser._extract_generic_inner(
            normalized,
            (
                "System.Collections.Generic.Dictionary",
                "System.Collections.Generic.IReadOnlyDictionary",
                "Dictionary",
            ),
        ):
            length = self.read_collection_header()
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

        if normalized in {"string", "System.String"}:
            return self.read_string()
        if normalized in {"bool", "System.Boolean"}:
            return self.read_bool()
        if normalized in {"byte", "System.Byte"}:
            return self.read_uint8()
        if normalized in {"sbyte", "System.SByte"}:
            return struct.unpack("<b", self._read_exact(1))[0]
        if normalized in {"short", "System.Int16"}:
            return self.read_int16()
        if normalized in {"ushort", "System.UInt16"}:
            return self.read_uint16()
        if normalized in {"int", "System.Int32"}:
            return self.read_int32()
        if normalized in {"uint", "System.UInt32"}:
            return self.read_uint32()
        if normalized in {"long", "System.Int64"}:
            return self.read_int64()
        if normalized in {"ulong", "System.UInt64"}:
            return self.read_uint64()
        if normalized in {"float", "System.Single"}:
            return self.read_float32()
        if normalized in {"double", "System.Double"}:
            return self.read_float64()

        if enum_type := schema_registry.resolve_enum(normalized):
            enum_value = self._read_enum_value(enum_type)
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
            return self._to_json_value(self.read_object(schema_type))

        raise TypeError(f"Unsupported MemoryPack formatter member type: {cs_type}.")

    def _read_enum_value(self, enum_type: type[IntEnum]) -> int:
        enum_metadata = getattr(enum_type, "__memorypack_enum__", None)
        underlying_type = getattr(enum_metadata, "underlying_type", "System.Int32")
        normalized = MemoryPackCSParser._normalize_cs_type(underlying_type)
        if normalized in {"byte", "System.Byte"}:
            return self.read_uint8()
        if normalized in {"sbyte", "System.SByte"}:
            return struct.unpack("<b", self._read_exact(1))[0]
        if normalized in {"short", "System.Int16"}:
            return self.read_int16()
        if normalized in {"ushort", "System.UInt16"}:
            return self.read_uint16()
        if normalized in {"uint", "System.UInt32"}:
            return self.read_uint32()
        if normalized in {"long", "System.Int64"}:
            return self.read_int64()
        if normalized in {"ulong", "System.UInt64"}:
            return self.read_uint64()
        return self.read_int32()

    @classmethod
    def _to_json_value(cls, value: Any) -> Any:
        if isinstance(value, IntEnum):
            return value.name
        if is_dataclass(value):
            metadata = getattr(value, "__memorypack_type__", None)
            type_name = getattr(metadata, "name", value.__class__.__name__)
            namespace = getattr(metadata, "namespace", "")
            full_name = f"{namespace}.{type_name}" if namespace else type_name
            result: dict[str, Any] = {"__type__": full_name}
            for field in fields(value):
                result[field.name] = cls._to_json_value(getattr(value, field.name))
            return result
        if isinstance(value, list):
            return [cls._to_json_value(item) for item in value]
        if isinstance(value, dict):
            return {
                cls._to_json_value(key): cls._to_json_value(item)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _schema_members(
        schema_type: type[Any],
    ) -> list[tuple[str, MemoryPackMember, Any]]:
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

    @classmethod
    def _list_arg(cls, annotation: Any) -> Any:
        object_type = cls._object_type(annotation)
        origin = get_origin(object_type)
        if origin is list:
            return get_args(object_type)[0]
        return Any

    @classmethod
    def _dict_args(cls, annotation: Any) -> tuple[Any, Any]:
        object_type = cls._object_type(annotation)
        origin = get_origin(object_type)
        if origin is dict:
            args = get_args(object_type)
            return args[0], args[1]
        return Any, Any

    @staticmethod
    def _object_type(annotation: Any) -> Any:
        origin = get_origin(annotation)
        if origin in {UnionType, Union}:
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if args:
                return args[0]
        return annotation
