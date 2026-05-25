from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class TablePayloadCodec(Enum):
    FLATBUFFER = "flatbuffer"
    MEMORYPACK = "memorypack"


@dataclass(frozen=True, slots=True)
class TablePayloadRoute:
    codec: TablePayloadCodec
    root_type: str = ""
    allow_partial_memorypack: bool = False


class TablePayloadRouter:
    """Route known table BLOB payloads to the currently verified codec.

    This is intentionally source-specific for now. CN/GL/JP table payloads still
    have region-specific container and serialization differences, so each route
    must be backed by a verified extractor. Once those formats are covered well
    enough, this class should become the single unified payload router instead of
    a collection of regional special cases.
    """

    CN_MEMORYPACK_DB_ROOT_TYPES: ClassVar[dict[str, str]] = {
        "LevelSkillDataDBSchema.db": "MX.GameData.DAO.Battle.SkillLogicDAO",
        "LogicEffectDataDBSchema.db": "MX.GameData.DAO.Battle.LogicEffectDAO",
        "SkillVisualEffectDataDBSchema.db": "MX.AppData.DAO.Battle.SkillVisualDAO",
    }

    def resolve_database_blob(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
    ) -> TablePayloadRoute:
        _ = table_name
        if column_name == "Bytes" and (
            root_type := self.CN_MEMORYPACK_DB_ROOT_TYPES.get(db_name)
        ):
            return TablePayloadRoute(
                codec=TablePayloadCodec.MEMORYPACK,
                root_type=root_type,
                allow_partial_memorypack=True,
            )
        return TablePayloadRoute(codec=TablePayloadCodec.FLATBUFFER)
