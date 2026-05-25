from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any, ClassVar

from ba_downloader.infrastructure.schema.memorypack.cursor import (
    NULL_COLLECTION_HEADER,
    MemoryPackCursor,
)
from ba_downloader.infrastructure.schema.memorypack.registry import (
    MemoryPackSchemaRegistry,
)

PartialReader = Callable[
    ["CnPartialDaoFallbackReader", str, MemoryPackSchemaRegistry | None],
    dict[str, Any],
]


class CnPartialDaoFallbackReader:
    _ROOT_READERS: ClassVar[dict[str, PartialReader]] = {}

    def __init__(self, cursor: MemoryPackCursor) -> None:
        self._cursor = cursor

    def read_partial(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry | None = None,
    ) -> dict[str, Any]:
        reader = self._ROOT_READERS.get(root_type)
        if reader is None:
            raise ValueError(f"Unsupported CN table MemoryPack root type: {root_type}.")
        return reader(self, root_type, schema_registry)

    def _read_skill_visual_dao_partial(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry | None,
    ) -> dict[str, Any]:
        _ = schema_registry
        object_header = self._read_required_object_header(root_type)
        result = self._partial_base(root_type)
        result["__object_header__"] = object_header
        result["name"] = self._cursor.read_string()
        result["VisualDataKey"] = self._cursor.read_string()
        result["GuidePrefabPath"] = self._cursor.read_string()
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

    def _read_skill_logic_dao_partial(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry | None,
    ) -> dict[str, Any]:
        _ = schema_registry
        union_tag = self._cursor.read_uint8()
        object_header = self._read_required_object_header(root_type)
        result = self._partial_base(root_type)
        result["__union_tag__"] = union_tag
        result["__object_header__"] = object_header
        result["name"] = self._cursor.read_string()
        result["SkillDataKey"] = self._cursor.read_string()
        self._finish_partial_result(result, known_member_count=2)
        return result

    def _read_logic_effect_dao_partial(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry | None,
    ) -> dict[str, Any]:
        union_tag = self._cursor.read_uint8()
        object_header = self._read_required_object_header(root_type)
        result = self._partial_base(root_type)
        result["__union_tag__"] = union_tag
        result["__object_header__"] = object_header
        result["Level"] = self._cursor.read_int32()
        result["GroupId"] = self._cursor.read_string()
        category_value = self._cursor.read_int32()
        result["Category"] = self._enum_name_or_raw(
            "FlatData.LogicEffectCategory",
            category_value,
            schema_registry,
        )
        result["TemplateId"] = self._cursor.read_string()
        result["Channel"] = self._cursor.read_int32()
        result["ApplyRate"] = self._cursor.read_int64()
        result["CommonVisualId"] = self._cursor.read_int64()
        result["CommonVisualHash"] = self._cursor.read_int64()
        result["PriorityWhenSameFrame"] = self._cursor.read_int32()
        self._finish_partial_result(result, known_member_count=9)
        return result

    def _read_required_object_header(self, root_type: str) -> int:
        object_header = self._cursor.read_object_header()
        if object_header is None:
            raise ValueError(f"Unexpected null MemoryPack object for {root_type}.")
        return object_header

    def _try_read_empty_collection(self) -> tuple[bool, list[Any] | None]:
        if len(self._cursor.payload) - self._cursor.offset < 4:
            return False, None
        length = self._cursor.peek_int32()
        if length == NULL_COLLECTION_HEADER:
            self._cursor.read_int32()
            return True, None
        if length == 0:
            self._cursor.read_int32()
            return True, []
        return False, None

    def _finish_partial_result(
        self,
        result: dict[str, Any],
        *,
        known_member_count: int,
    ) -> None:
        remaining_size = len(self._cursor.payload) - self._cursor.offset
        object_header = result.get("__object_header__")
        result["__remaining_offset__"] = self._cursor.offset
        result["__remaining_size__"] = remaining_size
        result["__partial_memorypack__"] = bool(
            remaining_size
            or (isinstance(object_header, int) and object_header > known_member_count)
        )

    def _partial_base(self, root_type: str) -> dict[str, Any]:
        return {
            "__type__": root_type,
            "__root_type__": root_type,
            "__payload_size__": len(self._cursor.payload),
            "__payload_sha256__": hashlib.sha256(self._cursor.payload).hexdigest(),
            "__payload_head__": self._cursor.payload[:64].hex(),
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


CnPartialDaoFallbackReader._ROOT_READERS = {
    "MX.AppData.DAO.Battle.SkillVisualDAO": (
        CnPartialDaoFallbackReader._read_skill_visual_dao_partial
    ),
    "MX.GameData.DAO.Battle.SkillLogicDAO": (
        CnPartialDaoFallbackReader._read_skill_logic_dao_partial
    ),
    "MX.GameData.DAO.Battle.LogicEffectDAO": (
        CnPartialDaoFallbackReader._read_logic_effect_dao_partial
    ),
}
