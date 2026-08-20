from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ba_downloader.application.contracts.commands import (
    AssetOperationOptions,
    AssetsSyncCommand,
    BuildCharacterIndexCommand,
    StorageCleanupCommand,
)
from ba_downloader.domain.exceptions import (
    BAError,
    ConfigError,
    DownloadError,
    ErrorCode,
    ExtractError,
    NetworkError,
    OperationCancelledError,
)
from ba_downloader.domain.models.asset_filter import (
    AssetFilter,
    FilterField,
    FilterOperator,
    FilterPredicate,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.storage import StorageCleanupTarget
from ba_downloader.domain.models.workspace import WorkspaceLayout


def test_workspace_layout_derives_all_v3_paths(tmp_path: Path) -> None:
    layout = WorkspaceLayout.create(tmp_path / "workspace", "jp", "ios")

    assert layout.base == (tmp_path / "workspace" / "jp" / "ios").resolve()
    assert layout.raw_tables == layout.base / "raw" / "tables"
    assert layout.raw_media == layout.base / "raw" / "media"
    assert layout.raw_bundles == layout.base / "raw" / "bundles"
    assert layout.extracted_table_semantic == (
        layout.base / "extracted" / "tables" / "semantic"
    )
    assert layout.flatbuffer_schemas == (
        layout.base / "extracted" / "schemas" / "flatbuffers"
    )
    assert layout.memorypack_schemas == (
        layout.base / "extracted" / "schemas" / "memorypack"
    )
    assert layout.character_index == layout.base / "indexes" / "characters.json"
    assert layout.runtime_state == layout.base / ".state" / "runtime"
    assert layout.schema_state == layout.base / ".state" / "schema"


def test_execution_context_resolves_resource_version_immutably(
    tmp_path: Path,
) -> None:
    layout = WorkspaceLayout.create(tmp_path, "cn", "android")
    context = ExecutionContext(region="cn", platform="android", workspace=layout)

    resolved = context.resolve_resource_version("2.1.2")

    assert context.resource_version is None
    assert resolved.resource_version == "2.1.2"
    assert resolved.resolve_resource_version("2.1.2") is resolved


def test_execution_context_rejects_conflicting_resource_version(
    tmp_path: Path,
) -> None:
    layout = WorkspaceLayout.create(tmp_path, "cn", "android")
    context = ExecutionContext(
        region="cn",
        platform="android",
        workspace=layout,
        resource_version="2.1.2",
    )

    with pytest.raises(ConfigError, match="already resolved"):
        context.resolve_resource_version("2.1.3")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"max_retries": -1}, "max_retries"),
        ({"sqlcipher_key": "not-a-key"}, "SQLCipher"),
        ({"region": "gl"}, "workspace region"),
        ({"platform": "ios"}, "workspace platform"),
    ],
)
def test_execution_context_rejects_invalid_environment(
    tmp_path: Path,
    changes: dict[str, object],
    message: str,
) -> None:
    layout = WorkspaceLayout.create(tmp_path, "cn", "android")
    values: dict[str, object] = {
        "region": "cn",
        "platform": "android",
        "workspace": layout,
    }
    values.update(changes)

    with pytest.raises(ConfigError, match=message):
        ExecutionContext(**values)  # type: ignore[arg-type]


def test_asset_filter_uses_and_between_predicates_and_or_between_values() -> None:
    asset_filter = AssetFilter.parse(["name~Ibuki,イブキ", "school=Abydos,Gehenna"])

    assert asset_filter.predicates == (
        FilterPredicate(
            FilterField.name,
            FilterOperator.contains,
            ("Ibuki", "イブキ"),
        ),
        FilterPredicate(
            FilterField.school,
            FilterOperator.equals,
            ("Abydos", "Gehenna"),
        ),
    )


def test_asset_filter_accepts_empty_expression_collection() -> None:
    assert AssetFilter.parse([]).predicates == ()


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("unknown=value", "Unknown filter field"),
        ("name", "operator"),
        ("name=", "candidate"),
        ("name=Ibuki,", "candidate"),
        ("age~11", "only supports"),
        ("age=eleven", "non-negative integer"),
        ("character-id=-1", "non-negative integer"),
    ],
)
def test_asset_filter_rejects_invalid_expression(
    expression: str,
    message: str,
) -> None:
    with pytest.raises(ConfigError, match=message):
        AssetFilter.parse([expression])


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ConfigError("bad config"), ErrorCode.config_invalid),
        (NetworkError("offline"), ErrorCode.network_failed),
        (DownloadError("download failed"), ErrorCode.download_failed),
        (ExtractError("extract failed"), ErrorCode.extraction_failed),
        (OperationCancelledError("cancelled"), ErrorCode.cancelled),
    ],
)
def test_domain_errors_expose_stable_codes(
    error: BAError,
    code: ErrorCode,
) -> None:
    assert error.code is code
    assert str(error)


def test_asset_command_defaults_are_typed_and_immutable() -> None:
    command = AssetsSyncCommand()

    assert command.options.concurrency == 30
    assert tuple(item.value for item in command.options.resources.types) == (
        "table",
        "media",
        "bundle",
    )
    assert command.options.asset_filter == AssetFilter()
    with pytest.raises(FrozenInstanceError):
        command.options = AssetOperationOptions(concurrency=1)


def test_asset_operation_options_reject_non_positive_concurrency() -> None:
    with pytest.raises(ConfigError, match="concurrency"):
        AssetOperationOptions(concurrency=0)


def test_cleanup_command_uses_validated_relative_targets() -> None:
    target = StorageCleanupTarget(
        "cache",
        "http/catalog.json",
        "file",
    )

    assert StorageCleanupCommand((target,)).targets == (target,)
    with pytest.raises(ConfigError, match="at least one target"):
        StorageCleanupCommand(())


def test_character_index_command_rejects_non_positive_concurrency() -> None:
    with pytest.raises(ConfigError, match="concurrency"):
        BuildCharacterIndexCommand(concurrency=-1)
