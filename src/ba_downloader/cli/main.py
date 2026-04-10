from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from ba_downloader.application.services.download import DownloadService
from ba_downloader.application.services.extract import ExtractService
from ba_downloader.application.services.relation import RelationService
from ba_downloader.application.services.sync import SyncService
from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.settings import AppSettings, Platform, Region
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort


@dataclass(frozen=True, slots=True)
class _CliRuntimeServices:
    logger: LoggerPort
    http_client: HttpClientPort
    provider: Any
    runtime_asset_preparer: Any
    downloader: Any
    extract_service: ExtractService
    flatbuffer_workflow: Any


class _StorePlatformAction(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        _ = parser
        _ = option_string
        if not isinstance(values, str):
            raise argparse.ArgumentError(self, "Platform must be a single string value.")
        setattr(namespace, self.dest, values)
        namespace.platform_explicit = True


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--region", "-r", choices=["cn", "gl", "jp"], required=True)
    parser.add_argument("--threads", "-t", type=int, default=20)
    parser.add_argument("--version", "-v", default="")
    parser.add_argument("--raw-dir", "-rd", default="RawData")
    parser.add_argument("--extract-dir", "-ed", default="Extracted")
    parser.add_argument("--temp-dir", "-td", default="Temp")
    parser.add_argument(
        "--resource-type",
        "-rt",
        choices=["table", "media", "bundle", "all"],
        nargs="*",
        default=["all"],
    )
    parser.add_argument("--proxy", "-px", default="")
    parser.add_argument("--max-retries", "-mr", type=int, default=5)
    parser.add_argument(
        "--platform",
        "-p",
        choices=["windows", "android", "ios"],
        default="android",
        action=_StorePlatformAction,
        help="JP bundle platform (default: android)",
    )
    parser.set_defaults(platform_explicit=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ba-downloader")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Download and extract assets")
    _add_common_options(sync_parser)
    sync_parser.add_argument("--extract-while-download", "-ewd", action="store_true")
    sync_parser.add_argument("--search", "-s", nargs="*", default=[])
    sync_parser.add_argument("--advanced-search", "-as", nargs="*", default=[])

    download_parser = subparsers.add_parser("download", help="Download assets only")
    _add_common_options(download_parser)
    download_parser.add_argument("--search", "-s", nargs="*", default=[])

    extract_parser = subparsers.add_parser("extract", help="Extract existing raw assets")
    _add_common_options(extract_parser)

    relation_parser = subparsers.add_parser("relation", help="Character relation commands")
    relation_sub = relation_parser.add_subparsers(dest="relation_command", required=True)
    relation_build = relation_sub.add_parser("build", help="Build character relation file")
    _add_common_options(relation_build)

    return parser


def runtime_context_from_namespace(args: argparse.Namespace) -> RuntimeContext:
    settings = AppSettings(
        region=cast(Region, args.region),
        threads=args.threads,
        version=args.version,
        raw_dir=args.raw_dir,
        extract_dir=args.extract_dir,
        temp_dir=args.temp_dir,
        extract_while_download=getattr(args, "extract_while_download", False),
        resource_type=tuple(args.resource_type),
        proxy_url=args.proxy,
        max_retries=args.max_retries,
        search=tuple(getattr(args, "search", [])),
        advanced_search=tuple(getattr(args, "advanced_search", [])),
        platform=cast(Platform, getattr(args, "platform", "android")),
        platform_explicit=getattr(args, "platform_explicit", False),
    )
    return RuntimeContext.from_settings(settings)


def _build_provider(
    context: RuntimeContext,
    logger: LoggerPort,
    http_client: HttpClientPort,
):
    from ba_downloader.infrastructure.regions.registry import DEFAULT_REGION_REGISTRY

    provider_factory = DEFAULT_REGION_REGISTRY.resolve(context.region)
    return provider_factory(http_client=http_client, logger=logger)


def _build_runtime_asset_preparer(
    context: RuntimeContext,
    logger: LoggerPort,
    http_client: HttpClientPort,
):
    from ba_downloader.infrastructure.runtime import (
        DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY,
    )

    preparer_factory = DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.resolve(context.region)
    return preparer_factory(http_client=http_client, logger=logger)


def _build_cli_runtime_services(context: RuntimeContext) -> _CliRuntimeServices:
    from ba_downloader.infrastructure.download import ResourceDownloader
    from ba_downloader.infrastructure.extract import AssetExtractionWorkflow
    from ba_downloader.infrastructure.http import ResilientHttpClient
    from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
    from ba_downloader.infrastructure.tools.flatbuffer_workflow import (
        FlatbufferWorkflow,
    )

    logger = ConsoleLogger()
    http_client = ResilientHttpClient(
        proxy_url=context.proxy_url or None,
        max_retries=context.max_retries,
    )
    runtime_asset_preparer = _build_runtime_asset_preparer(context, logger, http_client)
    flatbuffer_workflow = FlatbufferWorkflow(http_client, logger)
    return _CliRuntimeServices(
        logger=logger,
        http_client=http_client,
        provider=_build_provider(context, logger, http_client),
        runtime_asset_preparer=runtime_asset_preparer,
        downloader=ResourceDownloader(http_client, logger),
        extract_service=ExtractService(
            AssetExtractionWorkflow(logger),
            flatbuffer_workflow,
            runtime_asset_preparer,
            logger,
        ),
        flatbuffer_workflow=flatbuffer_workflow,
    )


def _build_relation_builder_factory(
    logger: LoggerPort,
) -> Callable[[RuntimeContext], Any]:
    from ba_downloader.infrastructure.extractors.character import CharacterNameRelation

    def relation_builder_factory(active_context: RuntimeContext) -> CharacterNameRelation:
        return CharacterNameRelation(active_context, logger)

    return relation_builder_factory


def _run_command(
    args: argparse.Namespace,
    context: RuntimeContext,
    services: _CliRuntimeServices,
) -> int:
    relation_builder_factory = _build_relation_builder_factory(services.logger)

    if args.command == "sync":
        SyncService(
            services.provider,
            services.downloader,
            services.extract_service,
            services.flatbuffer_workflow,
            services.runtime_asset_preparer,
            relation_builder_factory,
            services.logger,
        ).run(context)
        return 0

    if args.command == "download":
        DownloadService(services.provider, services.downloader).run(context)
        return 0

    if args.command == "extract":
        services.extract_service.run(context)
        return 0

    if args.command == "relation" and args.relation_command == "build":
        RelationService(
            services.provider,
            services.downloader,
            services.flatbuffer_workflow,
            services.runtime_asset_preparer,
            relation_builder_factory,
        ).build(context)
        return 0

    return 1


def main(argv: list[str] | None = None) -> int:
    from ba_downloader.infrastructure.logging.runtime import configure_logging

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging()
    context = runtime_context_from_namespace(args)
    services = _build_cli_runtime_services(context)

    try:
        command_result = _run_command(args, context, services)
        if command_result == 0:
            return 0
    except KeyboardInterrupt:
        services.logger.warn("Operation cancelled by user.")
        return 130
    except (LookupError, NetworkError) as exc:
        services.logger.error(str(exc) or exc.__class__.__name__)
        return 1
    finally:
        services.http_client.close()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
