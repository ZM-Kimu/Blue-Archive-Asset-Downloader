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
    MemoryPackCollectionFormatterDescriptor,
    MemoryPackEnumDescriptor,
    MemoryPackEnumMemberDescriptor,
    MemoryPackMemberDescriptor,
    MemoryPackTypeDescriptor,
)


class MemoryPackCSParser:
    KEYED_COLLECTION_GENERIC_NAMES = (
        "System.Collections.ObjectModel.KeyedCollection",
        "KeyedCollection",
    )
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
        self._declared_type_names: set[str] | None = None

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

    def parse_collection_formatters(
        self,
    ) -> list[MemoryPackCollectionFormatterDescriptor]:
        descriptors: list[MemoryPackCollectionFormatterDescriptor] = []
        for block in iter_dump_blocks(
            self.data,
            namespace_pattern=self.NAMESPACE_PATTERN,
            header_pattern=self.TYPE_PATTERN,
            include_header=lambda _match, line: (
                "MemoryPack.IMemoryPackFormatterRegister" in line
                and "KeyedCollection" in line
            ),
        ):
            bases = self._split_interfaces(
                block.header_match.group("bases") or "",
            )
            collection_base = next(
                (
                    item
                    for item in bases
                    if self._extract_generic_inner(
                        self._normalize_cs_type(item),
                        self.KEYED_COLLECTION_GENERIC_NAMES,
                    )
                ),
                "",
            )
            collection_inner = self._extract_generic_inner(
                self._normalize_cs_type(collection_base),
                self.KEYED_COLLECTION_GENERIC_NAMES,
            )
            if not collection_inner:
                continue
            collection_args = split_generic_arguments(collection_inner)
            if len(collection_args) != 2:
                continue

            type_name = self._strip_generic_arity(
                block.header_match.group("name"),
            )
            target_type = (
                f"{block.namespace}.{type_name}" if block.namespace else type_name
            )
            descriptors.append(
                MemoryPackCollectionFormatterDescriptor(
                    target_type=target_type,
                    element_type=self._normalize_cs_type(collection_args[1]),
                )
            )
        return descriptors

    def parse_formatter_layout_types(self) -> list[MemoryPackTypeDescriptor]:
        descriptors: list[MemoryPackTypeDescriptor] = []
        for block in iter_dump_blocks(
            self.data,
            namespace_pattern=self.NAMESPACE_PATTERN,
            header_pattern=self.TYPE_PATTERN,
            include_header=lambda _match, line: (
                "MemoryPack.IMemoryPackFormatterRegister" in line
                and "MemoryPack.IMemoryPackable" not in line
                and "KeyedCollection" not in line
            ),
        ):
            descriptors.append(
                self._build_descriptor(
                    block.namespace,
                    block.header_match,
                    block.body_lines,
                    include_properties=False,
                )
            )
        return descriptors

    def _build_descriptor(
        self,
        namespace: str,
        type_match: re.Match[str],
        body_lines: list[str],
        *,
        include_properties: bool = True,
    ) -> MemoryPackTypeDescriptor:
        bases = self._split_interfaces(type_match.group("bases") or "")
        base_type = (
            self._resolve_memorypack_base_type(bases)
            if include_properties
            else self._resolve_declared_base_type(namespace, bases)
        )
        members = (
            self._parse_members(body_lines)
            if include_properties
            else self._parse_field_members(body_lines)
        )
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

    @staticmethod
    def _resolve_memorypack_base_type(bases: list[str]) -> str | None:
        imemorypack_index = next(
            (
                index
                for index, item in enumerate(bases)
                if item.startswith("MemoryPack.IMemoryPackable")
            ),
            len(bases),
        )
        return bases[0] if imemorypack_index > 0 and bases else None

    def _resolve_declared_base_type(
        self,
        namespace: str,
        bases: list[str],
    ) -> str | None:
        declared_type_names = self._get_declared_type_names()
        for base in bases:
            normalized = self._normalize_cs_type(base)
            base_name = normalized.split("<", maxsplit=1)[0]
            qualified_name = (
                base_name
                if "." in base_name or not namespace
                else f"{namespace}.{base_name}"
            )
            if qualified_name in declared_type_names:
                return normalized
        return None

    def _get_declared_type_names(self) -> set[str]:
        if self._declared_type_names is not None:
            return self._declared_type_names

        declared_type_names: set[str] = set()
        for block in iter_dump_blocks(
            self.data,
            namespace_pattern=self.NAMESPACE_PATTERN,
            header_pattern=self.TYPE_PATTERN,
        ):
            type_name = self._strip_generic_arity(
                block.header_match.group("name"),
            )
            declared_type_names.add(
                f"{block.namespace}.{type_name}" if block.namespace else type_name
            )
        self._declared_type_names = declared_type_names
        return declared_type_names

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

        property_members: list[MemoryPackMemberDescriptor] = []
        for line in body_lines:
            property_match = cls.PROPERTY_PATTERN.match(line)
            if property_match is None:
                continue
            member_name = property_match.group("name")
            if member_name == "IsValid" and member_name not in backing_field_tokens:
                continue
            cs_type = cls._strip_member_type_modifiers(property_match.group("type"))
            property_members.append(
                MemoryPackMemberDescriptor(
                    index=0,
                    name=member_name,
                    cs_type=cs_type,
                    python_type=cls.to_python_type(cs_type),
                    member_token=property_match.group("token"),
                    backing_field_token=backing_field_tokens.get(member_name, ""),
                )
            )

        field_members = cls._parse_field_members(
            body_lines,
            public_only=bool(property_members),
        )
        members = property_members + field_members
        return [
            MemoryPackMemberDescriptor(
                index=index,
                name=member.name,
                cs_type=member.cs_type,
                python_type=member.python_type,
                member_token=member.member_token,
                backing_field_token=member.backing_field_token,
            )
            for index, member in enumerate(members)
        ]

    @classmethod
    def _parse_field_members(
        cls,
        body_lines: list[str],
        *,
        public_only: bool = False,
    ) -> list[MemoryPackMemberDescriptor]:
        members: list[MemoryPackMemberDescriptor] = []
        for line in body_lines:
            field_match = cls.FIELD_PATTERN.match(line)
            if field_match is None:
                continue

            modifiers = set(field_match.group("modifiers").split())
            if modifiers.intersection({"const", "static"}):
                continue
            if public_only and "public" not in modifiers:
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
