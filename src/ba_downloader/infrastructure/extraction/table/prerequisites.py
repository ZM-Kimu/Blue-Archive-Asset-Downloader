from __future__ import annotations

from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import (
    ExtractionPrerequisitePort,
    SchemaPreparationPort,
)
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.storage.workspace_paths import (
    extracted_dumps_root,
    extracted_schema_root,
    raw_type_root,
)


class TableExtractionPrerequisite(ExtractionPrerequisitePort):
    SCHEMA_DIRECTORIES = ("FlatBufferData", "MemoryPackData")

    def __init__(
        self,
        schema_preparation: SchemaPreparationPort,
        *,
        region: str,
        logger: LoggerPort | None = None,
    ) -> None:
        self.schema_preparation = schema_preparation
        self.region = region.upper()
        self.logger = logger

    def ensure(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        if "table" not in context.resource_type:
            return
        if not self._has_table_input(context, resources):
            return
        if self._are_schema_directories_ready(context):
            return

        attempted_dump = not self._is_dump_cs_ready(context)
        try:
            if not attempted_dump:
                if self.logger is not None:
                    self.logger.info(
                        f"Table schemas are missing. Recompiling {self.region} table "
                        "schemas from existing dump.cs..."
                    )
                self.schema_preparation.compile(context)
                return

            if self.logger is not None:
                self.logger.info(
                    f"Table schemas and dump.cs are missing. Generating {self.region} "
                    "table extraction prerequisites..."
                )
            self.schema_preparation.prepare(context)
        except (FileNotFoundError, LookupError, RuntimeError) as exc:
            raise LookupError(
                self._format_error(
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
        return raw_type_root(context, AssetType.table).exists()

    def _are_schema_directories_ready(self, context: RuntimeContext) -> bool:
        return all(
            (extracted_schema_root(context, schema) / "__init__.py").is_file()
            and (extracted_schema_root(context, schema) / "_registry.py").is_file()
            for schema in ("flatbuffer", "memorypack")
        )

    @staticmethod
    def _is_dump_cs_ready(context: RuntimeContext) -> bool:
        return (extracted_dumps_root(context) / "dump.cs").is_file()

    def _format_error(
        self,
        context: RuntimeContext,
        error: Exception,
        *,
        attempted_dump: bool,
    ) -> str:
        details = str(error).strip() or error.__class__.__name__
        if attempted_dump:
            return (
                f"{self.region} table extraction prerequisites were missing and "
                "auto-generation was attempted. Runtime files under "
                f"'{context.temp_dir}' must include 'global-metadata.dat', "
                "'globalgamemanagers', and either 'GameAssembly.dll' or "
                f"'libil2cpp.so'. Details: {details}"
            )
        return (
            f"{self.region} table extraction prerequisites were missing and "
            "recompiling schemas from the existing dump.cs failed under "
            f"'{context.extract_dir}'. Details: {details}"
        )
