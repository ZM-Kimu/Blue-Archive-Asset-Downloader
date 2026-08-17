from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from ba_downloader.application.contracts.commands import (
    ApplicationCommand,
    AssetOperationOptions,
    AssetsDownloadCommand,
    AssetsExtractCommand,
    AssetsSyncCommand,
    BuildCharacterIndexCommand,
)
from ba_downloader.application.operations import (
    ApplicationOperation,
    ApplicationOperationCommand,
)
from ba_downloader.bootstrap.container import application_operation_executor
from ba_downloader.domain.exceptions import BAError, ConfigError
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.asset_type_selection import ResourceTypeSelection
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region import Platform, Region
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.workspace import WorkspaceLayout


def _add_environment_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        default=str(Path.cwd()),
        help="Workspace root (default: current directory).",
    )
    parser.add_argument(
        "--region",
        choices=("cn", "gl", "jp"),
        required=True,
        help="Server region: cn, gl, or jp.",
    )
    parser.add_argument(
        "--platform",
        choices=("windows", "android", "ios"),
        default="android",
        help="Asset platform (default: android).",
    )
    parser.add_argument("--proxy", default="", help="HTTP proxy URL.")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum retry count for failed requests (default: 5).",
    )
    parser.add_argument(
        "--sqlcipher-key",
        default="",
        help="SQLCipher raw key override as exactly 64 hex characters.",
    )


def _add_asset_options(parser: argparse.ArgumentParser) -> None:
    _add_environment_options(parser)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=30,
        help="Concurrent worker count (default: 30).",
    )
    parser.add_argument(
        "--resources",
        default="",
        help="Comma-separated resource types: table, media, bundle.",
    )
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help="Asset filter. Repeat for AND; comma-separated values use OR.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ba-downloader")
    groups = parser.add_subparsers(dest="command_group", required=True)

    assets = groups.add_parser("assets", help="Asset operations")
    asset_operations = assets.add_subparsers(dest="operation", required=True)
    for name, help_text in (
        ("sync", "Download and extract assets"),
        ("download", "Download assets only"),
        ("extract", "Extract existing assets"),
    ):
        operation = asset_operations.add_parser(name, help=help_text)
        _add_asset_options(operation)

    index = groups.add_parser("index", help="Index operations")
    index_operations = index.add_subparsers(dest="operation", required=True)
    index_build = index_operations.add_parser("build", help="Build character index")
    _add_environment_options(index_build)
    index_build.add_argument(
        "--concurrency",
        type=int,
        default=30,
        help="Concurrent worker count (default: 30).",
    )

    server = groups.add_parser("server", help="HTTP server operations")
    server_operations = server.add_subparsers(dest="operation", required=True)
    server_start = server_operations.add_parser("start", help="Start the HTTP API")
    server_start.add_argument(
        "--host",
        default="0.0.0.0",
        help="HTTP API bind host (default: 0.0.0.0).",
    )
    server_start.add_argument(
        "--port",
        type=int,
        default=None,
        help="HTTP API port. By default, ports 9230 through 9239 are tried.",
    )
    return parser


def command_from_namespace(args: argparse.Namespace) -> ApplicationCommand:
    if args.command_group == "index" and args.operation == "build":
        return BuildCharacterIndexCommand(concurrency=args.concurrency)
    if args.command_group != "assets":
        raise ConfigError("The selected command is not an application operation.")

    resource_values = tuple(
        value.strip() for value in args.resources.split(",") if value.strip()
    )
    options = AssetOperationOptions(
        concurrency=args.concurrency,
        resources=ResourceTypeSelection.from_values(resource_values),
        asset_filter=AssetFilter.parse(args.filter),
    )
    if args.operation == "sync":
        return AssetsSyncCommand(options)
    if args.operation == "download":
        return AssetsDownloadCommand(options)
    if args.operation == "extract":
        return AssetsExtractCommand(options)
    raise ConfigError(f"Unsupported asset operation '{args.operation}'.")


def execution_context_from_namespace(args: argparse.Namespace) -> ExecutionContext:
    region = cast(Region, args.region)
    platform = cast(Platform, args.platform)
    workspace = WorkspaceLayout.create(args.workspace, region, platform)
    return ExecutionContext(
        region=region,
        platform=platform,
        workspace=workspace,
        proxy_url=args.proxy,
        max_retries=args.max_retries,
        sqlcipher_key=args.sqlcipher_key,
    )


def _runtime_context_adapter(
    context: ExecutionContext,
    command: ApplicationCommand,
) -> RuntimeContext:
    concurrency = getattr(command, "concurrency", None)
    options = getattr(command, "options", None)
    if options is not None:
        concurrency = options.concurrency
        resources = options.resources.as_strings()
        asset_filter = options.asset_filter
    else:
        resources = ("table",)
        asset_filter = AssetFilter()
    return RuntimeContext(
        region=context.region,
        platform=context.platform,
        threads=concurrency or 30,
        version=context.resource_version or "",
        raw_dir=str(context.workspace.raw),
        extract_dir=str(context.workspace.extracted),
        temp_dir=str(context.workspace.temp_state),
        resource_type=resources,
        proxy_url=context.proxy_url,
        max_retries=context.max_retries,
        search=(),
        advanced_search=(),
        work_dir=str(context.workspace.base),
        platform_explicit=True,
        sqlcipher_key_hex=context.sqlcipher_key,
        workspace_mode="v3",
        asset_filter=asset_filter,
    )


def _legacy_operation(command: ApplicationCommand) -> ApplicationOperation:
    if isinstance(command, AssetsSyncCommand):
        return ApplicationOperation.sync
    if isinstance(command, AssetsDownloadCommand):
        return ApplicationOperation.download
    if isinstance(command, AssetsExtractCommand):
        return ApplicationOperation.extract
    if isinstance(command, BuildCharacterIndexCommand):
        return ApplicationOperation.character_index
    raise ConfigError(f"Unsupported command type '{type(command).__name__}'.")


def main(argv: list[str] | None = None) -> int:
    from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
    from ba_downloader.infrastructure.logging.runtime import configure_logging
    from ba_downloader.infrastructure.progress import RichProgressReporterFactory

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging()
    if args.command_group == "server" and args.operation == "start":
        return _serve_api(args.host, args.port)

    logger = ConsoleLogger()
    try:
        command = command_from_namespace(args)
        execution_context = execution_context_from_namespace(args)
        runtime_context = _runtime_context_adapter(execution_context, command)
        with application_operation_executor(
            runtime_context,
            logger=logger,
            progress_factory=RichProgressReporterFactory(),
        ) as executor:
            executor.execute(ApplicationOperationCommand(_legacy_operation(command)))
        return 0
    except KeyboardInterrupt:
        logger.warn("Operation cancelled by user.")
        return 130
    except BAError as exc:
        logger.error(f"[{exc.code.value}] {str(exc) or exc.__class__.__name__}")
        return 2
    except (LookupError, ValueError) as exc:
        logger.error(str(exc) or exc.__class__.__name__)
        return 1


def _serve_api(host: str, port: int | None) -> int:
    from ba_downloader.bootstrap.api_server import serve_http_api

    return serve_http_api(host, port)


if __name__ == "__main__":
    raise SystemExit(main())
