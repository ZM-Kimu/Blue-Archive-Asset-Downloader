from __future__ import annotations

import re
from pathlib import Path

from ba_downloader.infrastructure.schema.common.csharp import (
    extract_generic_inner,
    normalize_cs_type,
    primitive_python_type,
    strip_generic_arity,
    strip_member_type_modifiers,
)
from ba_downloader.infrastructure.schema.flatbuffer.descriptors import (
    FlatBufferEnumDescriptor,
    FlatBufferEnumMemberDescriptor,
    FlatBufferFieldDescriptor,
    FlatBufferTypeDescriptor,
)

NULL_TOKEN = ""


class FlatBufferCSParser:
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
        r"^\s*(?P<prefix>(?:public|private|internal|protected)\s+"
        r"(?:(?:sealed|abstract|partial|readonly|static)\s+)*)"
        r"(?P<kind>struct)\s+"
        r"(?P<name>[A-Za-z_][\w`.]*)\s*:\s*(?P<bases>.*?)\s*//\s*"
        r"TypeDefIndex:\s*(?P<type_def_index>\d+)"
        r"(?:,?\s+Token:\s*(?P<token>0x[0-9A-Fa-f]+))?",
    )
    ENUM_PATTERN = re.compile(
        r"^\s*(?P<prefix>(?:public|private|internal|protected)\s+"
        r"(?:(?:sealed|abstract|partial|readonly|static)\s+)*)"
        r"enum\s+"
        r"(?P<name>[A-Za-z_][\w`.]*)\s*//\s*"
        r"TypeDefIndex:\s*(?P<type_def_index>\d+)"
        r"(?:,?\s+Token:\s*(?P<token>0x[0-9A-Fa-f]+))?",
    )
    NAMESPACE_PATTERN = re.compile(r"^\s*//\s*Namespace:\s*(?P<namespace>.*)$")
    PROPERTY_PATTERN = re.compile(
        r"^\s*public\s+(?P<type>.+?)\s+"
        r"(?P<name>[A-Za-z_][\w]*)\s+"
        r"\{\s*get;\s*(?:set;\s*)?\}\s*"
        r"//.*?Token:\s*(?P<token>0x[0-9A-Fa-f]+)"
    )
    LIST_METHOD_PATTERN = re.compile(
        r"^\s*public\s+(?P<type>.+?)\s+"
        r"(?P<name>[A-Za-z_][\w]*)\((?:int|System\.Int32)\s+j\)\s*"
        r"\{\s*\}(?:\s*//.*?Token:\s*(?P<token>0x[0-9A-Fa-f]+))?"
    )
    ENUM_VALUE_PATTERN = re.compile(
        r"^\s*public\s+(?P<type>.+?)\s+value__;\s*//"
    )
    ENUM_MEMBER_PATTERN = re.compile(
        r"^\s*public\s+(?:static\s+)?const\s+"
        r"(?P<type>.+?)\s+"
        r"(?P<name>[A-Za-z_][\w]*)"
        r"(?:\s*=\s*(?P<value>-?\d+))?;\s*"
        r"(?:\/\/.*?Token:\s*(?P<token>0x[0-9A-Fa-f]+))?"
    )

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.data = Path(file_path).read_text(encoding="utf8")

    def parse_types(self) -> list[FlatBufferTypeDescriptor]:
        descriptors: list[FlatBufferTypeDescriptor] = []
        namespace = ""
        lines = self.data.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            if namespace_match := self.NAMESPACE_PATTERN.match(line):
                namespace = namespace_match.group("namespace").strip()
                if namespace == "-":
                    namespace = ""
                index += 1
                continue

            type_match = self.TYPE_PATTERN.match(line)
            if (
                type_match is None
                or "FlatBuffers.IFlatbufferObject" not in type_match.group("bases")
            ):
                index += 1
                continue

            body_lines, next_index = self._collect_type_body(lines, index)
            descriptors.append(
                self._build_type_descriptor(namespace, type_match, body_lines)
            )
            index = next_index

        return descriptors

    def parse_enums(self) -> list[FlatBufferEnumDescriptor]:
        descriptors: list[FlatBufferEnumDescriptor] = []
        namespace = ""
        lines = self.data.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            if namespace_match := self.NAMESPACE_PATTERN.match(line):
                namespace = namespace_match.group("namespace").strip()
                if namespace == "-":
                    namespace = ""
                index += 1
                continue

            enum_match = self.ENUM_PATTERN.match(line)
            if enum_match is None:
                index += 1
                continue

            body_lines, next_index = self._collect_type_body(lines, index)
            descriptors.append(
                self._build_enum_descriptor(namespace, enum_match, body_lines)
            )
            index = next_index

        return descriptors

    def parse_struct(self) -> list[FlatBufferTypeDescriptor]:
        return self.parse_types()

    def parse_enum(self) -> list[FlatBufferEnumDescriptor]:
        return self.parse_enums()

    @staticmethod
    def _collect_type_body(lines: list[str], start_index: int) -> tuple[list[str], int]:
        body_lines: list[str] = []
        depth = 0
        started = False
        index = start_index
        while index < len(lines):
            line = lines[index]
            body_lines.append(line)
            depth += line.count("{")
            if "{" in line:
                started = True
            depth -= line.count("}")
            index += 1
            if started and depth <= 0:
                break
        return body_lines, index

    def _build_type_descriptor(
        self,
        namespace: str,
        type_match: re.Match[str],
        body_lines: list[str],
    ) -> FlatBufferTypeDescriptor:
        original_name = type_match.group("name")
        return FlatBufferTypeDescriptor(
            name=self._strip_generic_arity(original_name),
            namespace=namespace,
            kind=type_match.group("kind"),
            original_name=original_name,
            type_def_index=int(type_match.group("type_def_index")),
            token=type_match.group("token") or NULL_TOKEN,
            fields=self._parse_fields(body_lines),
        )

    @classmethod
    def _build_enum_descriptor(
        cls,
        namespace: str,
        enum_match: re.Match[str],
        body_lines: list[str],
    ) -> FlatBufferEnumDescriptor:
        underlying_type = "System.Int32"
        members: list[FlatBufferEnumMemberDescriptor] = []
        next_value = 0
        for line in body_lines:
            if value_match := cls.ENUM_VALUE_PATTERN.match(line):
                underlying_type = cls._strip_member_type_modifiers(
                    value_match.group("type")
                )
                continue

            member_match = cls.ENUM_MEMBER_PATTERN.match(line)
            if member_match is None:
                continue

            value_text = member_match.group("value")
            value = int(value_text) if value_text is not None else next_value
            members.append(
                FlatBufferEnumMemberDescriptor(
                    name=member_match.group("name"),
                    value=value,
                    token=member_match.group("token") or NULL_TOKEN,
                )
            )
            next_value = value + 1

        original_name = enum_match.group("name")
        return FlatBufferEnumDescriptor(
            name=cls._strip_generic_arity(original_name),
            namespace=namespace,
            original_name=original_name,
            underlying_type=underlying_type,
            type_def_index=int(enum_match.group("type_def_index")),
            token=enum_match.group("token") or NULL_TOKEN,
            members=members,
        )

    @classmethod
    def _parse_fields(
        cls,
        body_lines: list[str],
    ) -> list[FlatBufferFieldDescriptor]:
        list_methods = {
            method_match.group("name"): (
                cls._normalize_cs_type(method_match.group("type")),
                method_match.group("token") or NULL_TOKEN,
            )
            for line in body_lines
            if (method_match := cls.LIST_METHOD_PATTERN.match(line))
        }
        fields_: list[FlatBufferFieldDescriptor] = []
        for line in body_lines:
            property_match = cls.PROPERTY_PATTERN.match(line)
            if property_match is None:
                continue

            member_name = property_match.group("name")
            if "ByteBuffer" in member_name:
                continue

            if member_name.endswith("Length"):
                list_name = member_name.removesuffix("Length")
                if list_name in list_methods:
                    cs_type, method_token = list_methods[list_name]
                    fields_.append(
                        FlatBufferFieldDescriptor(
                            index=len(fields_),
                            name=list_name,
                            cs_type=cs_type,
                            python_type=cls.to_python_type(cs_type, is_vector=True),
                            member_token=property_match.group("token")
                            or method_token,
                            is_vector=True,
                        )
                    )
                    continue

            cs_type = cls._normalize_cs_type(property_match.group("type"))
            fields_.append(
                FlatBufferFieldDescriptor(
                    index=len(fields_),
                    name=member_name,
                    cs_type=cs_type,
                    python_type=cls.to_python_type(cs_type),
                    member_token=property_match.group("token"),
                    is_vector=False,
                )
            )
        return fields_

    @classmethod
    def _strip_member_type_modifiers(cls, cs_type: str) -> str:
        return strip_member_type_modifiers(cs_type, cls.TYPE_MODIFIERS)

    @staticmethod
    def _strip_generic_arity(type_name: str) -> str:
        return strip_generic_arity(type_name)

    @classmethod
    def _normalize_cs_type(cls, cs_type: str) -> str:
        return normalize_cs_type(
            cs_type,
            modifiers=cls.TYPE_MODIFIERS,
            unwrap_generic_names=(
                "System.Nullable",
                "Nullable",
                "FlatBuffers.Offset",
            ),
        )

    @classmethod
    def to_python_type(cls, cs_type: str, *, is_vector: bool = False) -> str:
        normalized = cls._normalize_cs_type(cs_type)
        primitive = cls.primitive_python_type(normalized)
        if primitive:
            python_type = primitive
        elif normalized in {"string", "System.String"}:
            python_type = "str | None"
        else:
            python_type = "Any"
        if is_vector:
            return f"list[{python_type.removesuffix(' | None')}]"
        return python_type

    @staticmethod
    def primitive_python_type(cs_type: str) -> str:
        return primitive_python_type(cs_type, extra={"FlatBuffers.VectorOffset": "int"})

    @staticmethod
    def _extract_generic_inner(value: str, names: tuple[str, ...]) -> str:
        return extract_generic_inner(value, names)
