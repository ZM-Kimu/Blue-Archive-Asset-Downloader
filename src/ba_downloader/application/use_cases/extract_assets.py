from pathlib import Path

from ba_downloader.application.use_cases.asset_selection import (
    AssetSelectionService,
    RelationBuilderFactory,
)
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import (
    AssetExtractionPort,
    SchemaWorkflowPort,
)
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort
from ba_downloader.domain.services.resource_query import ResourceQueryService


class ExtractAssetsUseCase:
    def __init__(
        self,
        extraction_workflow: AssetExtractionPort,
        schema_workflow: SchemaWorkflowPort | None = None,
        runtime_asset_preparer: RuntimeAssetPreparerPort | None = None,
        logger: LoggerPort | None = None,
        *,
        provider: RegionProvider | None = None,
        relation_builder_factory: RelationBuilderFactory | None = None,
    ) -> None:
        self.extraction_workflow = extraction_workflow
        self.schema_workflow = schema_workflow
        self.runtime_asset_preparer = runtime_asset_preparer
        self.logger = logger
        self.provider = provider
        self.asset_selector = (
            AssetSelectionService(relation_builder_factory, logger)
            if relation_builder_factory is not None and logger is not None
            else None
        )

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

    def _ensure_jp_table_prerequisites(self, context: RuntimeContext) -> None:
        if context.region != "jp" or "table" not in context.resource_type:
            return
        if not (Path(context.raw_dir) / "Table").exists():
            return
        if self._is_flat_buffer_data_ready(context):
            return
        if self.schema_workflow is None or self.runtime_asset_preparer is None:
            raise LookupError(
                "JP table extract prerequisites are unavailable because FlatBufferData bootstrap services are not configured."
            )

        attempted_dump = not self._is_dump_cs_ready(context)
        try:
            if not attempted_dump:
                if self.logger is not None:
                    self.logger.info(
                        "FlatBufferData is missing. Recompiling JP FlatBufferData from existing dump.cs..."
                    )
                self.schema_workflow.compile(context)
                return

            if self.logger is not None:
                self.logger.info(
                    "FlatBufferData and dump.cs are missing. Generating JP table extract prerequisites..."
                )
            self.runtime_asset_preparer.prepare(context)
            self.schema_workflow.dump(context)
            self.schema_workflow.compile(context)
        except (FileNotFoundError, LookupError, RuntimeError) as exc:
            raise LookupError(
                self._format_jp_table_bootstrap_error(
                    context,
                    exc,
                    attempted_dump=attempted_dump,
                )
            ) from exc

    def _resolve_search_resources(
        self,
        context: RuntimeContext,
    ) -> tuple[RuntimeContext, AssetCollection]:
        if self.provider is None:
            raise LookupError("Extract search requires a configured region provider.")

        capabilities = self.provider.get_capabilities()
        if context.advanced_search and not capabilities.supports_advanced_search:
            raise LookupError(
                f"Advanced search is not supported for region '{context.region}'."
            )

        catalog = self.provider.load_catalog(context)
        active_context = catalog.context
        resources = self._filter_search_resources(catalog.resources, active_context)
        resources = ResourceQueryService.filter_type(
            resources,
            active_context.resource_type,
        )
        return active_context, AssetSelectionService.filter_existing_resources(
            resources,
            active_context,
        )

    def _filter_search_resources(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> AssetCollection:
        if self.asset_selector is not None:
            return self.asset_selector.filter_search_resources(
                resources,
                context,
                require_current_relation=bool(context.advanced_search),
            )

        if context.advanced_search:
            raise LookupError(
                "Extract advanced search requires a configured relation builder."
            )
        if context.search:
            return ResourceQueryService.search_name(resources, context.search)
        return resources

    @staticmethod
    def _filter_resources_for_type(
        resources: AssetCollection | None,
        resource_type: str,
    ) -> AssetCollection | None:
        if resources is None:
            return None
        return ResourceQueryService.filter_type(resources, (resource_type,))

    @staticmethod
    def _should_extract_type(resources: AssetCollection | None) -> bool:
        return resources is None or bool(resources)

    def run(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        active_context = context
        active_resources = resources
        if active_resources is None and (
            active_context.search or active_context.advanced_search
        ):
            active_context, active_resources = self._resolve_search_resources(
                active_context
            )

        if active_resources is not None and not active_resources:
            return

        if "table" in active_context.resource_type:
            table_resources = self._filter_resources_for_type(
                active_resources,
                "table",
            )
            if self._should_extract_type(table_resources):
                self._ensure_jp_table_prerequisites(active_context)
                self.extraction_workflow.extract_tables(
                    active_context,
                    table_resources,
                )
        if "bundle" in active_context.resource_type:
            bundle_resources = self._filter_resources_for_type(
                active_resources,
                "bundle",
            )
            if self._should_extract_type(bundle_resources):
                self.extraction_workflow.extract_bundles(
                    active_context,
                    bundle_resources,
                )
        if "media" in active_context.resource_type:
            media_resources = self._filter_resources_for_type(
                active_resources,
                "media",
            )
            if self._should_extract_type(media_resources):
                self.extraction_workflow.extract_media(active_context, media_resources)

    def run_post_download(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None:
        if context.extract_while_download:
            return
        self.run(context, resources)
