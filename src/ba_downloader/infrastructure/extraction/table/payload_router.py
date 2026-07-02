from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class TablePayloadCodec(Enum):
    FLATBUFFER = "flatbuffer"
    MEMORYPACK = "memorypack"


@dataclass(frozen=True, slots=True)
class TablePayloadRoute:
    codec: TablePayloadCodec
    root_type: str = ""
    allow_partial_memorypack: bool = False


class TablePayloadRouter(Protocol):
    def resolve_database_blob(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
    ) -> TablePayloadRoute: ...


MEMORYPACK_DB_ROOT_TYPES = {
    "LevelSkillDataDBSchema.db": "MX.GameData.DAO.Battle.SkillLogicDAO",
    "LogicEffectDataDBSchema.db": "MX.GameData.DAO.Battle.LogicEffectDAO",
    "SkillVisualEffectDataDBSchema.db": "MX.AppData.DAO.Battle.SkillVisualDAO",
}


class FlatBufferTablePayloadRouter:
    def resolve_database_blob(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
    ) -> TablePayloadRoute:
        _ = (db_name, table_name, column_name)
        return TablePayloadRoute(codec=TablePayloadCodec.FLATBUFFER)


class JpTablePayloadRouter:
    def resolve_database_blob(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
    ) -> TablePayloadRoute:
        _ = table_name
        if column_name == "Bytes" and (
            root_type := MEMORYPACK_DB_ROOT_TYPES.get(db_name)
        ):
            return TablePayloadRoute(
                codec=TablePayloadCodec.MEMORYPACK,
                root_type=root_type,
                allow_partial_memorypack=False,
            )
        return TablePayloadRoute(codec=TablePayloadCodec.FLATBUFFER)


class CnLegacyTablePayloadRouter:
    def resolve_database_blob(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
    ) -> TablePayloadRoute:
        _ = table_name
        if column_name == "Bytes" and (
            root_type := MEMORYPACK_DB_ROOT_TYPES.get(db_name)
        ):
            return TablePayloadRoute(
                codec=TablePayloadCodec.MEMORYPACK,
                root_type=root_type,
                allow_partial_memorypack=True,
            )
        return TablePayloadRoute(codec=TablePayloadCodec.FLATBUFFER)
