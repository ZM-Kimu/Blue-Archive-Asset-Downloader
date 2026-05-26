from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.infrastructure.schema.common.identifiers import make_valid_identifier


@dataclass(frozen=True, slots=True)
class MemoryPackMember:
    index: int
    cs_type: str
    type_name: str = ""
    namespace: str = ""
    member_token: str = ""
    backing_field_token: str = ""
    original_name: str = ""


@dataclass(frozen=True, slots=True)
class MemoryPackTypeMetadata:
    name: str
    namespace: str
    kind: str
    original_name: str
    base_type: str | None
    interfaces: tuple[str, ...]
    type_def_index: int
    token: str


@dataclass(frozen=True, slots=True)
class MemoryPackEnumMemberMetadata:
    name: str
    python_name: str
    value: int
    token: str


@dataclass(frozen=True, slots=True)
class MemoryPackEnumMetadata:
    name: str
    namespace: str
    original_name: str
    underlying_type: str
    type_def_index: int
    token: str
    members: tuple[MemoryPackEnumMemberMetadata, ...]


@dataclass(frozen=True, slots=True)
class MemoryPackMemberDescriptor:
    index: int
    name: str
    cs_type: str
    python_type: str
    member_token: str
    backing_field_token: str = ""


@dataclass(frozen=True, slots=True)
class MemoryPackTypeDescriptor:
    name: str
    namespace: str
    kind: str
    original_name: str
    base_type: str | None
    interfaces: tuple[str, ...]
    type_def_index: int
    token: str
    members: list[MemoryPackMemberDescriptor]

    @property
    def python_name(self) -> str:
        return make_valid_identifier(self.name)

    @property
    def full_name(self) -> str:
        if self.namespace:
            return f"{self.namespace}.{self.original_name}"
        return self.original_name


@dataclass(frozen=True, slots=True)
class MemoryPackEnumMemberDescriptor:
    name: str
    value: int
    token: str


@dataclass(frozen=True, slots=True)
class MemoryPackEnumDescriptor:
    name: str
    namespace: str
    original_name: str
    underlying_type: str
    type_def_index: int
    token: str
    members: list[MemoryPackEnumMemberDescriptor]

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
