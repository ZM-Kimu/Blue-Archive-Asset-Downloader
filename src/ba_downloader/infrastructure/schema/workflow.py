from __future__ import annotations

import py_compile
from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import SchemaWorkflowPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.schema.flatbuffer.generator import (
    CompileFlatBufferToPython,
)
from ba_downloader.infrastructure.schema.flatbuffer.parser import FlatBufferCSParser
from ba_downloader.infrastructure.schema.memorypack.generator import (
    CompileMemoryPackToPython,
)
from ba_downloader.infrastructure.schema.memorypack.parser import MemoryPackCSParser
from ba_downloader.infrastructure.schema.memorypack.supplemental import (
    SupplementalMemoryPackFormatterBuilder,
)
from ba_downloader.infrastructure.tools.dump_backend import (
    BackendFactory,
)


class SchemaWorkflow(SchemaWorkflowPort):
    DUMP_PATH = "Dumps"

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        dumper_backend_factory: BackendFactory | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.dumper_backend_factory = dumper_backend_factory

    def dump(self, context: RuntimeContext) -> None:
        if self.dumper_backend_factory is None:
            raise ValueError(
                "SchemaWorkflow.dump requires a configured dumper backend factory."
            )
        extract_path = Path(context.extract_dir) / self.DUMP_PATH
        backend = self.dumper_backend_factory(self.http_client, self.logger)
        backend.dump(
            context,
            str(extract_path.resolve()),
        )

    def _validate_generated_python(self, output_dir: Path, label: str) -> None:
        for python_file in sorted(output_dir.rglob("*.py")):
            try:
                py_compile.compile(str(python_file), doraise=True)
            except py_compile.PyCompileError as exc:
                raise SyntaxError(
                    f"Generated {label} module is invalid: {python_file}. "
                    f"Compiler details: {exc.msg.strip()}"
                ) from exc

    def _generate_memorypack_data(
        self, dump_cs_file_path: str, context: RuntimeContext
    ) -> None:
        memorypack_data_dir = Path(context.extract_dir) / "MemoryPackData"
        try:
            self.logger.info("Generating MemoryPackData schema files...")
            memorypack_parser = MemoryPackCSParser(dump_cs_file_path)
            descriptors = memorypack_parser.parse_types()
            enums = memorypack_parser.parse_enums()
            memorypack_compiler = CompileMemoryPackToPython(
                descriptors,
                str(memorypack_data_dir),
                enums,
            )
            memorypack_compiler.create_schema_files()
            self._validate_generated_python(memorypack_data_dir, "MemoryPackData")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.warn(f"MemoryPackData generation failed: {exc}")

    def _generate_supplemental_memorypack_formatters(
        self,
        dump_cs_file_path: str,
        context: RuntimeContext,
    ) -> None:
        dumps_dir = Path(context.extract_dir) / self.DUMP_PATH
        memorypack_data_dir = Path(context.extract_dir) / "MemoryPackData"
        sidecar_path = dumps_dir / "memorypack_formatters.json"
        try:
            self.logger.info("Building MemoryPack semantic formatter sidecar...")
            updated = SupplementalMemoryPackFormatterBuilder(
                dump_cs_path=dump_cs_file_path,
                memorypack_data_dir=memorypack_data_dir,
                sidecar_path=sidecar_path,
            ).build()
            if not updated:
                self.logger.warn(
                    "MemoryPack semantic formatter sidecar was not updated; "
                    "advanced JP table semantics may fall back to raw payloads."
                )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.warn(
                f"MemoryPack semantic formatter sidecar generation failed: {exc}"
            )

    def compile(self, context: RuntimeContext) -> None:
        dump_cs_file_path = str(Path(context.extract_dir) / self.DUMP_PATH / "dump.cs")
        flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"

        self.logger.info("Parsing dump.cs...")
        parser = FlatBufferCSParser(dump_cs_file_path)
        enums = parser.parse_enums()
        descriptors = parser.parse_types()

        self.logger.info("Generating FlatBufferData schema files...")
        compiler = CompileFlatBufferToPython(
            descriptors,
            str(flatbuffer_data_dir),
            enums,
        )
        compiler.create_schema_files()
        self._validate_generated_python(flatbuffer_data_dir, "FlatBufferData")
        self._generate_memorypack_data(dump_cs_file_path, context)
        self._generate_supplemental_memorypack_formatters(dump_cs_file_path, context)
