from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ba_downloader.application.use_cases.extract_assets import ExtractAssetsUseCase
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort


@dataclass(frozen=True, slots=True)
class CliRuntimeServices:
    logger: LoggerPort
    http_client: HttpClientPort
    provider: Any
    runtime_asset_preparer: Any
    downloader: Any
    extract_service: ExtractAssetsUseCase
    schema_workflow: Any
    relation_builder_factory: Callable[[RuntimeContext], Any]


def build_cli_runtime_services(context: RuntimeContext) -> CliRuntimeServices:
    from ba_downloader.bootstrap.registries import (
        DEFAULT_REGION_REGISTRY,
        DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY,
    )
    from ba_downloader.infrastructure.download import ResourceDownloader
    from ba_downloader.infrastructure.extraction import (
        AssetExtractionWorkflow,
        ImmediateResourceExtractor,
    )
    from ba_downloader.infrastructure.extraction.character import CharacterNameRelation
    from ba_downloader.infrastructure.http import ResilientHttpClient
    from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
    from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow

    logger = ConsoleLogger()
    http_client = ResilientHttpClient(
        proxy_url=context.proxy_url or None,
        max_retries=context.max_retries,
    )
    provider_factory = DEFAULT_REGION_REGISTRY.resolve(context.region)
    preparer_factory = DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.resolve(context.region)
    runtime_asset_preparer = preparer_factory(
        http_client=http_client,
        logger=logger,
    )
    schema_workflow = SchemaWorkflow(http_client, logger)
    immediate_extractor = ImmediateResourceExtractor(logger)

    def relation_builder_factory(
        active_context: RuntimeContext,
    ) -> CharacterNameRelation:
        return CharacterNameRelation(active_context, logger)

    return CliRuntimeServices(
        logger=logger,
        http_client=http_client,
        provider=provider_factory(http_client=http_client, logger=logger),
        runtime_asset_preparer=runtime_asset_preparer,
        downloader=ResourceDownloader(
            http_client,
            logger,
            immediate_extraction_handler=immediate_extractor,
        ),
        extract_service=ExtractAssetsUseCase(
            AssetExtractionWorkflow(logger),
            schema_workflow,
            runtime_asset_preparer,
            logger,
        ),
        schema_workflow=schema_workflow,
        relation_builder_factory=relation_builder_factory,
    )
