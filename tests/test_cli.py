from ba_downloader.cli.main import build_parser


def test_sync_command_parsing() -> None:
    parser = build_parser()
    args = parser.parse_args(["sync", "--region", "jp", "--resource-type", "media"])

    assert args.command == "sync"
    assert args.region == "jp"
    assert args.resource_type == ["media"]


def test_download_command_parsing_with_search() -> None:
    parser = build_parser()
    args = parser.parse_args(["download", "--region", "jp", "--search", "shiroko"])

    assert args.command == "download"
    assert args.region == "jp"
    assert args.search == ["shiroko"]


def test_relation_build_command_parsing() -> None:
    parser = build_parser()
    args = parser.parse_args(["relation", "build", "--region", "gl"])

    assert args.command == "relation"
    assert args.relation_command == "build"
    assert args.region == "gl"
