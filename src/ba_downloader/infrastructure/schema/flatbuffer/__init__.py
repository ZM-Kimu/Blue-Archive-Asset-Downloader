"""FlatBuffer dump.cs schema parser, generator, and reader."""

from ba_downloader.infrastructure.schema.flatbuffer.descriptors import (
    FlatBufferEnumDescriptor,
    FlatBufferEnumMemberDescriptor,
    FlatBufferEnumMemberMetadata,
    FlatBufferEnumMetadata,
    FlatBufferField,
    FlatBufferFieldDescriptor,
    FlatBufferTypeDescriptor,
    FlatBufferTypeMetadata,
)
from ba_downloader.infrastructure.schema.flatbuffer.generator import (
    CompileFlatBufferToPython,
)
from ba_downloader.infrastructure.schema.flatbuffer.parser import FlatBufferCSParser
from ba_downloader.infrastructure.schema.flatbuffer.reader import (
    FlatBufferExporter,
    FlatBufferReader,
)

__all__ = [
    "CompileFlatBufferToPython",
    "FlatBufferCSParser",
    "FlatBufferEnumDescriptor",
    "FlatBufferEnumMemberDescriptor",
    "FlatBufferEnumMemberMetadata",
    "FlatBufferEnumMetadata",
    "FlatBufferExporter",
    "FlatBufferField",
    "FlatBufferFieldDescriptor",
    "FlatBufferReader",
    "FlatBufferTypeDescriptor",
    "FlatBufferTypeMetadata",
]
