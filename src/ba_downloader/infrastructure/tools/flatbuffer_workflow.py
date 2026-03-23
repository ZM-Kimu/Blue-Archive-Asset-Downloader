from __future__ import annotations

from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import FlatbufferWorkflowPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.tools import CompileToPython, CSParser, IL2CppDumper


class FlatbufferWorkflow(FlatbufferWorkflowPort):
    DUMP_PATH = "Dumps"
    IL2CPP_NAME = "libil2cpp.so"
    METADATA_NAME = "global-metadata.dat"

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def dump(self, context: RuntimeContext) -> None:
        save_path = context.temp_dir
        dumper = IL2CppDumper()
        self.logger.info("Downloading il2cpp-dumper...")
        dumper.get_il2cpp_dumper(self.http_client, save_path)

        il2cpp_matches = list(Path(context.temp_dir).rglob(self.IL2CPP_NAME))
        metadata_matches = list(Path(context.temp_dir).rglob(self.METADATA_NAME))
        if not (il2cpp_matches and metadata_matches):
            raise FileNotFoundError(
                "Cannot find il2cpp binary file or global-metadata file. Make sure they exist."
            )

        extract_path = Path(context.extract_dir) / self.DUMP_PATH
        self.logger.info("Trying to dump il2cpp...")
        dumper.dump_il2cpp(
            str(extract_path.resolve()),
            str(il2cpp_matches[0].resolve()),
            str(metadata_matches[0].resolve()),
            context.max_retries,
        )
        self.logger.warn("Dumped il2cpp binary file successfully.")

    def compile(self, context: RuntimeContext) -> None:
        dump_cs_file_path = str(Path(context.extract_dir) / self.DUMP_PATH / "dump.cs")
        flat_data_dir = str(Path(context.extract_dir) / "FlatData")

        self.logger.info("Parsing dump.cs...")
        parser = CSParser(dump_cs_file_path)
        enums = parser.parse_enum()
        structs = parser.parse_struct()

        self.logger.info("Generating flatbuffer python dump files...")
        compiler = CompileToPython(enums, structs, flat_data_dir)
        compiler.create_enum_files()
        compiler.create_struct_files()
        compiler.create_module_file()
        compiler.create_dump_dict_file()
