from __future__ import annotations

from pathlib import Path

from ba_downloader.application.contracts.commands import (
    AssetsExtractCommand,
    AssetsSyncCommand,
    BuildCharacterIndexCommand,
)
from ba_downloader.cli.main import build_parser, command_from_namespace
from ba_downloader.domain.models.asset_filter import FilterField, FilterOperator


def test_assets_sync_parser_uses_v3_defaults(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        ["assets", "sync", "--workspace", str(tmp_path), "--region", "jp"]
    )

    assert args.command_group == "assets"
    assert args.operation == "sync"
    assert args.workspace == str(tmp_path)
    assert args.platform == "android"
    assert args.concurrency == 30
    assert args.max_retries == 5
    command = command_from_namespace(args)
    assert isinstance(command, AssetsSyncCommand)
    assert {item.value for item in command.options.resources.types} == {
        "table",
        "media",
        "bundle",
    }


def test_assets_extract_parser_builds_typed_resources_and_filters() -> None:
    args = build_parser().parse_args(
        [
            "assets",
            "extract",
            "--region",
            "cn",
            "--resources",
            "table,bundle",
            "--filter",
            "name~Ibuki,伊吹",
            "--filter",
            "school=Gehenna",
        ]
    )

    command = command_from_namespace(args)

    assert isinstance(command, AssetsExtractCommand)
    assert tuple(item.value for item in command.options.resources.types) == (
        "table",
        "bundle",
    )
    assert command.options.asset_filter.predicates[0].field is FilterField.name
    assert (
        command.options.asset_filter.predicates[0].operator is FilterOperator.contains
    )
    assert command.options.asset_filter.predicates[0].candidates == ("Ibuki", "伊吹")


def test_index_build_parser_builds_typed_command() -> None:
    args = build_parser().parse_args(["index", "build", "--region", "gl"])

    assert isinstance(command_from_namespace(args), BuildCharacterIndexCommand)


def test_server_start_parser_uses_fixed_defaults() -> None:
    args = build_parser().parse_args(["server", "start"])

    assert args.host == "0.0.0.0"
    assert args.port is None
