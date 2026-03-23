import argparse

from ba_downloader.application.services.download import DownloadService
from ba_downloader.application.services.extract import ExtractService
from ba_downloader.application.services.relation import RelationService
from ba_downloader.application.services.sync import SyncService
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.settings import AppSettings
from ba_downloader.infrastructure.download import ResourceDownloader
from ba_downloader.infrastructure.extract import AssetExtractionWorkflow
from ba_downloader.infrastructure.extractors.character import CharacterNameRelation
from ba_downloader.infrastructure.http import ResilientHttpClient
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
from ba_downloader.infrastructure.logging.runtime import configure_logging
from ba_downloader.infrastructure.regions.registry import DEFAULT_REGION_REGISTRY
from ba_downloader.infrastructure.tools.flatbuffer_workflow import FlatbufferWorkflow


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--region", "-g", choices=["cn", "gl", "jp"], required=True)
    parser.add_argument("--threads", "-t", type=int, default=20)
    parser.add_argument("--version", "-v", default="")
    parser.add_argument("--raw-dir", "-r", default="RawData")
    parser.add_argument("--extract-dir", "-e", default="Extracted")
    parser.add_argument("--temp-dir", "-m", default="Temp")
    parser.add_argument(
        "--resource-type",
        "-rt",
        choices=["table", "media", "bundle", "all"],
        nargs="*",
        default=["all"],
    )
    parser.add_argument("--proxy", "-p", default="")
    parser.add_argument("--max-retries", "-mr", type=int, default=5)


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

    extract_parser = subparsers.add_parser("extract", help="Extract existing raw assets")
    _add_common_options(extract_parser)

    relation_parser = subparsers.add_parser("relation", help="Character relation commands")
    relation_sub = relation_parser.add_subparsers(dest="relation_command", required=True)
    relation_build = relation_sub.add_parser("build", help="Build character relation file")
    _add_common_options(relation_build)

    return parser


def runtime_context_from_namespace(args: argparse.Namespace) -> RuntimeContext:
    settings = AppSettings(
        region=args.region,
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
    )
    return RuntimeContext.from_settings(settings)


def _build_provider(context: RuntimeContext, logger: ConsoleLogger, http_client: ResilientHttpClient):
    provider_factory = DEFAULT_REGION_REGISTRY.resolve(context.region)
    return provider_factory(http_client=http_client, logger=logger)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging()
    context = runtime_context_from_namespace(args)
    logger = ConsoleLogger()
    http_client = ResilientHttpClient(
        proxy_url=context.proxy_url or None,
        max_retries=context.max_retries,
    )
    provider = _build_provider(context, logger, http_client)
    downloader = ResourceDownloader(http_client, logger)
    extraction_workflow = AssetExtractionWorkflow(logger)
    extract_service = ExtractService(extraction_workflow)
    flatbuffer_workflow = FlatbufferWorkflow(http_client, logger)
    relation_builder_factory = lambda active_context: CharacterNameRelation(
        active_context,
        logger,
    )

    if args.command == "sync":
        SyncService(
            provider,
            downloader,
            extract_service,
            flatbuffer_workflow,
            relation_builder_factory,
            logger,
        ).run(context)
        return 0

    if args.command == "download":
        DownloadService(provider, downloader).run(context)
        return 0

    if args.command == "extract":
        extract_service.run(context)
        return 0

    if args.command == "relation" and args.relation_command == "build":
        RelationService(
            provider,
            downloader,
            flatbuffer_workflow,
            relation_builder_factory,
        ).build(context)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
