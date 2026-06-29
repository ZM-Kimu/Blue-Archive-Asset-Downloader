from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.application.use_cases.schema_preparation import (
    SchemaPreparationService,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.ports.relation import RelationBuilderPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort

RelationBuilderFactory = Callable[[RuntimeContext], RelationBuilderPort]


@dataclass(frozen=True, slots=True)
class BaseRuntimeServices:
    logger: LoggerPort
    http_client: HttpClientPort
    provider: RegionProvider


@dataclass(frozen=True, slots=True)
class DownloadRuntimeServices(BaseRuntimeServices):
    downloader: ResourceDownloaderPort


@dataclass(frozen=True, slots=True)
class ExtractRuntimeServices(BaseRuntimeServices):
    extract_service: ExtractAssetsUseCase


@dataclass(frozen=True, slots=True)
class SyncRuntimeServices(BaseRuntimeServices):
    downloader: ResourceDownloaderPort
    extract_service: ExtractAssetsUseCase
    schema_preparation: SchemaPreparationPort
    relation_builder_factory: RelationBuilderFactory


@dataclass(frozen=True, slots=True)
class RelationRuntimeServices(BaseRuntimeServices):
    downloader: ResourceDownloaderPort
    schema_preparation: SchemaPreparationPort
    relation_builder_factory: RelationBuilderFactory


def _build_base_services(context: RuntimeContext) -> BaseRuntimeServices:
    from ba_downloader.bootstrap.registries import DEFAULT_REGION_REGISTRY
    from ba_downloader.infrastructure.http import ResilientHttpClient
    from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger

    logger = ConsoleLogger()
    http_client = ResilientHttpClient(
        proxy_url=context.proxy_url or None,
        max_retries=context.max_retries,
    )
    provider_factory = DEFAULT_REGION_REGISTRY.resolve(context.region)
    provider = provider_factory(http_client=http_client, logger=logger)
    return BaseRuntimeServices(
        logger=logger,
        http_client=http_client,
        provider=provider,
    )


def _build_downloader(
    http_client: HttpClientPort,
    logger: LoggerPort,
    *,
    enable_immediate_extraction: bool = False,
) -> ResourceDownloaderPort:
    from ba_downloader.infrastructure.download import ResourceDownloader

    immediate_extractor = None
    if enable_immediate_extraction:
        from ba_downloader.infrastructure.extraction import ImmediateResourceExtractor

        immediate_extractor = ImmediateResourceExtractor(logger)

    return ResourceDownloader(
        http_client,
        logger,
        immediate_extraction_handler=immediate_extractor,
    )


def _build_runtime_asset_preparer(
    context: RuntimeContext,
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> RuntimeAssetPreparerPort:
    from ba_downloader.bootstrap.registries import (
        DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY,
    )

    preparer_factory = DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.resolve(context.region)
    return preparer_factory(http_client=http_client, logger=logger)


def _build_schema_preparation(
    context: RuntimeContext,
    http_client: HttpClientPort,
    logger: LoggerPort,
) -> SchemaPreparationPort:
    from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow

    return SchemaPreparationService(
        SchemaWorkflow(http_client, logger),
        _build_runtime_asset_preparer(context, http_client, logger),
    )


def _build_relation_builder_factory(logger: LoggerPort) -> RelationBuilderFactory:
    from ba_downloader.infrastructure.extraction.character import CharacterNameRelation

    def relation_builder_factory(active_context: RuntimeContext) -> RelationBuilderPort:
        return CharacterNameRelation(active_context, logger)

    return relation_builder_factory


def _build_extract_service(
    context: RuntimeContext,
    base: BaseRuntimeServices,
    schema_preparation: SchemaPreparationPort,
) -> ExtractAssetsUseCase:
    from ba_downloader.infrastructure.extraction import AssetExtractionWorkflow
    from ba_downloader.infrastructure.extraction.prerequisites import (
        JpTableExtractionPrerequisite,
    )

    _ = context
    relation_builder_factory = _build_relation_builder_factory(base.logger)
    return ExtractAssetsUseCase(
        AssetExtractionWorkflow(base.logger),
        base.logger,
        provider=base.provider,
        relation_builder_factory=relation_builder_factory,
        prerequisite_service=JpTableExtractionPrerequisite(
            schema_preparation,
            base.logger,
        ),
    )


def build_download_runtime_services(
    context: RuntimeContext,
) -> DownloadRuntimeServices:
    base = _build_base_services(context)
    return DownloadRuntimeServices(
        logger=base.logger,
        http_client=base.http_client,
        provider=base.provider,
        downloader=_build_downloader(base.http_client, base.logger),
    )


def build_extract_runtime_services(
    context: RuntimeContext,
) -> ExtractRuntimeServices:
    base = _build_base_services(context)
    schema_preparation = _build_schema_preparation(
        context,
        base.http_client,
        base.logger,
    )
    return ExtractRuntimeServices(
        logger=base.logger,
        http_client=base.http_client,
        provider=base.provider,
        extract_service=_build_extract_service(context, base, schema_preparation),
    )


def build_sync_runtime_services(context: RuntimeContext) -> SyncRuntimeServices:
    base = _build_base_services(context)
    schema_preparation = _build_schema_preparation(
        context,
        base.http_client,
        base.logger,
    )
    relation_builder_factory = _build_relation_builder_factory(base.logger)
    return SyncRuntimeServices(
        logger=base.logger,
        http_client=base.http_client,
        provider=base.provider,
        downloader=_build_downloader(
            base.http_client,
            base.logger,
            enable_immediate_extraction=context.extract_while_download,
        ),
        extract_service=_build_extract_service(context, base, schema_preparation),
        schema_preparation=schema_preparation,
        relation_builder_factory=relation_builder_factory,
    )


def build_relation_runtime_services(
    context: RuntimeContext,
) -> RelationRuntimeServices:
    base = _build_base_services(context)
    schema_preparation = _build_schema_preparation(
        context,
        base.http_client,
        base.logger,
    )
    return RelationRuntimeServices(
        logger=base.logger,
        http_client=base.http_client,
        provider=base.provider,
        downloader=_build_downloader(base.http_client, base.logger),
        schema_preparation=schema_preparation,
        relation_builder_factory=_build_relation_builder_factory(base.logger),
    )
