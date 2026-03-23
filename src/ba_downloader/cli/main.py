import argparse
from dataclasses import asdict

from ba_downloader.domain.models.settings import AppSettings
from ba_downloader.utils.config import apply_settings


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


def settings_from_namespace(args: argparse.Namespace) -> AppSettings:
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
    return apply_settings(settings)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings_from_namespace(args)

    if args.command == "sync":
        from ba_downloader.application.services.sync import SyncService

        SyncService().run()
        return 0

    if args.command == "download":
        from ba_downloader.application.services.download import DownloadService

        DownloadService().run()
        return 0

    if args.command == "extract":
        from ba_downloader.application.services.extract import ExtractService

        ExtractService().run()
        return 0

    if args.command == "relation" and args.relation_command == "build":
        from ba_downloader.application.services.relation import RelationService

        RelationService().build()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
