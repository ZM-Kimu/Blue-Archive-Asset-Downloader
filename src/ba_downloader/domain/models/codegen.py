from dataclasses import dataclass


@dataclass
class Property:
    data_type: str
    name: str
    is_list: bool


@dataclass
class StructTable:
    name: str
    properties: list[Property]


@dataclass
class EnumMember:
    name: str
    value: str


@dataclass
class EnumType:
    name: str
    underlying_type: str
    members: list[EnumMember]
