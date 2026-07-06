from __future__ import annotations

from collections.abc import Mapping
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


class FlatBufferTablePayloadRouter:
    def resolve_database_blob(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
    ) -> TablePayloadRoute:
        _ = (db_name, table_name, column_name)
        return TablePayloadRoute(codec=TablePayloadCodec.FLATBUFFER)


class MemoryPackTablePayloadRouter:
    def __init__(
        self,
        db_root_types: Mapping[str, str],
        *,
        allow_partial_memorypack: bool,
    ) -> None:
        self.db_root_types = dict(db_root_types)
        self.allow_partial_memorypack = allow_partial_memorypack

    def resolve_database_blob(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
    ) -> TablePayloadRoute:
        _ = table_name
        if column_name == "Bytes" and (root_type := self.db_root_types.get(db_name)):
            return TablePayloadRoute(
                codec=TablePayloadCodec.MEMORYPACK,
                root_type=root_type,
                allow_partial_memorypack=self.allow_partial_memorypack,
            )
        return TablePayloadRoute(codec=TablePayloadCodec.FLATBUFFER)
