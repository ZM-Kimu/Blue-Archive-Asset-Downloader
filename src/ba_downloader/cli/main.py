from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any, cast

from ba_downloader.application.config import AppSettings
from ba_downloader.application.use_cases.build_character_index import (
    BuildCharacterIndexUseCase,
)
from ba_downloader.application.use_cases.download_assets import DownloadAssetsUseCase
from ba_downloader.application.use_cases.sync_assets import SyncAssetsUseCase
from ba_downloader.bootstrap.container import (
    BaseRuntimeServices,
    CharacterIndexRuntimeServices,
    DownloadRuntimeServices,
    ExtractRuntimeServices,
    SyncRuntimeServices,
    build_character_index_runtime_services,
    build_download_runtime_services,
    build_extract_runtime_services,
    build_sync_runtime_services,
)
from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
)
from ba_downloader.domain.exceptions import DownloadError, ExtractError, NetworkError
from ba_downloader.domain.models.region import Platform, Region
from ba_downloader.domain.models.runtime import RuntimeContext


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
            raise argparse.ArgumentError(
                self, "Platform must be a single string value."
            )
        setattr(namespace, self.dest, values)
        namespace.platform_explicit = True


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        "-r",
        choices=["cn", "gl", "jp"],
        required=True,
        help="Server region: cn, gl, or jp.",
    )
    parser.add_argument(
        "--threads",
        "-t",
        type=int,
        default=20,
        help="Concurrent download or extraction worker count.",
    )
    parser.add_argument(
        "--version",
        "-v",
        default="",
        help="Resource version. Effective for GL only; JP resolves the latest version.",
    )
    parser.add_argument(
        "--raw-dir",
        "-rd",
        default="RawData",
        help=(
            "Raw asset directory. The default logical name is normalized by region "
            "when unchanged."
        ),
    )
    parser.add_argument(
        "--extract-dir",
        "-ed",
        default="Extracted",
        help=(
            "Extracted asset directory. The default logical name is normalized by "
            "region when unchanged."
        ),
    )
    parser.add_argument(
        "--temp-dir",
        "-td",
        default="Temp",
        help=(
            "Temporary asset directory. The default logical name is normalized by "
            "region when unchanged."
        ),
    )
    parser.add_argument(
        "--resource-type",
        "-rt",
        choices=["table", "media", "bundle", "all"],
        nargs="*",
        default=["all"],
        help="Resource types to process.",
    )
    parser.add_argument("--proxy", "-px", default="", help="HTTP proxy URL.")
    parser.add_argument(
        "--max-retries",
        "-mr",
        type=int,
        default=5,
        help="Maximum retry count for failed downloads.",
    )
    parser.add_argument(
        "--sqlcipher-key-hex",
        "-kei",
        default="",
        help=(
            "SQLCipher raw key override as 64 hex characters; "
            "JP fetches the default key when omitted."
        ),
    )
    parser.add_argument(
        "--platform",
        "-p",
        choices=["windows", "android", "ios"],
        default="android",
        action=_StorePlatformAction,
        help="JP bundle platform (default: android)",
    )
    parser.set_defaults(platform_explicit=False)


def _add_basic_search_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--search",
        "-s",
        nargs="*",
        default=[],
        help="Search assets by file or bundle name.",
    )


def _add_search_options(parser: argparse.ArgumentParser, *, advanced_help: str) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--search",
        "-s",
        nargs="*",
        default=[],
        help="Search assets by file or bundle name.",
    )
    group.add_argument(
        "--advanced-search",
        "-as",
        nargs="*",
        default=[],
        help=advanced_help,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ba-downloader")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Download and extract assets")
    _add_common_options(sync_parser)
    sync_parser.add_argument(
        "--extract-while-download",
        "-ewd",
        action="store_true",
        help="Extract supported resources immediately after each download.",
    )
    _add_search_options(
        sync_parser,
        advanced_help="Search assets by character index fields.",
    )

    download_parser = subparsers.add_parser("download", help="Download assets only")
    _add_common_options(download_parser)
    _add_basic_search_option(download_parser)

    extract_parser = subparsers.add_parser(
        "extract", help="Extract existing raw assets"
    )
    _add_common_options(extract_parser)
    _add_search_options(
        extract_parser,
        advanced_help="Search existing raw assets by character index fields.",
    )

    character_index_parser = subparsers.add_parser(
        "character-index", help="Character index commands"
    )
    character_index_sub = character_index_parser.add_subparsers(
        dest="character_index_command", required=True
    )
    character_index_build = character_index_sub.add_parser(
        "build", help="Build character index file"
    )
    _add_common_options(character_index_build)

    return parser


def runtime_context_from_namespace(args: argparse.Namespace) -> RuntimeContext:
    region = cast(Region, args.region)
    service_profile = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(region)
    settings = AppSettings(
        region=region,
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
        sqlcipher_key_hex=getattr(args, "sqlcipher_key_hex", ""),
    )
    return settings.to_runtime_context(service_profile.settings_policy)


def _run_command(
    args: argparse.Namespace,
    context: RuntimeContext,
    services: BaseRuntimeServices,
) -> int:
    if args.command == "sync" and isinstance(services, SyncRuntimeServices):
        SyncAssetsUseCase(
            services.provider,
            services.downloader,
            services.extract_service,
            services.schema_preparation,
            services.character_index_builder_factory,
            services.logger,
            workflow_profile=services.workflow_profile,
        ).run(context)
        return 0

    if args.command == "download" and isinstance(services, DownloadRuntimeServices):
        DownloadAssetsUseCase(
            services.provider,
            services.downloader,
            workflow_profile=services.workflow_profile,
        ).run(context)
        return 0

    if args.command == "extract" and isinstance(services, ExtractRuntimeServices):
        services.extract_service.run(context)
        return 0

    if (
        args.command == "character-index"
        and args.character_index_command == "build"
        and isinstance(services, CharacterIndexRuntimeServices)
    ):
        BuildCharacterIndexUseCase(
            services.provider,
            services.downloader,
            services.schema_preparation,
            services.character_index_builder_factory,
        ).build(context)
        return 0

    return 1


def _build_services(
    args: argparse.Namespace,
    context: RuntimeContext,
) -> BaseRuntimeServices:
    if args.command == "sync":
        return build_sync_runtime_services(context)
    if args.command == "download":
        return build_download_runtime_services(context)
    if args.command == "extract":
        return build_extract_runtime_services(context)
    if args.command == "character-index" and args.character_index_command == "build":
        return build_character_index_runtime_services(context)
    raise LookupError(f"Unsupported command '{args.command}'.")


def _log_cli_error(services: BaseRuntimeServices | None, message: str) -> None:
    if services is None:
        from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger

        ConsoleLogger().error(message)
        return
    services.logger.error(message)


def main(argv: list[str] | None = None) -> int:
    from ba_downloader.infrastructure.logging.runtime import configure_logging

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging()
    context = runtime_context_from_namespace(args)
    services: BaseRuntimeServices | None = None

    try:
        services = _build_services(args, context)
        command_result = _run_command(args, context, services)
        if command_result == 0:
            return 0
    except KeyboardInterrupt:
        if services is None:
            from ba_downloader.infrastructure.logging.console_logger import (
                ConsoleLogger,
            )

            ConsoleLogger().warn("Operation cancelled by user.")
        else:
            services.logger.warn("Operation cancelled by user.")
        return 130
    except (LookupError, DownloadError, ExtractError, NetworkError) as exc:
        _log_cli_error(services, str(exc) or exc.__class__.__name__)
        return 1
    finally:
        if services is not None:
            services.http_client.close()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
