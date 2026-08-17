from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import cast

from ba_downloader.application.bus import CommandBus, MessageRegistration
from ba_downloader.application.middleware import CancellationMiddleware
from ba_downloader.application.operations import (
    ApplicationOperation,
    ApplicationOperationCommand,
    ApplicationOperationExecutor,
    ApplicationOperationHandlerResult,
)
from ba_downloader.application.profiles import RegionProfile
from ba_downloader.application.use_cases.build_character_index import (
    BuildCharacterIndexUseCase,
)
from ba_downloader.application.use_cases.cleanup_storage import CleanupStorageUseCase
from ba_downloader.application.use_cases.download_assets import DownloadAssetsUseCase
from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.application.use_cases.schema_preparation import (
    SchemaPreparationService,
)
from ba_downloader.application.use_cases.sync_assets import SyncAssetsUseCase
from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
    RegionGatewayDefinition,
    RegionGatewayRegistry,
    build_application_region_profile,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.workspace import WorkspaceLayout
from ba_downloader.domain.ports.catalog_metadata import TableMetadataManifestPort
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.execution import (
    ArtifactCollector,
    ArtifactSinkPort,
    CancellationPort,
    NeverCancelled,
)
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import ProgressReporterFactoryPort
from ba_downloader.domain.ports.region import RegionProvider

CharacterIndexBuilderFactory = Callable[[RuntimeContext], CharacterIndexBuilderPort]


class _OperationHandler:
    def __init__(self, scope: ExecutionScope) -> None:
        self._scope = scope

    def __call__(
        self,
        _context: ExecutionContext,
        command: ApplicationOperationCommand,
    ) -> ApplicationOperationHandlerResult:
        context = self._scope.context
        cancellation = self._scope.cancellation
        operation = command.operation

        if operation is ApplicationOperation.storage_cleanup:
            from ba_downloader.infrastructure.storage.cleanup import (
                BoundedStorageCleanup,
            )

            deleted = CleanupStorageUseCase(BoundedStorageCleanup(), cancellation).run(
                context, command.cleanup_targets
            )
            return ApplicationOperationHandlerResult(
                context,
                statistics=(("deleted", deleted),),
            )

        if operation is ApplicationOperation.sync:
            sync_result = SyncAssetsUseCase(
                self._scope.provider(),
                self._scope.downloader(),
                self._scope.extract_service(),
                self._scope.schema_preparation(),
                self._scope.character_index_builder_factory(),
                self._scope.logger,
                workflow_profile=self._scope.workflow_profile(),
                cancellation=cancellation,
            ).run(context)
            return ApplicationOperationHandlerResult(
                sync_result.context,
                warnings=sync_result.extraction.warnings,
            )

        if operation is ApplicationOperation.download:
            active_context = DownloadAssetsUseCase(
                self._scope.provider(),
                self._scope.downloader(),
                workflow_profile=self._scope.workflow_profile(),
                cancellation=cancellation,
                character_index_builder_factory=(
                    self._scope.character_index_builder_factory()
                ),
            ).run(context)
            return ApplicationOperationHandlerResult(active_context)

        if operation is ApplicationOperation.extract:
            extraction = self._scope.extract_service().run(context)
            return ApplicationOperationHandlerResult(
                context,
                warnings=extraction.warnings,
            )

        if operation is ApplicationOperation.character_index:
            active_context = BuildCharacterIndexUseCase(
                self._scope.provider(),
                self._scope.downloader(),
                self._scope.schema_preparation(),
                self._scope.character_index_builder_factory(),
                cancellation=cancellation,
                catalog_metadata=self._scope.workflow_profile().catalog_metadata,
            ).build(context)
            return ApplicationOperationHandlerResult(active_context)

        if operation is ApplicationOperation.catalog_refresh:
            catalog = self._scope.provider().load_catalog(context)
            self._scope.workflow_profile().catalog_metadata.on_catalog_loaded(
                catalog.context,
                catalog.resources,
            )
            return ApplicationOperationHandlerResult(
                catalog.context,
                catalog.resources,
            )

        raise LookupError(f"Unsupported operation '{operation.value}'.")


class ExecutionScope:
    def __init__(
        self,
        context: RuntimeContext,
        *,
        logger: LoggerPort | None = None,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
        gateway_registry: RegionGatewayRegistry = DEFAULT_REGION_GATEWAY_REGISTRY,
    ) -> None:
        self.context = context
        self._provided_logger = logger
        self._progress_factory = progress_factory
        self.cancellation = cancellation or NeverCancelled()
        self._gateway_registry = gateway_registry
        self._resources = ExitStack()
        self._entered = False
        self._executed = False
        self._logger: LoggerPort | None = None
        self._http_client: HttpClientPort | None = None
        self._definition: RegionGatewayDefinition | None = None
        self._provider: RegionProvider | None = None
        self._schema_preparation: SchemaPreparationPort | None = None
        self._workflow_profile: RegionProfile | None = None
        self._downloader: ResourceDownloaderPort | None = None
        self._extract_service: ExtractAssetsUseCase | None = None
        self._index_builder_factory: CharacterIndexBuilderFactory | None = None
        self._bus: CommandBus | None = None

    @property
    def logger(self) -> LoggerPort:
        self._require_active()
        if self._logger is None:
            from ba_downloader.infrastructure.logging.console_logger import (
                ConsoleLogger,
            )

            self._logger = self._provided_logger or ConsoleLogger()
        return self._logger

    def __enter__(self) -> ExecutionScope:
        if self._entered:
            raise RuntimeError("Execution scope is already active.")
        self._resources.__enter__()
        self._entered = True
        handler = _OperationHandler(self)
        self._bus = CommandBus(
            [MessageRegistration(ApplicationOperationCommand, handler)],
            middleware=[CancellationMiddleware(self.cancellation)],
        )
        return self

    def __exit__(self, *_: object) -> None:
        self._entered = False
        self._resources.close()

    def execute(
        self,
        command: ApplicationOperationCommand,
    ) -> ApplicationOperationHandlerResult:
        self._require_active()
        if self._executed:
            raise RuntimeError("Execution scope supports one operation only.")
        self._executed = True
        assert self._bus is not None
        result = self._bus.dispatch(self._bus_context(), command)
        return cast(ApplicationOperationHandlerResult, result)

    def definition(self) -> RegionGatewayDefinition:
        self._require_active()
        if self._definition is None:
            self._definition = self._gateway_registry.resolve(self.context.region)
        return self._definition

    def http_client(self) -> HttpClientPort:
        self._require_active()
        if self._http_client is None:
            from ba_downloader.infrastructure.http import ResilientHttpClient

            client = ResilientHttpClient(
                proxy_url=self.context.proxy_url or None,
                max_retries=self.context.max_retries,
                cancellation=self.cancellation,
            )
            self._resources.callback(client.close)
            self._http_client = client
        return self._http_client

    def provider(self) -> RegionProvider:
        if self._provider is None:
            self._provider = self.definition().catalog.provider(
                self.http_client(),
                self.logger,
                self._progress_factory,
                self.cancellation,
            )
        return self._provider

    def schema_preparation(self) -> SchemaPreparationPort:
        if self._schema_preparation is None:
            from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow

            definition = self.definition()
            workflow = SchemaWorkflow(
                self.http_client(),
                self.logger,
                dumper_backend_factory=definition.runtime.dump_backend,
                cancellation=self.cancellation,
            )
            preparer = definition.runtime.asset_preparer(
                self.http_client(),
                self.logger,
                self._progress_factory,
                self.cancellation,
            )
            self._schema_preparation = SchemaPreparationService(
                workflow,
                preparer,
                cancellation=self.cancellation,
            )
        return self._schema_preparation

    def workflow_profile(self) -> RegionProfile:
        if self._workflow_profile is None:
            self._workflow_profile = build_application_region_profile(
                self.definition(),
                logger=self.logger,
                table_metadata_store=self._table_metadata_store(),
                provider=self.provider(),
            )
        return self._workflow_profile

    def downloader(self) -> ResourceDownloaderPort:
        if self._downloader is not None:
            return self._downloader

        from ba_downloader.infrastructure.download import ResourceDownloader

        downloader = ResourceDownloader(
            self.http_client(),
            self.logger,
            progress_factory=self._progress_factory,
            cancellation=self.cancellation,
        )
        self._downloader = downloader
        return downloader

    def character_index_builder_factory(self) -> CharacterIndexBuilderFactory:
        if self._index_builder_factory is None:
            from ba_downloader.infrastructure.extraction.character import (
                CharacterIndexBuilder,
            )

            definition = self.definition()

            def build(active_context: RuntimeContext) -> CharacterIndexBuilderPort:
                return CharacterIndexBuilder(
                    active_context,
                    self.logger,
                    table_profile_factory=definition.tables.extraction_profile,
                    character_index_source_profile_factory=(
                        definition.character_index.source_profile
                    ),
                    character_index_composition_profile_factory=(
                        definition.character_index.composition_profile
                    ),
                )

            self._index_builder_factory = build
        return self._index_builder_factory

    def extract_service(self) -> ExtractAssetsUseCase:
        if self._extract_service is None:
            from ba_downloader.infrastructure.extraction import AssetExtractionWorkflow
            from ba_downloader.infrastructure.extraction.assetripper import (
                AssetRipperBatchExporter,
                AssetRipperBundleWorkflow,
                AssetRipperDependencyScanner,
                AssetRipperSourceResolver,
                BundleBatchScheduler,
                BundleDependencyScanCache,
                CachedBundleDependencyScanner,
                dependency_scan_cache_root,
            )
            from ba_downloader.infrastructure.extraction.assetripper.exporter import (
                assetripper_dependency_scan_cache_key,
            )
            from ba_downloader.infrastructure.runtime.process import (
                CancellableProcessRunner,
            )

            prerequisite = self.definition().tables.extraction_prerequisite(
                self.schema_preparation(),
                self.logger,
            )
            process_runner = CancellableProcessRunner(self.cancellation)
            source_resolver = AssetRipperSourceResolver(
                self.http_client(),
                self.logger,
                cancellation=self.cancellation,
            )
            dependency_scanner = CachedBundleDependencyScanner(
                AssetRipperDependencyScanner(source_resolver, process_runner),
                BundleDependencyScanCache(dependency_scan_cache_root(self.context)),
                tool_key=assetripper_dependency_scan_cache_key(),
            )
            self._extract_service = ExtractAssetsUseCase(
                AssetExtractionWorkflow(
                    self.logger,
                    table_profile_factory=(self.definition().tables.extraction_profile),
                    progress_factory=self._progress_factory,
                    cancellation=self.cancellation,
                    bundle_workflow=AssetRipperBundleWorkflow(
                        AssetRipperBatchExporter(
                            source_resolver,
                            process_runner,
                        ),
                        dependency_scanner,
                        self.logger,
                        progress_factory=self._progress_factory,
                        cancellation=self.cancellation,
                        batch_scheduler=BundleBatchScheduler(),
                    ),
                ),
                self.logger,
                provider=self.provider(),
                character_index_builder_factory=(
                    self.character_index_builder_factory()
                ),
                prerequisite_service=prerequisite,
                workflow_profile=self.workflow_profile(),
                cancellation=self.cancellation,
            )
        return self._extract_service

    def _bus_context(self) -> ExecutionContext:
        platform = self.context.platform or "android"
        workspace_root = Path(self.context.work_dir)
        if self.context.workspace_mode == "v3":
            workspace_root = workspace_root.parents[1]
        workspace = WorkspaceLayout.create(
            workspace_root,
            self.context.region,
            platform,
        )
        return ExecutionContext(
            region=self.context.region,
            platform=platform,
            workspace=workspace,
            proxy_url=self.context.proxy_url,
            max_retries=self.context.max_retries,
            sqlcipher_key=self.context.sqlcipher_key_hex,
            resource_version=self.context.version or None,
        )

    def _require_active(self) -> None:
        if not self._entered:
            raise RuntimeError("Execution scope is not active.")

    @staticmethod
    def _table_metadata_store() -> TableMetadataManifestPort:
        from ba_downloader.infrastructure.storage.table_metadata_manifest import (
            JpTableMetadataManifestStore,
        )

        return JpTableMetadataManifestStore()


@contextmanager
def application_operation_executor(
    context: RuntimeContext,
    *,
    logger: LoggerPort | None = None,
    progress_factory: ProgressReporterFactoryPort | None = None,
    cancellation: CancellationPort | None = None,
    artifacts: ArtifactSinkPort | None = None,
) -> Iterator[ApplicationOperationExecutor]:
    active_cancellation = cancellation or NeverCancelled()
    active_artifacts = artifacts or ArtifactCollector()
    with ExecutionScope(
        context,
        logger=logger,
        progress_factory=progress_factory,
        cancellation=active_cancellation,
    ) as scope:
        yield ApplicationOperationExecutor(
            scope,
            active_cancellation,
            active_artifacts,
            context,
        )
