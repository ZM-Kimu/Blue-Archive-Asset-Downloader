from __future__ import annotations

import struct
from collections.abc import Callable
from typing import Any

NULL_OBJECT_HEADER = 255
NULL_COLLECTION_HEADER = -1

PrimitiveReader = Callable[["MemoryPackCursor"], Any]


class MemoryPackCursor:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

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

    def read_int8(self) -> int:
        return struct.unpack("<b", self._read_exact(1))[0]

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


INTEGER_READERS: dict[str, PrimitiveReader] = {
    "byte": MemoryPackCursor.read_uint8,
    "System.Byte": MemoryPackCursor.read_uint8,
    "sbyte": MemoryPackCursor.read_int8,
    "System.SByte": MemoryPackCursor.read_int8,
    "short": MemoryPackCursor.read_int16,
    "System.Int16": MemoryPackCursor.read_int16,
    "ushort": MemoryPackCursor.read_uint16,
    "System.UInt16": MemoryPackCursor.read_uint16,
    "int": MemoryPackCursor.read_int32,
    "System.Int32": MemoryPackCursor.read_int32,
    "uint": MemoryPackCursor.read_uint32,
    "System.UInt32": MemoryPackCursor.read_uint32,
    "long": MemoryPackCursor.read_int64,
    "System.Int64": MemoryPackCursor.read_int64,
    "ulong": MemoryPackCursor.read_uint64,
    "System.UInt64": MemoryPackCursor.read_uint64,
}

PRIMITIVE_READERS: dict[str, PrimitiveReader] = {
    "string": MemoryPackCursor.read_string,
    "System.String": MemoryPackCursor.read_string,
    "bool": MemoryPackCursor.read_bool,
    "System.Boolean": MemoryPackCursor.read_bool,
    **INTEGER_READERS,
    "float": MemoryPackCursor.read_float32,
    "System.Single": MemoryPackCursor.read_float32,
    "double": MemoryPackCursor.read_float64,
    "System.Double": MemoryPackCursor.read_float64,
}
