from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path, PurePosixPath
from threading import Event

import pytest

from ba_downloader.application.bus import (
    CommandBus,
    MessageRegistration,
    QueryBus,
)
from ba_downloader.application.contracts.commands import (
    AssetOperationKind,
    AssetOperationOptions,
    AssetsSyncCommand,
    BuildCharacterIndexCommand,
    CleanupScope,
    CleanupTarget,
    StorageCleanupCommand,
)
from ba_downloader.application.contracts.queries import PreviewAssetsQuery
from ba_downloader.application.contracts.results import (
    ArtifactReference,
    AssetOperationStats,
    OperationResult,
    OperationWarning,
)
from ba_downloader.application.middleware import CancellationMiddleware
from ba_downloader.domain.exceptions import (
    BAError,
    ConfigError,
    DispatchError,
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
from ba_downloader.domain.models.workspace import WorkspaceLayout
from ba_downloader.domain.ports.execution import EventCancellation


def test_workspace_layout_derives_all_v3_paths(tmp_path: Path) -> None:
    layout = WorkspaceLayout.create(tmp_path / "workspace", "jp", "ios")

    assert layout.base == (tmp_path / "workspace" / "jp" / "ios").resolve()
    assert layout.raw_tables == layout.base / "raw" / "tables"
    assert layout.raw_media == layout.base / "raw" / "media"
    assert layout.raw_bundles == layout.base / "raw" / "bundles"
    assert layout.extracted_table_semantic == (
        layout.base / "extracted" / "tables" / "semantic"
    )
    assert layout.extracted_table_raw == (layout.base / "extracted" / "tables" / "raw")
    assert layout.flatbuffer_schemas == (
        layout.base / "extracted" / "schemas" / "flatbuffers"
    )
    assert layout.memorypack_schemas == (
        layout.base / "extracted" / "schemas" / "memorypack"
    )
    assert layout.character_index == layout.base / "indexes" / "characters.json"
    assert layout.runtime_state == layout.base / ".state" / "runtime"
    assert layout.schema_state == layout.base / ".state" / "schema"
    assert layout.manifest_state == layout.base / ".state" / "manifests"


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
    assert command.options.resources.as_strings() == ("table", "media", "bundle")
    assert command.options.asset_filter == AssetFilter()
    with pytest.raises(FrozenInstanceError):
        command.options = AssetOperationOptions(concurrency=1)


def test_asset_operation_options_reject_non_positive_concurrency() -> None:
    with pytest.raises(ConfigError, match="concurrency"):
        AssetOperationOptions(concurrency=0)


def test_cleanup_command_uses_validated_relative_targets() -> None:
    target = CleanupTarget(
        CleanupScope.cache,
        PurePosixPath("http/catalog.json"),
        "file",
    )

    assert StorageCleanupCommand((target,)).targets == (target,)
    with pytest.raises(ConfigError, match="relative"):
        CleanupTarget(CleanupScope.cache, PurePosixPath("../outside"), "file")


def test_preview_query_reuses_asset_operation_options() -> None:
    options = AssetOperationOptions(
        concurrency=4,
        asset_filter=AssetFilter.parse(["type=table"]),
    )

    query = PreviewAssetsQuery(AssetOperationKind.extract, options)

    assert query.operation is AssetOperationKind.extract
    assert query.options is options


def test_operation_result_contains_typed_summary(tmp_path: Path) -> None:
    layout = WorkspaceLayout.create(tmp_path, "gl", "android")
    context = ExecutionContext(region="gl", platform="android", workspace=layout)
    warning = OperationWarning("TABLE_RAW_FALLBACK", "Decoder is unavailable.")
    artifact = ArtifactReference("extracted", PurePosixPath("tables/raw/A.zip"))

    result = OperationResult(
        context=context,
        duration_seconds=1.25,
        data=AssetOperationStats(selected=2, downloaded=2, extracted=1),
        warnings=(warning,),
        artifacts=(artifact,),
    )

    assert result.data.extracted == 1
    assert result.warnings == (warning,)
    assert result.artifacts == (artifact,)


def test_character_index_command_rejects_non_positive_concurrency() -> None:
    with pytest.raises(ConfigError, match="concurrency"):
        BuildCharacterIndexCommand(concurrency=-1)


def test_command_bus_dispatches_exact_message_type(tmp_path: Path) -> None:
    context = ExecutionContext(
        region="jp",
        platform="android",
        workspace=WorkspaceLayout.create(tmp_path, "jp", "android"),
    )
    command = AssetsSyncCommand()

    def handle(
        active_context: ExecutionContext,
        active_command: AssetsSyncCommand,
    ) -> str:
        assert active_context is context
        assert active_command is command
        return "handled"

    bus = CommandBus([MessageRegistration(AssetsSyncCommand, handle)])

    assert bus.dispatch(context, command) == "handled"


def test_command_bus_runs_middleware_in_declaration_order(tmp_path: Path) -> None:
    context = ExecutionContext(
        region="gl",
        platform="android",
        workspace=WorkspaceLayout.create(tmp_path, "gl", "android"),
    )
    events: list[str] = []

    class RecordingMiddleware:
        def __init__(self, name: str) -> None:
            self.name = name

        def __call__(
            self,
            active_context: ExecutionContext,
            message: object,
            call_next,
        ) -> object:
            events.append(f"{self.name}:before")
            result = call_next(active_context, message)
            events.append(f"{self.name}:after")
            return result

    def handle(_: ExecutionContext, __: AssetsSyncCommand) -> str:
        events.append("handler")
        return "done"

    bus = CommandBus(
        [MessageRegistration(AssetsSyncCommand, handle)],
        middleware=[RecordingMiddleware("outer"), RecordingMiddleware("inner")],
    )

    assert bus.dispatch(context, AssetsSyncCommand()) == "done"
    assert events == [
        "outer:before",
        "inner:before",
        "handler",
        "inner:after",
        "outer:after",
    ]


def test_command_and_query_bus_have_separate_registries(tmp_path: Path) -> None:
    context = ExecutionContext(
        region="cn",
        platform="android",
        workspace=WorkspaceLayout.create(tmp_path, "cn", "android"),
    )
    query = PreviewAssetsQuery(AssetOperationKind.sync, AssetOperationOptions())
    query_bus = QueryBus(
        [MessageRegistration(PreviewAssetsQuery, lambda _context, _query: "preview")]
    )
    command_bus = CommandBus()

    assert query_bus.dispatch(context, query) == "preview"
    with pytest.raises(DispatchError) as exc_info:
        command_bus.dispatch(context, query)
    assert exc_info.value.code is ErrorCode.dispatch_unhandled


def test_message_bus_rejects_duplicate_registration() -> None:
    registration = MessageRegistration(
        AssetsSyncCommand,
        lambda _context, _command: None,
    )

    with pytest.raises(DispatchError) as exc_info:
        CommandBus([registration, registration])

    assert exc_info.value.code is ErrorCode.dispatch_duplicate


def test_cancellation_middleware_stops_before_handler(tmp_path: Path) -> None:
    context = ExecutionContext(
        region="jp",
        platform="android",
        workspace=WorkspaceLayout.create(tmp_path, "jp", "android"),
    )
    cancellation_event = Event()
    cancellation_event.set()
    handled = False

    def handle(_: ExecutionContext, __: AssetsSyncCommand) -> None:
        nonlocal handled
        handled = True

    bus = CommandBus(
        [MessageRegistration(AssetsSyncCommand, handle)],
        middleware=[CancellationMiddleware(EventCancellation(cancellation_event))],
    )

    with pytest.raises(OperationCancelledError):
        bus.dispatch(context, AssetsSyncCommand())

    assert handled is False
