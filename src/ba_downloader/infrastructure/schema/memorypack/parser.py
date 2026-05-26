from __future__ import annotations

import re
from pathlib import Path

from ba_downloader.infrastructure.schema.common.csharp import (
    extract_generic_inner,
    normalize_cs_type,
    primitive_python_type,
    split_generic_arguments,
    strip_generic_arity,
    strip_member_type_modifiers,
)
from ba_downloader.infrastructure.schema.common.parser import (
    iter_dump_blocks,
    parse_enum_member_rows,
)
from ba_downloader.infrastructure.schema.memorypack.descriptors import (
    MemoryPackEnumDescriptor,
    MemoryPackEnumMemberDescriptor,
    MemoryPackMemberDescriptor,
    MemoryPackTypeDescriptor,
)


class MemoryPackCSParser:
    TYPE_MODIFIERS = frozenset(
        {
            "abstract",
            "async",
            "extern",
            "new",
            "override",
            "readonly",
            "sealed",
            "static",
            "unsafe",
            "virtual",
            "volatile",
        }
    )
    TYPE_PATTERN = re.compile(
        r"^(?P<prefix>(?:public|private|internal|protected)\s+"
        r"(?:(?:sealed|abstract|partial|readonly|static)\s+)*)"
        r"(?P<kind>class|struct)\s+"
        r"(?P<name>[A-Za-z_][\w`.]*)"
        r"(?:\s*:\s*(?P<bases>.*?))?\s*//\s*"
        r"TypeDefIndex:\s*(?P<type_def_index>\d+),?\s+"
        r"Token:\s*(?P<token>0x[0-9A-Fa-f]+)",
    )
    ENUM_PATTERN = re.compile(
        r"^(?P<prefix>(?:public|private|internal|protected)\s+"
        r"(?:(?:sealed|abstract|partial|readonly|static)\s+)*)"
        r"enum\s+"
        r"(?P<name>[A-Za-z_][\w`.]*)\s*//\s*"
        r"TypeDefIndex:\s*(?P<type_def_index>\d+),?\s+"
        r"Token:\s*(?P<token>0x[0-9A-Fa-f]+)",
    )
    NAMESPACE_PATTERN = re.compile(r"^//\s*Namespace:\s*(?P<namespace>.*)$")
    BACKING_FIELD_PATTERN = re.compile(
        r"^\s*(?:private|public|protected|internal)?\s*"
        r"(?P<type>.+?)\s+"
        r"(?:_(?P<underscore_name>.+?)_k__BackingField|"
        r"<(?P<angle_name>.+?)>k__BackingField);\s*"
        r"//.*?Token:\s*(?P<token>0x[0-9A-Fa-f]+)"
    )
    PROPERTY_PATTERN = re.compile(
        r"^\s*public\s+(?P<type>.+?)\s+"
        r"(?P<name>[A-Za-z_][\w]*)\s+"
        r"\{\s*get;\s*(?:set;\s*)?\}\s*"
        r"//\s*Token:\s*(?P<token>0x[0-9A-Fa-f]+)"
    )
    FIELD_PATTERN = re.compile(
        r"^\s*(?P<modifiers>(?:(?:private|public|protected|internal|readonly|"
        r"volatile|static|const)\s+)*)"
        r"(?P<type>.+?)\s+"
        r"(?P<name>[A-Za-z_][\w]*)"
        r"(?:\s*=\s*[^;]+)?;\s*"
        r"//.*?Token:\s*(?P<token>0x[0-9A-Fa-f]+)"
    )
    ENUM_VALUE_PATTERN = re.compile(r"^\s*public\s+(?P<type>.+?)\s+value__;\s*//")
    ENUM_MEMBER_PATTERN = re.compile(
        r"^\s*public\s+(?:static\s+)?const\s+"
        r"(?P<type>.+?)\s+"
        r"(?P<name>[A-Za-z_][\w]*)"
        r"(?:\s*=\s*(?P<value>-?\d+))?;\s*"
        r"//.*?Token:\s*(?P<token>0x[0-9A-Fa-f]+)"
    )

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.data = Path(file_path).read_text(encoding="utf8")

    def parse_types(self) -> list[MemoryPackTypeDescriptor]:
        descriptors: list[MemoryPackTypeDescriptor] = []
        for block in iter_dump_blocks(
            self.data,
            namespace_pattern=self.NAMESPACE_PATTERN,
            header_pattern=self.TYPE_PATTERN,
            include_header=lambda _match, line: "MemoryPack.IMemoryPackable" in line,
        ):
            descriptors.append(
                self._build_descriptor(
                    block.namespace,
                    block.header_match,
                    block.body_lines,
                )
            )

        return descriptors

    def parse_enums(self) -> list[MemoryPackEnumDescriptor]:
        descriptors: list[MemoryPackEnumDescriptor] = []
        for block in iter_dump_blocks(
            self.data,
            namespace_pattern=self.NAMESPACE_PATTERN,
            header_pattern=self.ENUM_PATTERN,
        ):
            descriptors.append(
                self._build_enum_descriptor(
                    block.namespace,
                    block.header_match,
                    block.body_lines,
                )
            )

        return descriptors

    def _build_descriptor(
        self,
        namespace: str,
        type_match: re.Match[str],
        body_lines: list[str],
    ) -> MemoryPackTypeDescriptor:
        bases = self._split_interfaces(type_match.group("bases") or "")
        imemorypack_index = next(
            (
                index
                for index, item in enumerate(bases)
                if item.startswith("MemoryPack.IMemoryPackable")
            ),
            len(bases),
        )
        base_type = bases[0] if imemorypack_index > 0 and bases else None
        members = self._parse_members(body_lines)
        original_name = type_match.group("name")
        return MemoryPackTypeDescriptor(
            name=self._strip_generic_arity(original_name),
            namespace=namespace,
            kind=type_match.group("kind"),
            original_name=original_name,
            base_type=base_type,
            interfaces=tuple(bases),
            type_def_index=int(type_match.group("type_def_index")),
            token=type_match.group("token"),
            members=members,
        )

    @classmethod
    def _build_enum_descriptor(
        cls,
        namespace: str,
        enum_match: re.Match[str],
        body_lines: list[str],
    ) -> MemoryPackEnumDescriptor:
        underlying_type, member_rows = parse_enum_member_rows(
            body_lines,
            enum_value_pattern=cls.ENUM_VALUE_PATTERN,
            enum_member_pattern=cls.ENUM_MEMBER_PATTERN,
        )
        members = [
            MemoryPackEnumMemberDescriptor(
                name=row.name,
                value=row.value,
                token=row.token,
            )
            for row in member_rows
        ]

        original_name = enum_match.group("name")
        return MemoryPackEnumDescriptor(
            name=cls._strip_generic_arity(original_name),
            namespace=namespace,
            original_name=original_name,
            underlying_type=underlying_type,
            type_def_index=int(enum_match.group("type_def_index")),
            token=enum_match.group("token"),
            members=members,
        )

    @classmethod
    def _parse_members(
        cls,
        body_lines: list[str],
    ) -> list[MemoryPackMemberDescriptor]:
        backing_field_tokens: dict[str, str] = {}
        for line in body_lines:
            if field_match := cls.BACKING_FIELD_PATTERN.match(line):
                field_name = field_match.group("underscore_name") or field_match.group(
                    "angle_name"
                )
                backing_field_tokens[field_name] = field_match.group("token")

        members: list[MemoryPackMemberDescriptor] = []
        for line in body_lines:
            property_match = cls.PROPERTY_PATTERN.match(line)
            if property_match is None:
                continue
            member_name = property_match.group("name")
            cs_type = cls._strip_member_type_modifiers(property_match.group("type"))
            members.append(
                MemoryPackMemberDescriptor(
                    index=len(members),
                    name=member_name,
                    cs_type=cs_type,
                    python_type=cls.to_python_type(cs_type),
                    member_token=property_match.group("token"),
                    backing_field_token=backing_field_tokens.get(member_name, ""),
                )
            )
        if members:
            return members

        return cls._parse_field_members(body_lines)

    @classmethod
    def _parse_field_members(
        cls,
        body_lines: list[str],
    ) -> list[MemoryPackMemberDescriptor]:
        members: list[MemoryPackMemberDescriptor] = []
        for line in body_lines:
            field_match = cls.FIELD_PATTERN.match(line)
            if field_match is None:
                continue

            modifiers = set(field_match.group("modifiers").split())
            if modifiers.intersection({"const", "static"}):
                continue

            field_name = field_match.group("name")
            if "k__BackingField" in field_name:
                continue

            cs_type = cls._strip_member_type_modifiers(field_match.group("type"))
            token = field_match.group("token")
            members.append(
                MemoryPackMemberDescriptor(
                    index=len(members),
                    name=field_name,
                    cs_type=cs_type,
                    python_type=cls.to_python_type(cs_type),
                    member_token=token,
                    backing_field_token=token,
                )
            )
        return members

    @staticmethod
    def _split_interfaces(value: str) -> list[str]:
        return split_generic_arguments(value)

    @staticmethod
    def _strip_generic_arity(type_name: str) -> str:
        return strip_generic_arity(type_name)

    @classmethod
    def _strip_member_type_modifiers(cls, cs_type: str) -> str:
        return strip_member_type_modifiers(cs_type, cls.TYPE_MODIFIERS)

    @classmethod
    def to_python_type(cls, cs_type: str) -> str:
        normalized = cls._normalize_cs_type(cs_type)
        primitive = primitive_python_type(
            normalized,
            extra={"string": "str | None", "System.String": "str | None"},
        )
        if primitive:
            return primitive

        if list_inner := cls._extract_generic_inner(
            normalized,
            (
                "System.Collections.Generic.List",
                "System.Collections.Generic.IReadOnlyList",
                "System.Collections.Generic.IList",
                "List",
            ),
        ):
            return f"list[{cls._container_inner_python_type(list_inner)}] | None"

        if dictionary_inner := cls._extract_generic_inner(
            normalized,
            (
                "System.Collections.Generic.Dictionary",
                "System.Collections.Generic.IReadOnlyDictionary",
                "Dictionary",
            ),
        ):
            key_type, value_type = cls._split_generic_arguments(dictionary_inner)
            return (
                "dict["
                f"{cls._container_inner_python_type(key_type)}, "
                f"{cls._container_inner_python_type(value_type)}"
                "] | None"
            )

        if normalized.endswith("[]"):
            inner = normalized.removesuffix("[]")
            return f"list[{cls._container_inner_python_type(inner)}] | None"

        return "Any"

    @staticmethod
    def _normalize_cs_type(cs_type: str) -> str:
        return normalize_cs_type(
            cs_type,
            modifiers=MemoryPackCSParser.TYPE_MODIFIERS,
        )

    @classmethod
    def _container_inner_python_type(cls, cs_type: str) -> str:
        python_type = cls.to_python_type(cs_type)
        return python_type.removesuffix(" | None")

    @staticmethod
    def _extract_generic_inner(value: str, names: tuple[str, ...]) -> str:
        return extract_generic_inner(value, names)

    @classmethod
    def _split_generic_arguments(cls, value: str) -> tuple[str, str]:
        args = split_generic_arguments(value)
        if len(args) < 2:
            return "Any", "Any"
        return args[0], args[1]
