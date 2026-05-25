from __future__ import annotations

import os
from typing import Any

from ba_downloader.infrastructure.schema.common.codegen import (
    build_cyclic_imports,
    build_python_name_maps,
    build_refs,
    build_simple_refs,
    escape_string,
    import_names,
    render_relative_imports,
    resolve_reference,
    string_or_none,
    tuple_literal,
    write_text_file,
)
from ba_downloader.infrastructure.schema.common.identifiers import make_valid_identifier
from ba_downloader.infrastructure.schema.memorypack.descriptors import (
    MemoryPackEnumDescriptor,
    MemoryPackTypeDescriptor,
    PythonTypeRender,
)
from ba_downloader.infrastructure.schema.memorypack.parser import MemoryPackCSParser


class CompileMemoryPackToPython:
    def __init__(
        self,
        descriptors: list[MemoryPackTypeDescriptor],
        extract_dir: str,
        enums: list[MemoryPackEnumDescriptor] | None = None,
    ) -> None:
        self.descriptors = descriptors
        self.enums = enums or []
        self.extract_dir = extract_dir
        self.type_python_names, self.enum_python_names = self._build_python_name_maps()
        self.type_refs = self._build_type_refs()
        self.enum_refs = self._build_enum_refs()
        self.simple_type_refs = self._build_simple_refs(self.type_refs)
        self.simple_enum_refs = self._build_simple_refs(self.enum_refs)
        self.cyclic_type_imports = self._build_cyclic_type_imports()

    def create_schema_files(self) -> None:
        os.makedirs(self.extract_dir, exist_ok=True)
        self._create_metadata_file()
        self._create_registry_file()
        self._create_module_file()
        for enum in self.enums:
            self._create_enum_file(enum, self.enum_python_names[self._enum_key(enum)])
        for descriptor in self.descriptors:
            python_name = self.type_python_names[self._descriptor_key(descriptor)]
            self._create_type_file(descriptor, python_name)

    def _build_python_name_maps(self) -> tuple[dict[str, str], dict[str, str]]:
        return build_python_name_maps(
            self.descriptors,
            self.enums,
            descriptor_key=self._descriptor_key,
            enum_key=self._enum_key,
        )

    def _build_type_refs(self) -> dict[str, tuple[str, MemoryPackTypeDescriptor]]:
        return build_refs(
            self.descriptors, self.type_python_names, self._descriptor_key
        )

    def _build_enum_refs(self) -> dict[str, tuple[str, MemoryPackEnumDescriptor]]:
        return build_refs(self.enums, self.enum_python_names, self._enum_key)

    @staticmethod
    def _build_simple_refs(
        refs: dict[str, tuple[str, Any]],
    ) -> dict[str, tuple[str, Any]]:
        return build_simple_refs(refs)

    def _build_cyclic_type_imports(self) -> set[tuple[str, str]]:
        def collect_imports(
            descriptor: MemoryPackTypeDescriptor,
            source_name: str,
        ) -> set[str]:
            imports: set[str] = set()
            for member in descriptor.members:
                render = self._render_python_type(
                    member.cs_type,
                    descriptor.namespace,
                    source_name,
                )
                imports.update(render.imports)
            return imports

        return build_cyclic_imports(
            self.descriptors,
            self.type_python_names,
            descriptor_key=self._descriptor_key,
            collect_imports=collect_imports,
        )

    @staticmethod
    def _descriptor_key(descriptor: MemoryPackTypeDescriptor) -> str:
        return f"{descriptor.full_name}:{descriptor.token}"

    @staticmethod
    def _enum_key(enum: MemoryPackEnumDescriptor) -> str:
        return f"{enum.full_name}:{enum.token}"

    def _create_metadata_file(self) -> None:
        self._write_file(
            "_metadata.py",
            (
                "from ba_downloader.infrastructure.schema.memorypack.descriptors import (\n"
                "    MemoryPackEnumMemberMetadata,\n"
                "    MemoryPackEnumMetadata,\n"
                "    MemoryPackMember,\n"
                "    MemoryPackTypeMetadata,\n"
                ")\n"
            ),
        )

    def _create_registry_file(self) -> None:
        lines = [
            "from __future__ import annotations",
            "",
            "MEMORYPACK_TYPES: dict[str, str] = {",
        ]
        for descriptor in self.descriptors:
            python_name = self.type_python_names[self._descriptor_key(descriptor)]
            lines.append(f'    "{descriptor.full_name}": "{python_name}",')
        lines.extend(["}", "", "MEMORYPACK_ENUMS: dict[str, str] = {"])
        for enum in self.enums:
            python_name = self.enum_python_names[self._enum_key(enum)]
            lines.append(f'    "{enum.full_name}": "{python_name}",')
        lines.extend(["}", ""])
        self._write_file("_registry.py", "\n".join(lines))

    def _create_module_file(self) -> None:
        lines = ["from ._registry import MEMORYPACK_ENUMS, MEMORYPACK_TYPES", ""]
        self._write_file("__init__.py", "\n".join(lines))

    def _create_enum_file(
        self,
        enum: MemoryPackEnumDescriptor,
        python_name: str,
    ) -> None:
        lines = [
            "from __future__ import annotations",
            "",
            "from enum import IntEnum",
            "",
            "from ba_downloader.infrastructure.schema.memorypack.descriptors import (",
            "    MemoryPackEnumMemberMetadata,",
            "    MemoryPackEnumMetadata,",
            ")",
            "",
            "__memorypack_enum__ = MemoryPackEnumMetadata(",
            f'    name="{self._escape(enum.name)}",',
            f'    namespace="{self._escape(enum.namespace)}",',
            f'    original_name="{self._escape(enum.original_name)}",',
            f'    underlying_type="{self._escape(enum.underlying_type)}",',
            f"    type_def_index={enum.type_def_index},",
            f'    token="{self._escape(enum.token)}",',
            "    members=(",
        ]
        for member in enum.members:
            member_python_name = make_valid_identifier(member.name)
            lines.append(
                "        MemoryPackEnumMemberMetadata("
                f'name="{self._escape(member.name)}", '
                f'python_name="{self._escape(member_python_name)}", '
                f"value={member.value}, "
                f'token="{self._escape(member.token)}"'
                "),"
            )
        lines.extend(
            [
                "    ),",
                ")",
                "",
                f"class {python_name}(IntEnum):",
            ]
        )
        if not enum.members:
            lines.append("    pass")
        for member in enum.members:
            lines.append(f"    {make_valid_identifier(member.name)} = {member.value}")
        lines.extend(
            ["", f"{python_name}.__memorypack_enum__ = __memorypack_enum__", ""]
        )
        self._write_file(f"{python_name}.py", "\n".join(lines))

    def _create_type_file(
        self,
        descriptor: MemoryPackTypeDescriptor,
        python_name: str,
    ) -> None:
        member_renders = [
            (
                member,
                self._render_python_type(
                    member.cs_type,
                    descriptor.namespace,
                    python_name,
                ),
            )
            for member in descriptor.members
        ]
        imports = sorted(
            {
                import_name
                for _, render in member_renders
                for import_name in render.imports
            }
        )
        runtime_imports, type_checking_imports, typing_import = render_relative_imports(
            imports,
            self.cyclic_type_imports,
            python_name,
        )
        lines = [
            "from __future__ import annotations",
            "",
            "from dataclasses import dataclass",
            typing_import,
            "",
            "from ba_downloader.infrastructure.schema.memorypack.descriptors import (",
            "    MemoryPackMember,",
            "    MemoryPackTypeMetadata,",
            ")",
        ]
        if runtime_imports:
            lines.append("")
            lines.extend(
                f"from .{import_name} import {import_name}"
                for import_name in runtime_imports
            )
        if type_checking_imports:
            lines.extend(["", "if TYPE_CHECKING:"])
            lines.extend(
                f"    from .{import_name} import {import_name}"
                for import_name in type_checking_imports
            )
            lines.append("else:")
            lines.extend(
                f"    {import_name} = Any" for import_name in type_checking_imports
            )
        lines.extend(
            [
                "",
                "__memorypack_type__ = MemoryPackTypeMetadata(",
                f'    name="{self._escape(descriptor.name)}",',
                f'    namespace="{self._escape(descriptor.namespace)}",',
                f'    kind="{self._escape(descriptor.kind)}",',
                f'    original_name="{self._escape(descriptor.original_name)}",',
                f"    base_type={self._string_or_none(descriptor.base_type)},",
                f"    interfaces={self._tuple_literal(descriptor.interfaces)},",
                f"    type_def_index={descriptor.type_def_index},",
                f'    token="{self._escape(descriptor.token)}",',
                ")",
                "",
                "@dataclass",
                f"class {python_name}:",
                "    __memorypack_type__ = __memorypack_type__",
            ]
        )
        if not descriptor.members:
            lines.append("    pass")
        for member, render in member_renders:
            lines.append(
                f"    {make_valid_identifier(member.name)}: "
                f"Annotated[{render.annotation}, "
                f"MemoryPackMember("
                f"index={member.index}, "
                f'cs_type="{self._escape(member.cs_type)}", '
                f'type_name="{self._escape(descriptor.name)}", '
                f'namespace="{self._escape(descriptor.namespace)}", '
                f'member_token="{self._escape(member.member_token)}", '
                f'backing_field_token="{self._escape(member.backing_field_token)}", '
                f'original_name="{self._escape(member.name)}"'
                ")]"
            )
        lines.append("")
        self._write_file(f"{python_name}.py", "\n".join(lines))

    def _render_python_type(
        self,
        cs_type: str,
        current_namespace: str,
        current_python_name: str,
    ) -> PythonTypeRender:
        normalized = MemoryPackCSParser._normalize_cs_type(cs_type)
        if nullable_inner := MemoryPackCSParser._extract_generic_inner(
            normalized,
            ("System.Nullable", "Nullable"),
        ):
            render = self._render_python_type(
                nullable_inner,
                current_namespace,
                current_python_name,
            )
            return PythonTypeRender(
                self._ensure_optional(render.annotation),
                render.imports,
            )

        if list_inner := MemoryPackCSParser._extract_generic_inner(
            normalized,
            (
                "System.Collections.Generic.List",
                "System.Collections.Generic.IReadOnlyList",
                "System.Collections.Generic.IList",
                "List",
            ),
        ):
            inner = self._render_container_inner(
                list_inner,
                current_namespace,
                current_python_name,
            )
            return PythonTypeRender(
                f"list[{inner.annotation}] | None",
                inner.imports,
            )

        if dictionary_inner := MemoryPackCSParser._extract_generic_inner(
            normalized,
            (
                "System.Collections.Generic.Dictionary",
                "System.Collections.Generic.IReadOnlyDictionary",
                "Dictionary",
            ),
        ):
            key_type, value_type = MemoryPackCSParser._split_generic_arguments(
                dictionary_inner
            )
            key_render = self._render_container_inner(
                key_type,
                current_namespace,
                current_python_name,
            )
            value_render = self._render_container_inner(
                value_type,
                current_namespace,
                current_python_name,
            )
            return PythonTypeRender(
                f"dict[{key_render.annotation}, {value_render.annotation}] | None",
                key_render.imports | value_render.imports,
            )

        if normalized.endswith("[]"):
            inner = self._render_container_inner(
                normalized.removesuffix("[]"),
                current_namespace,
                current_python_name,
            )
            return PythonTypeRender(f"list[{inner.annotation}] | None", inner.imports)

        primitive = MemoryPackCSParser.to_python_type(normalized)
        if primitive != "Any":
            return PythonTypeRender(primitive, frozenset())

        if enum_ref := self._resolve_enum_reference(normalized, current_namespace):
            enum_python_name, _ = enum_ref
            return PythonTypeRender(
                enum_python_name,
                self._import_names(enum_python_name, current_python_name),
            )

        if type_ref := self._resolve_type_reference(normalized, current_namespace):
            type_python_name, descriptor = type_ref
            annotation = type_python_name
            if descriptor.kind == "class":
                annotation = self._ensure_optional(annotation)
            return PythonTypeRender(
                annotation,
                self._import_names(type_python_name, current_python_name),
            )

        return PythonTypeRender("Any", frozenset())

    def _render_container_inner(
        self,
        cs_type: str,
        current_namespace: str,
        current_python_name: str,
    ) -> PythonTypeRender:
        render = self._render_python_type(
            cs_type,
            current_namespace,
            current_python_name,
        )
        return PythonTypeRender(
            render.annotation.removesuffix(" | None"),
            render.imports,
        )

    def _resolve_enum_reference(
        self,
        cs_type: str,
        current_namespace: str,
    ) -> tuple[str, MemoryPackEnumDescriptor] | None:
        return resolve_reference(
            cs_type,
            current_namespace,
            self.enum_refs,
            self.simple_enum_refs,
        )

    def _resolve_type_reference(
        self,
        cs_type: str,
        current_namespace: str,
    ) -> tuple[str, MemoryPackTypeDescriptor] | None:
        return resolve_reference(
            cs_type,
            current_namespace,
            self.type_refs,
            self.simple_type_refs,
        )

    @staticmethod
    def _ensure_optional(annotation: str) -> str:
        if annotation.endswith(" | None"):
            return annotation
        return f"{annotation} | None"

    @staticmethod
    def _import_names(python_name: str, current_python_name: str) -> frozenset[str]:
        return import_names(python_name, current_python_name)

    def _write_file(self, file_name: str, content: str) -> None:
        write_text_file(self.extract_dir, file_name, content)

    @staticmethod
    def _escape(value: str) -> str:
        return escape_string(value)

    @staticmethod
    def _string_or_none(value: str | None) -> str:
        return string_or_none(value)

    @staticmethod
    def _tuple_literal(values: tuple[str, ...]) -> str:
        return tuple_literal(values)
