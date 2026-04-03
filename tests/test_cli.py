from ba_downloader.cli.main import build_parser, runtime_context_from_namespace


def test_sync_command_parsing() -> None:
    parser = build_parser()
    args = parser.parse_args(["sync", "--region", "jp", "--resource-type", "media"])

    assert args.command == "sync"
    assert args.region == "jp"
    assert args.resource_type == ["media"]
    assert args.platform == "android"
    assert args.platform_explicit is False


def test_sync_command_parses_new_short_options() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "sync",
            "-r",
            "jp",
            "-t",
            "8",
            "-v",
            "1.2.3",
            "-p",
            "ios",
            "-rd",
            "raw",
            "-ed",
            "out",
            "-td",
            "tmp",
            "-rt",
            "bundle",
            "media",
            "-px",
            "http://127.0.0.1:8080",
            "-mr",
            "7",
            "-s",
            "shiroko",
            "-as",
            "hoshino",
            "-ewd",
        ]
    )

    assert args.command == "sync"
    assert args.region == "jp"
    assert args.threads == 8
    assert args.version == "1.2.3"
    assert args.platform == "ios"
    assert args.platform_explicit is True
    assert args.raw_dir == "raw"
    assert args.extract_dir == "out"
    assert args.temp_dir == "tmp"
    assert args.resource_type == ["bundle", "media"]
    assert args.proxy == "http://127.0.0.1:8080"
    assert args.max_retries == 7
    assert args.search == ["shiroko"]
    assert args.advanced_search == ["hoshino"]
    assert args.extract_while_download is True


def test_download_command_parsing_with_search() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["download", "--region", "jp", "--platform", "windows", "--search", "shiroko"]
    )

    assert args.command == "download"
    assert args.region == "jp"
    assert args.platform == "windows"
    assert args.platform_explicit is True
    assert args.search == ["shiroko"]


def test_relation_build_command_parsing() -> None:
    parser = build_parser()
    args = parser.parse_args(["relation", "build", "--region", "gl"])

    assert args.command == "relation"
    assert args.relation_command == "build"
    assert args.region == "gl"
    assert args.platform == "android"


def test_extract_command_accepts_platform_and_updates_runtime_context() -> None:
    parser = build_parser()
    args = parser.parse_args(["extract", "--region", "jp", "--platform", "ios"])

    context = runtime_context_from_namespace(args)

    assert context.platform == "ios"
    assert context.platform_explicit is True
    assert context.raw_dir == "JP_iOS_RawData"
    assert context.extract_dir == "JP_iOS_Extracted"
    assert context.temp_dir == "JP_iOS_Temp"
