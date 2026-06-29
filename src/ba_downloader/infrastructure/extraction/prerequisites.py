from __future__ import annotations

from pathlib import Path

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import (
    ExtractionPrerequisitePort,
    SchemaPreparationPort,
)
from ba_downloader.domain.ports.logging import LoggerPort


class JpTableExtractionPrerequisite(ExtractionPrerequisitePort):
    def __init__(
        self,
        schema_preparation: SchemaPreparationPort,
        logger: LoggerPort | None = None,
    ) -> None:
        self.schema_preparation = schema_preparation
        self.logger = logger

    def ensure(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        if context.region != "jp" or "table" not in context.resource_type:
            return
        if not self._has_table_input(context, resources):
            return
        if self._is_flat_buffer_data_ready(context):
            return

        attempted_dump = not self._is_dump_cs_ready(context)
        try:
            if not attempted_dump:
                if self.logger is not None:
                    self.logger.info(
                        "FlatBufferData is missing. Recompiling JP FlatBufferData from existing dump.cs..."
                    )
                self.schema_preparation.compile(context)
                return

            if self.logger is not None:
                self.logger.info(
                    "FlatBufferData and dump.cs are missing. Generating JP table extract prerequisites..."
                )
            self.schema_preparation.prepare(context)
        except (FileNotFoundError, LookupError, RuntimeError) as exc:
            raise LookupError(
                self._format_jp_table_bootstrap_error(
                    context,
                    exc,
                    attempted_dump=attempted_dump,
                )
            ) from exc

    @staticmethod
    def _has_table_input(
        context: RuntimeContext,
        resources: AssetCollection | None,
    ) -> bool:
        if resources is not None:
            return bool(resources)
        return (Path(context.raw_dir) / "Table").exists()

    @staticmethod
    def _is_flat_buffer_data_ready(context: RuntimeContext) -> bool:
        flatbuffer_data_dir = Path(context.extract_dir) / "FlatBufferData"
        return (
            flatbuffer_data_dir.is_dir()
            and (flatbuffer_data_dir / "__init__.py").is_file()
            and (flatbuffer_data_dir / "_registry.py").is_file()
        )

    @staticmethod
    def _is_dump_cs_ready(context: RuntimeContext) -> bool:
        return (Path(context.extract_dir) / "Dumps" / "dump.cs").is_file()

    @staticmethod
    def _format_jp_table_bootstrap_error(
        context: RuntimeContext,
        error: Exception,
        *,
        attempted_dump: bool,
    ) -> str:
        details = str(error).strip() or error.__class__.__name__
        if attempted_dump:
            return (
                "JP table extract prerequisites were missing and auto-generation was attempted. "
                f"This requires JP runtime files under '{context.temp_dir}', including "
                "'global-metadata.dat' and either 'GameAssembly.dll' or 'libil2cpp.so'. "
                f"Retry after preparing the JP temp files or running a JP sync/download flow. Details: {details}"
            )
        return (
            "JP table extract prerequisites were missing and recompiling FlatBufferData from the existing "
            f"dump.cs failed under '{context.extract_dir}'. If dump.cs must be regenerated, JP runtime "
            f"files are required under '{context.temp_dir}', including 'global-metadata.dat' and either "
            f"'GameAssembly.dll' or 'libil2cpp.so'. Details: {details}"
        )
