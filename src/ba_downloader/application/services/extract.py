from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import (
    AssetExtractionPort,
    FlatbufferWorkflowPort,
)
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort


class ExtractService:
    def __init__(
        self,
        extraction_workflow: AssetExtractionPort,
        flatbuffer_workflow: FlatbufferWorkflowPort | None = None,
        runtime_asset_preparer: RuntimeAssetPreparerPort | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        self.extraction_workflow = extraction_workflow
        self.flatbuffer_workflow = flatbuffer_workflow
        self.runtime_asset_preparer = runtime_asset_preparer
        self.logger = logger

    @staticmethod
    def _is_flat_data_ready(context: RuntimeContext) -> bool:
        flat_data_dir = Path(context.extract_dir) / "FlatData"
        return (
            flat_data_dir.is_dir()
            and (flat_data_dir / "__init__.py").is_file()
            and (flat_data_dir / "dump_wrapper.py").is_file()
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
            "JP table extract prerequisites were missing and recompiling FlatData from the existing "
            f"dump.cs failed under '{context.extract_dir}'. If dump.cs must be regenerated, JP runtime "
            f"files are required under '{context.temp_dir}', including 'global-metadata.dat' and either "
            f"'GameAssembly.dll' or 'libil2cpp.so'. Details: {details}"
        )

    def _ensure_jp_table_prerequisites(self, context: RuntimeContext) -> None:
        if context.region != "jp" or "table" not in context.resource_type:
            return
        if not (Path(context.raw_dir) / "Table").exists():
            return
        if self._is_flat_data_ready(context):
            return
        if self.flatbuffer_workflow is None or self.runtime_asset_preparer is None:
            raise LookupError(
                "JP table extract prerequisites are unavailable because FlatData bootstrap services are not configured."
            )

        attempted_dump = not self._is_dump_cs_ready(context)
        try:
            if not attempted_dump:
                if self.logger is not None:
                    self.logger.info(
                        "FlatData is missing. Recompiling JP FlatData from existing dump.cs..."
                    )
                self.flatbuffer_workflow.compile(context)
                return

            if self.logger is not None:
                self.logger.info(
                    "FlatData and dump.cs are missing. Generating JP table extract prerequisites..."
                )
            self.runtime_asset_preparer.prepare(context)
            self.flatbuffer_workflow.dump(context)
            self.flatbuffer_workflow.compile(context)
        except (FileNotFoundError, LookupError, RuntimeError) as exc:
            raise LookupError(
                self._format_jp_table_bootstrap_error(
                    context,
                    exc,
                    attempted_dump=attempted_dump,
                )
            ) from exc

    def run(self, context: RuntimeContext) -> None:
        if "table" in context.resource_type:
            self._ensure_jp_table_prerequisites(context)
            self.extraction_workflow.extract_tables(context)
        if "bundle" in context.resource_type:
            self.extraction_workflow.extract_bundles(context)
        if "media" in context.resource_type:
            self.extraction_workflow.extract_media(context)

    def run_post_download(self, context: RuntimeContext) -> None:
        if context.extract_while_download:
            return
        self.run(context)
