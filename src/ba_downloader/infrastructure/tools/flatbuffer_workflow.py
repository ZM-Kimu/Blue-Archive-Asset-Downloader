from __future__ import annotations

from pathlib import Path
import py_compile

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import FlatbufferWorkflowPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.tools import (
    DEFAULT_DUMPER_BACKEND_REGISTRY,
    CompileToPython,
    CSParser,
    DumperBackendRegistry,
)


class FlatbufferWorkflow(FlatbufferWorkflowPort):
    DUMP_PATH = "Dumps"

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        dumper_backend_registry: DumperBackendRegistry = DEFAULT_DUMPER_BACKEND_REGISTRY,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.dumper_backend_registry = dumper_backend_registry

    def dump(self, context: RuntimeContext) -> None:
        extract_path = Path(context.extract_dir) / self.DUMP_PATH
        backend_factory = self.dumper_backend_registry.resolve(context.region)
        backend = backend_factory(self.http_client, self.logger)
        backend.dump(
            context,
            str(extract_path.resolve()),
        )

    def _validate_generated_flat_data(self, flat_data_dir: Path) -> None:
        for python_file in sorted(flat_data_dir.rglob("*.py")):
            try:
                py_compile.compile(str(python_file), doraise=True)
            except py_compile.PyCompileError as exc:
                raise SyntaxError(
                    f"Generated FlatData module is invalid: {python_file}."
                ) from exc

    def compile(self, context: RuntimeContext) -> None:
        dump_cs_file_path = str(Path(context.extract_dir) / self.DUMP_PATH / "dump.cs")
        flat_data_dir = Path(context.extract_dir) / "FlatData"

        self.logger.info("Parsing dump.cs...")
        parser = CSParser(dump_cs_file_path)
        enums = parser.parse_enum()
        structs = parser.parse_struct()

        self.logger.info("Generating flatbuffer python dump files...")
        compiler = CompileToPython(enums, structs, str(flat_data_dir))
        compiler.create_enum_files()
        compiler.create_struct_files()
        compiler.create_module_file()
        compiler.create_dump_dict_file()
        self._validate_generated_flat_data(flat_data_dir)
