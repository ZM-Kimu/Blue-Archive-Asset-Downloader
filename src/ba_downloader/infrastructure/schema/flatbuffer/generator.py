from __future__ import annotations

import os
from typing import Any

from ba_downloader.infrastructure.schema.common.codegen import (
    build_simple_refs,
    escape_string,
    graph_has_path,
    import_names,
    resolve_unique_python_name,
    write_text_file,
)
from ba_downloader.infrastructure.schema.common.identifiers import make_valid_identifier
from ba_downloader.infrastructure.schema.flatbuffer.descriptors import (
    FlatBufferEnumDescriptor,
    FlatBufferTypeDescriptor,
    PythonTypeRender,
    make_enum_member_identifier,
)
from ba_downloader.infrastructure.schema.flatbuffer.parser import FlatBufferCSParser


class CompileFlatBufferToPython:
    def __init__(
        self,
        descriptors: list[FlatBufferTypeDescriptor],
        extract_dir: str,
        enums: list[FlatBufferEnumDescriptor] | None = None,
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
        for enum in self.enums:
            self._create_enum_file(enum, self.enum_python_names[self._enum_key(enum)])
        for descriptor in self.descriptors:
            python_name = self.type_python_names[self._descriptor_key(descriptor)]
            self._create_type_file(descriptor, python_name)
        self._create_registry_file()
        self._create_module_file()

    def _build_python_name_maps(self) -> tuple[dict[str, str], dict[str, str]]:
        used_names: dict[str, int] = {}
        type_names: dict[str, str] = {}
        enum_names: dict[str, str] = {}
        for enum in self.enums:
            enum_names[self._enum_key(enum)] = self._resolve_unique_python_name(
                enum.python_name,
                enum.type_def_index,
                used_names,
            )
        for descriptor in self.descriptors:
            type_names[self._descriptor_key(descriptor)] = (
                self._resolve_unique_python_name(
                    descriptor.python_name,
                    descriptor.type_def_index,
                    used_names,
                )
            )
        return type_names, enum_names

    @staticmethod
    def _resolve_unique_python_name(
        base_name: str,
        type_def_index: int,
        used_names: dict[str, int],
    ) -> str:
        return resolve_unique_python_name(base_name, type_def_index, used_names)

    def _build_type_refs(self) -> dict[str, tuple[str, FlatBufferTypeDescriptor]]:
        refs: dict[str, tuple[str, FlatBufferTypeDescriptor]] = {}
        for descriptor in self.descriptors:
            python_name = self.type_python_names[self._descriptor_key(descriptor)]
            refs[descriptor.full_name] = (python_name, descriptor)
        return refs

    def _build_enum_refs(self) -> dict[str, tuple[str, FlatBufferEnumDescriptor]]:
        refs: dict[str, tuple[str, FlatBufferEnumDescriptor]] = {}
        for enum in self.enums:
            python_name = self.enum_python_names[self._enum_key(enum)]
            refs[enum.full_name] = (python_name, enum)
        return refs

    @staticmethod
    def _build_simple_refs(
        refs: dict[str, tuple[str, Any]],
    ) -> dict[str, tuple[str, Any]]:
        return build_simple_refs(refs)

    def _build_cyclic_type_imports(self) -> set[tuple[str, str]]:
        graph: dict[str, set[str]] = {
            python_name: set() for python_name in self.type_python_names.values()
        }
        type_python_names = set(self.type_python_names.values())
        for descriptor in self.descriptors:
            source_name = self.type_python_names[self._descriptor_key(descriptor)]
            for field in descriptor.fields:
                render = self._render_python_type(
                    field.cs_type,
                    descriptor.namespace,
                    source_name,
                    is_vector=field.is_vector,
                )
                graph[source_name].update(render.imports & type_python_names)

        cyclic_imports: set[tuple[str, str]] = set()
        for source_name, targets in graph.items():
            for target_name in targets:
                if self._graph_has_path(graph, target_name, source_name):
                    cyclic_imports.add((source_name, target_name))
        return cyclic_imports

    @staticmethod
    def _graph_has_path(
        graph: dict[str, set[str]],
        start_name: str,
        target_name: str,
    ) -> bool:
        return graph_has_path(graph, start_name, target_name)

    @staticmethod
    def _descriptor_key(descriptor: FlatBufferTypeDescriptor) -> str:
        return f"{descriptor.full_name}:{descriptor.token}:{descriptor.type_def_index}"

    @staticmethod
    def _enum_key(enum: FlatBufferEnumDescriptor) -> str:
        return f"{enum.full_name}:{enum.token}:{enum.type_def_index}"

    def _create_metadata_file(self) -> None:
        self._write_file(
            "_metadata.py",
            (
                "from ba_downloader.infrastructure.schema.flatbuffer.descriptors import (\n"
                "    FlatBufferEnumMemberMetadata,\n"
                "    FlatBufferEnumMetadata,\n"
                "    FlatBufferField,\n"
                "    FlatBufferTypeMetadata,\n"
                ")\n"
            ),
        )

    def _create_registry_file(self) -> None:
        lines = ["from __future__ import annotations", ""]
        for enum in self.enums:
            python_name = self.enum_python_names[self._enum_key(enum)]
            lines.append(f"from .{python_name} import {python_name}")
        for descriptor in self.descriptors:
            python_name = self.type_python_names[self._descriptor_key(descriptor)]
            lines.append(f"from .{python_name} import {python_name}")
        lines.extend(["", "FLATBUFFER_TYPES: dict[str, type] = {"])
        for descriptor in self.descriptors:
            python_name = self.type_python_names[self._descriptor_key(descriptor)]
            keys = {descriptor.name, descriptor.original_name, descriptor.full_name}
            for key in sorted(keys):
                lines.append(f'    "{self._escape(key)}": {python_name},')
        lines.extend(["}", "", "FLATBUFFER_ENUMS: dict[str, type] = {"])
        for enum in self.enums:
            python_name = self.enum_python_names[self._enum_key(enum)]
            keys = {enum.name, enum.original_name, enum.full_name}
            for key in sorted(keys):
                lines.append(f'    "{self._escape(key)}": {python_name},')
        lines.extend(["}", ""])
        self._write_file("_registry.py", "\n".join(lines))

    def _create_module_file(self) -> None:
        lines = ["from ._registry import FLATBUFFER_ENUMS, FLATBUFFER_TYPES", ""]
        self._write_file("__init__.py", "\n".join(lines))

    def _create_enum_file(
        self,
        enum: FlatBufferEnumDescriptor,
        python_name: str,
    ) -> None:
        member_python_names = self._enum_member_python_names(enum)
        lines = [
            "from __future__ import annotations",
            "",
            "from enum import IntEnum",
            "",
            "from ba_downloader.infrastructure.schema.flatbuffer.descriptors import (",
            "    FlatBufferEnumMemberMetadata,",
            "    FlatBufferEnumMetadata,",
            ")",
            "",
            "__flatbuffer_enum__ = FlatBufferEnumMetadata(",
            f'    name="{self._escape(enum.name)}",',
            f'    namespace="{self._escape(enum.namespace)}",',
            f'    original_name="{self._escape(enum.original_name)}",',
            f'    underlying_type="{self._escape(enum.underlying_type)}",',
            f"    type_def_index={enum.type_def_index},",
            f'    token="{self._escape(enum.token)}",',
            "    members=(",
        ]
        for member in enum.members:
            member_python_name = member_python_names[member.name]
            lines.append(
                "        FlatBufferEnumMemberMetadata("
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
            lines.append(f"    {member_python_names[member.name]} = {member.value}")
        lines.extend(["", f"{python_name}.__flatbuffer_enum__ = __flatbuffer_enum__", ""])
        self._write_file(f"{python_name}.py", "\n".join(lines))

    @staticmethod
    def _enum_member_python_names(enum: FlatBufferEnumDescriptor) -> dict[str, str]:
        names: dict[str, str] = {}
        used_names: dict[str, int] = {}
        for member in enum.members:
            base_name = make_enum_member_identifier(member.name)
            used_names[base_name] = used_names.get(base_name, 0) + 1
            if used_names[base_name] == 1:
                names[member.name] = base_name
            else:
                names[member.name] = f"{base_name}_{used_names[base_name]}"
        return names

    def _create_type_file(
        self,
        descriptor: FlatBufferTypeDescriptor,
        python_name: str,
    ) -> None:
        field_renders = [
            (
                field,
                self._render_python_type(
                    field.cs_type,
                    descriptor.namespace,
                    python_name,
                    is_vector=field.is_vector,
                ),
            )
            for field in descriptor.fields
        ]
        imports = sorted(
            {
                import_name
                for _, render in field_renders
                for import_name in render.imports
            }
        )
        runtime_imports = [
            import_name
            for import_name in imports
            if (python_name, import_name) not in self.cyclic_type_imports
        ]
        type_checking_imports = [
            import_name
            for import_name in imports
            if (python_name, import_name) in self.cyclic_type_imports
        ]
        typing_import = "from typing import Annotated, Any"
        if type_checking_imports:
            typing_import = "from typing import Annotated, Any, TYPE_CHECKING"
        lines = [
            "from __future__ import annotations",
            "",
            "from dataclasses import dataclass",
            typing_import,
            "",
            "from ba_downloader.infrastructure.schema.flatbuffer.descriptors import (",
            "    FlatBufferField,",
            "    FlatBufferTypeMetadata,",
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
            lines.extend(f"    {import_name} = Any" for import_name in type_checking_imports)
        lines.extend(
            [
                "",
                "__flatbuffer_type__ = FlatBufferTypeMetadata(",
                f'    name="{self._escape(descriptor.name)}",',
                f'    namespace="{self._escape(descriptor.namespace)}",',
                f'    kind="{self._escape(descriptor.kind)}",',
                f'    original_name="{self._escape(descriptor.original_name)}",',
                f"    type_def_index={descriptor.type_def_index},",
                f'    token="{self._escape(descriptor.token)}",',
                ")",
                "",
                "@dataclass",
                f"class {python_name}:",
                "    __flatbuffer_type__ = __flatbuffer_type__",
            ]
        )
        if not descriptor.fields:
            lines.append("    pass")
        for field, render in field_renders:
            lines.append(
                f"    {make_valid_identifier(field.name)}: "
                f"Annotated[{render.annotation}, "
                f"FlatBufferField("
                f"index={field.index}, "
                f'cs_type="{self._escape(field.cs_type)}", '
                f'type_name="{self._escape(descriptor.name)}", '
                f'namespace="{self._escape(descriptor.namespace)}", '
                f'member_token="{self._escape(field.member_token)}", '
                f'original_name="{self._escape(field.name)}", '
                f"is_vector={field.is_vector}"
                ")]"
            )
        lines.append("")
        self._write_file(f"{python_name}.py", "\n".join(lines))

    def _render_python_type(
        self,
        cs_type: str,
        current_namespace: str,
        current_python_name: str,
        *,
        is_vector: bool = False,
    ) -> PythonTypeRender:
        render = self._render_single_python_type(
            cs_type,
            current_namespace,
            current_python_name,
        )
        if is_vector:
            return PythonTypeRender(
                f"list[{render.annotation.removesuffix(' | None')}]",
                render.imports,
            )
        return render

    def _render_single_python_type(
        self,
        cs_type: str,
        current_namespace: str,
        current_python_name: str,
    ) -> PythonTypeRender:
        normalized = FlatBufferCSParser._normalize_cs_type(cs_type)
        primitive = FlatBufferCSParser.to_python_type(normalized)
        if primitive != "Any":
            return PythonTypeRender(primitive, frozenset())

        if enum_ref := self._resolve_enum_reference(normalized, current_namespace):
            enum_python_name, _ = enum_ref
            return PythonTypeRender(
                enum_python_name,
                self._import_names(enum_python_name, current_python_name),
            )

        if type_ref := self._resolve_type_reference(normalized, current_namespace):
            type_python_name, _ = type_ref
            return PythonTypeRender(
                f"{type_python_name} | None",
                self._import_names(type_python_name, current_python_name),
            )

        return PythonTypeRender("Any", frozenset())

    def _resolve_enum_reference(
        self,
        cs_type: str,
        current_namespace: str,
    ) -> tuple[str, FlatBufferEnumDescriptor] | None:
        return self._resolve_reference(
            cs_type,
            current_namespace,
            self.enum_refs,
            self.simple_enum_refs,
        )

    def _resolve_type_reference(
        self,
        cs_type: str,
        current_namespace: str,
    ) -> tuple[str, FlatBufferTypeDescriptor] | None:
        return self._resolve_reference(
            cs_type,
            current_namespace,
            self.type_refs,
            self.simple_type_refs,
        )

    @staticmethod
    def _resolve_reference(
        cs_type: str,
        current_namespace: str,
        refs: dict[str, tuple[str, Any]],
        simple_refs: dict[str, tuple[str, Any]],
    ) -> tuple[str, Any] | None:
        candidates = [cs_type]
        if "." not in cs_type and current_namespace:
            candidates.insert(0, f"{current_namespace}.{cs_type}")
        for candidate in candidates:
            if candidate in refs:
                return refs[candidate]
        if "." not in cs_type:
            return simple_refs.get(cs_type)
        return None

    @staticmethod
    def _import_names(python_name: str, current_python_name: str) -> frozenset[str]:
        return import_names(python_name, current_python_name)

    def _write_file(self, file_name: str, content: str) -> None:
        write_text_file(self.extract_dir, file_name, content)

    @staticmethod
    def _escape(value: str) -> str:
        return escape_string(value)
