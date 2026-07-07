from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ba_downloader.application.profiles import RegionProfile
from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.application.use_cases.schema_preparation import (
    SchemaPreparationService,
)
from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
    RegionServiceProfile,
    build_application_region_profile,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.catalog_metadata import TableMetadataManifestPort
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort

CharacterIndexBuilderFactory = Callable[[RuntimeContext], CharacterIndexBuilderPort]


@dataclass(frozen=True, slots=True)
class BaseRuntimeServices:
    logger: LoggerPort
    http_client: HttpClientPort
    provider: RegionProvider
    service_profile: RegionServiceProfile


@dataclass(frozen=True, slots=True)
class DownloadRuntimeServices(BaseRuntimeServices):
    downloader: ResourceDownloaderPort
    workflow_profile: RegionProfile


@dataclass(frozen=True, slots=True)
class ExtractRuntimeServices(BaseRuntimeServices):
    extract_service: ExtractAssetsUseCase
    workflow_profile: RegionProfile


@dataclass(frozen=True, slots=True)
class SyncRuntimeServices(BaseRuntimeServices):
    downloader: ResourceDownloaderPort
    extract_service: ExtractAssetsUseCase
    schema_preparation: SchemaPreparationPort
    character_index_builder_factory: CharacterIndexBuilderFactory
    workflow_profile: RegionProfile


@dataclass(frozen=True, slots=True)
class CharacterIndexRuntimeServices(BaseRuntimeServices):
    downloader: ResourceDownloaderPort
    schema_preparation: SchemaPreparationPort
    character_index_builder_factory: CharacterIndexBuilderFactory


def _build_base_services(context: RuntimeContext) -> BaseRuntimeServices:
    from ba_downloader.infrastructure.http import ResilientHttpClient
    from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger

    logger = ConsoleLogger()
    http_client = ResilientHttpClient(
        proxy_url=context.proxy_url or None,
        max_retries=context.max_retries,
    )
    service_profile = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(context.region)
    provider = service_profile.provider_factory(http_client, logger)
    return BaseRuntimeServices(
        logger=logger,
        http_client=http_client,
        provider=provider,
        service_profile=service_profile,
    )


def _build_downloader(
    http_client: HttpClientPort,
    logger: LoggerPort,
    service_profile: RegionServiceProfile,
    *,
    enable_immediate_extraction: bool = False,
) -> ResourceDownloaderPort:
    from ba_downloader.infrastructure.download import ResourceDownloader

    immediate_extractor = None
    if enable_immediate_extraction:
        from ba_downloader.infrastructure.extraction import ImmediateResourceExtractor

        immediate_extractor = ImmediateResourceExtractor(
            logger,
            table_profile_factory=service_profile.table_profile_factory,
        )

    return ResourceDownloader(
        http_client,
        logger,
        immediate_extraction_handler=immediate_extractor,
    )


def _build_runtime_asset_preparer(
    context: RuntimeContext,
    http_client: HttpClientPort,
    logger: LoggerPort,
    service_profile: RegionServiceProfile,
) -> RuntimeAssetPreparerPort:
    _ = context
    return service_profile.runtime_asset_preparer_factory(http_client, logger)


def _build_schema_preparation(
    context: RuntimeContext,
    http_client: HttpClientPort,
    logger: LoggerPort,
    service_profile: RegionServiceProfile,
) -> SchemaPreparationPort:
    from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow

    return SchemaPreparationService(
        SchemaWorkflow(
            http_client,
            logger,
            dumper_backend_factory=service_profile.dumper_backend_factory,
        ),
        _build_runtime_asset_preparer(context, http_client, logger, service_profile),
    )


def _build_character_index_builder_factory(
    logger: LoggerPort,
    service_profile: RegionServiceProfile,
) -> CharacterIndexBuilderFactory:
    from ba_downloader.infrastructure.extraction.character import CharacterIndexBuilder

    def character_index_builder_factory(
        active_context: RuntimeContext,
    ) -> CharacterIndexBuilderPort:
        return CharacterIndexBuilder(
            active_context,
            logger,
            table_profile_factory=service_profile.table_profile_factory,
            character_index_source_profile_factory=(
                service_profile.character_index_source_profile_factory
            ),
            character_index_composition_profile_factory=(
                service_profile.character_index_composition_profile_factory
            ),
        )

    return character_index_builder_factory


def _build_table_metadata_store() -> TableMetadataManifestPort:
    from ba_downloader.infrastructure.storage.table_metadata_manifest import (
        JpTableMetadataManifestStore,
    )

    return JpTableMetadataManifestStore()


def _build_extract_service(
    context: RuntimeContext,
    base: BaseRuntimeServices,
    schema_preparation: SchemaPreparationPort,
    workflow_profile: RegionProfile,
) -> ExtractAssetsUseCase:
    from ba_downloader.infrastructure.extraction import AssetExtractionWorkflow

    prerequisite_service = base.service_profile.extraction_prerequisite_factory(
        schema_preparation,
        base.logger,
    )

    _ = context
    character_index_builder_factory = _build_character_index_builder_factory(
        base.logger,
        base.service_profile,
    )
    return ExtractAssetsUseCase(
        AssetExtractionWorkflow(
            base.logger,
            table_profile_factory=base.service_profile.table_profile_factory,
        ),
        base.logger,
        provider=base.provider,
        character_index_builder_factory=character_index_builder_factory,
        prerequisite_service=prerequisite_service,
        workflow_profile=workflow_profile,
    )


def build_download_runtime_services(
    context: RuntimeContext,
) -> DownloadRuntimeServices:
    base = _build_base_services(context)
    workflow_profile = build_application_region_profile(
        base.service_profile,
        context,
        http_client=base.http_client,
        logger=base.logger,
        table_metadata_store=_build_table_metadata_store(),
        provider=base.provider,
    )
    return DownloadRuntimeServices(
        logger=base.logger,
        http_client=base.http_client,
        provider=base.provider,
        service_profile=base.service_profile,
        downloader=_build_downloader(
            base.http_client,
            base.logger,
            base.service_profile,
        ),
        workflow_profile=workflow_profile,
    )


def build_extract_runtime_services(
    context: RuntimeContext,
) -> ExtractRuntimeServices:
    base = _build_base_services(context)
    schema_preparation = _build_schema_preparation(
        context,
        base.http_client,
        base.logger,
        base.service_profile,
    )
    workflow_profile = build_application_region_profile(
        base.service_profile,
        context,
        http_client=base.http_client,
        logger=base.logger,
        table_metadata_store=_build_table_metadata_store(),
        provider=base.provider,
    )
    return ExtractRuntimeServices(
        logger=base.logger,
        http_client=base.http_client,
        provider=base.provider,
        service_profile=base.service_profile,
        extract_service=_build_extract_service(
            context,
            base,
            schema_preparation,
            workflow_profile,
        ),
        workflow_profile=workflow_profile,
    )


def build_sync_runtime_services(context: RuntimeContext) -> SyncRuntimeServices:
    base = _build_base_services(context)
    schema_preparation = _build_schema_preparation(
        context,
        base.http_client,
        base.logger,
        base.service_profile,
    )
    character_index_builder_factory = _build_character_index_builder_factory(
        base.logger,
        base.service_profile,
    )
    workflow_profile = build_application_region_profile(
        base.service_profile,
        context,
        http_client=base.http_client,
        logger=base.logger,
        table_metadata_store=_build_table_metadata_store(),
        provider=base.provider,
    )
    return SyncRuntimeServices(
        logger=base.logger,
        http_client=base.http_client,
        provider=base.provider,
        service_profile=base.service_profile,
        downloader=_build_downloader(
            base.http_client,
            base.logger,
            base.service_profile,
            enable_immediate_extraction=context.extract_while_download,
        ),
        extract_service=_build_extract_service(
            context,
            base,
            schema_preparation,
            workflow_profile,
        ),
        schema_preparation=schema_preparation,
        character_index_builder_factory=character_index_builder_factory,
        workflow_profile=workflow_profile,
    )


def build_character_index_runtime_services(
    context: RuntimeContext,
) -> CharacterIndexRuntimeServices:
    base = _build_base_services(context)
    schema_preparation = _build_schema_preparation(
        context,
        base.http_client,
        base.logger,
        base.service_profile,
    )
    return CharacterIndexRuntimeServices(
        logger=base.logger,
        http_client=base.http_client,
        provider=base.provider,
        service_profile=base.service_profile,
        downloader=_build_downloader(
            base.http_client,
            base.logger,
            base.service_profile,
        ),
        schema_preparation=schema_preparation,
        character_index_builder_factory=_build_character_index_builder_factory(
            base.logger,
            base.service_profile,
        ),
    )
