from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class DatabaseSourceIdentity:
    region: str
    platform: str
    release: str
    size: int
    checksum: str
    exporter_fingerprint: str = ""
    key_id: str = ""


@dataclass
class DBColumn:
    name: str
    data_type: str


@dataclass
class DBTable:
    name: str
    columns: list[DBColumn]
    data: list[list]


class SQLiteDataType(Enum):
    INTEGER = int
    REAL = float
    NUMERIC = float
    TEXT = str
    BLOB = bytes
    BOOLEAN = bool
    NULL = None
