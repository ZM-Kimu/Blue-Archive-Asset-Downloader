from __future__ import annotations

import re
from dataclasses import dataclass

from ba_downloader.infrastructure.schema.common.identifiers import make_valid_identifier


def make_enum_member_identifier(member_name: str) -> str:
    identifier = make_valid_identifier(member_name)
    if re.fullmatch(r"_[^_].*_", identifier):
        identifier = f"{identifier.strip('_')}_"
    elif identifier.startswith("_"):
        identifier = identifier.lstrip("_")
    if not identifier:
        identifier = "Value"
    return make_valid_identifier(identifier)


@dataclass(frozen=True, slots=True)
class FlatBufferField:
    index: int
    cs_type: str
    type_name: str = ""
    namespace: str = ""
    member_token: str = ""
    original_name: str = ""
    is_vector: bool = False


@dataclass(frozen=True, slots=True)
class FlatBufferTypeMetadata:
    name: str
    namespace: str
    kind: str
    original_name: str
    type_def_index: int
    token: str


@dataclass(frozen=True, slots=True)
class FlatBufferEnumMemberMetadata:
    name: str
    python_name: str
    value: int
    token: str


@dataclass(frozen=True, slots=True)
class FlatBufferEnumMetadata:
    name: str
    namespace: str
    original_name: str
    underlying_type: str
    type_def_index: int
    token: str
    members: tuple[FlatBufferEnumMemberMetadata, ...]


@dataclass(frozen=True, slots=True)
class FlatBufferFieldDescriptor:
    index: int
    name: str
    cs_type: str
    python_type: str
    member_token: str = ""
    is_vector: bool = False


@dataclass(frozen=True, slots=True)
class FlatBufferTypeDescriptor:
    name: str
    namespace: str
    kind: str
    original_name: str
    type_def_index: int
    token: str
    fields: list[FlatBufferFieldDescriptor]

    @property
    def python_name(self) -> str:
        return make_valid_identifier(self.name)

    @property
    def full_name(self) -> str:
        if self.namespace:
            return f"{self.namespace}.{self.original_name}"
        return self.original_name


@dataclass(frozen=True, slots=True)
class FlatBufferEnumMemberDescriptor:
    name: str
    value: int
    token: str


@dataclass(frozen=True, slots=True)
class FlatBufferEnumDescriptor:
    name: str
    namespace: str
    original_name: str
    underlying_type: str
    type_def_index: int
    token: str
    members: list[FlatBufferEnumMemberDescriptor]

    @property
    def python_name(self) -> str:
        return make_valid_identifier(self.name)

    @property
    def full_name(self) -> str:
        if self.namespace:
            return f"{self.namespace}.{self.original_name}"
        return self.original_name


@dataclass(frozen=True, slots=True)
class PythonTypeRender:
    annotation: str
    imports: frozenset[str]
