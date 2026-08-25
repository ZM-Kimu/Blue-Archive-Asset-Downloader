from __future__ import annotations

import base64
import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast
from uuid import uuid4

from ba_downloader.domain.exceptions import ProcessExecutionError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.process import (
    ProcessCommand,
    ProcessOutputLine,
    ProcessOutputObserverPort,
    ProcessResult,
    ProcessRunnerPort,
)
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleArchiveScan,
    BundleEntryInput,
    BundleEntryScan,
    SerializedFileScan,
    StreamedResourceScan,
)
from ba_downloader.infrastructure.extraction.assetripper.entry_store import (
    bundle_entry_cache_identity,
)
from ba_downloader.infrastructure.extraction.assetripper.events import (
    AssetRipperProcessEvent,
    parse_assetripper_event,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    ASSETRIPPER_COMMIT,
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    write_json_atomic,
)
from ba_downloader.infrastructure.files.build_cache import (
    validate_build_manifest,
    write_build_manifest,
)
from ba_downloader.infrastructure.files.checksum import calculate_source_fingerprint
from ba_downloader.infrastructure.files.lock import wait_for_interprocess_lock

ASSETRIPPER_EXPORTED_CONTENT_PROFILE = "readable-playable"


def assetripper_exporter_cache_key() -> str:
    root = _assetripper_tool_root()
    sources = (
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in {".cs", ".csproj"}
        and "runtime_inspector" not in path.relative_to(root).parts
    )
    return calculate_source_fingerprint(
        root,
        sources,
        identities=(
            ("assetripper-commit", ASSETRIPPER_COMMIT),
            ("overlay", AssetRipperSourceResolver.overlay_hash()),
        ),
    )


def assetripper_exported_content_fingerprint() -> str:
    root = _assetripper_tool_root()
    sources = [
        root / "ContentProfile.cs",
        *(
            path
            for directory in (root / "PrimaryContent", root / "Models")
            for path in directory.rglob("*.cs")
        ),
    ]
    return calculate_source_fingerprint(
        root,
        sources,
        identities=(
            ("assetripper-commit", ASSETRIPPER_COMMIT),
            (
                "content-overlay",
                AssetRipperSourceResolver.overlay_hash(content_only=True),
            ),
            ("profile", ASSETRIPPER_EXPORTED_CONTENT_PROFILE),
        ),
    )


def assetripper_runtime_inspector_cache_key() -> str:
    root = _assetripper_tool_root() / "runtime_inspector"
    sources = (
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".cs", ".csproj"}
    )
    return calculate_source_fingerprint(
        root,
        sources,
        identities=(
            ("assetripper-commit", ASSETRIPPER_COMMIT),
            ("overlay", AssetRipperSourceResolver.overlay_hash()),
        ),
    )


def assetripper_dependency_scan_cache_key() -> str:
    return assetripper_exporter_cache_key()


def _assetripper_tool_root() -> Path:
    return Path(__file__).with_name("tool")


class _AssetRipperOutputObserver(ProcessOutputObserverPort):
    def __init__(self, callback: Callable[[AssetRipperProcessEvent], None]) -> None:
        self._callback = callback

    def on_output(self, output: ProcessOutputLine) -> None:
        if output.stream != "stdout":
            return
        event = parse_assetripper_event(output.text)
        if event is not None:
            self._callback(event)


class AssetRipperExportError(RuntimeError):
    def __init__(self, message: str, *, kind: str | None = None) -> None:
        super().__init__(message)
        self.kind = kind


class AssetRipperOutOfMemoryError(AssetRipperExportError):
    pass


class AssetRipperToolError(AssetRipperExportError):
    """AssetRipper source, build, or process protocol is unavailable."""


class _ExportedFilePayload(TypedDict):
    path: str
    size: int
    mtime_ns: int


class _ExportResultPayload(TypedDict):
    succeeded: bool
    error: str | None
    files: list[_ExportedFilePayload]
    requested_target_ids: list[str]
    resolved_target_ids: list[str]
    exported_target_ids: list[str]
    assets: list[AssetRipperExportedAsset]
    failures: list[AssetRipperCollectionFailure]
    failure_kind: str | None


@dataclass(frozen=True, slots=True)
class AssetRipperExportedFile:
    path: str
    size: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class AssetRipperExportedAsset:
    stable_id: str
    asset_type: str
    readable_name: str
    collection: str
    normalized_collection: str
    path_id: int
    class_id: int
    source_target_ids: tuple[str, ...]
    files: tuple[AssetRipperExportedFile, ...]


@dataclass(frozen=True, slots=True)
class AssetRipperCollectionFailure:
    stable_id: str
    source_target_ids: tuple[str, ...]
    error: str


@dataclass(frozen=True, slots=True)
class AssetRipperExportInput:
    path: Path
    node_id: str
    target: bool


@dataclass(frozen=True, slots=True)
class AssetRipperExportGroup:
    group_id: str
    inputs: tuple[AssetRipperExportInput, ...]


@dataclass(frozen=True, slots=True)
class AssetRipperExportResult:
    files: tuple[AssetRipperExportedFile, ...]
    requested_target_ids: tuple[str, ...] = ()
    resolved_target_ids: tuple[str, ...] = ()
    exported_target_ids: tuple[str, ...] = ()
    assets: tuple[AssetRipperExportedAsset, ...] = ()
    failures: tuple[AssetRipperCollectionFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class AssetRipperRuntimeMetadata:
    game_main_config: bytes
    bundle_version: str


@dataclass(frozen=True, slots=True)
class _AssetRipperToolBuildSpec:
    cache_directory: str
    project_parts: tuple[str, ...]
    assembly_name: str
    display_name: str
    cache_key_factory: Callable[[], str]


_EXPORTER_BUILD_SPEC = _AssetRipperToolBuildSpec(
    cache_directory="exporter",
    project_parts=("AssetRipperExporter.csproj",),
    assembly_name="AssetRipperExporter.dll",
    display_name="AssetRipper exporter",
    cache_key_factory=assetripper_exporter_cache_key,
)

_RUNTIME_INSPECTOR_BUILD_SPEC = _AssetRipperToolBuildSpec(
    cache_directory="runtime-inspector",
    project_parts=("runtime_inspector", "AssetRipperRuntimeInspector.csproj"),
    assembly_name="AssetRipperRuntimeInspector.dll",
    display_name="AssetRipper runtime inspector",
    cache_key_factory=assetripper_runtime_inspector_cache_key,
)


class _AssetRipperTool:
    build_spec = _EXPORTER_BUILD_SPEC

    def __init__(
        self,
        source_resolver: AssetRipperSourceResolver,
        process_runner: ProcessRunnerPort,
        *,
        repository_root: Path | None = None,
        logger: LoggerPort | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self._source_resolver = source_resolver
        self._process_runner = process_runner
        self._repository_root = repository_root or Path(__file__).resolve().parents[5]
        self._logger = logger
        self._cancellation = cancellation or NeverCancelled()

    def prepare(self, context: ExecutionContext) -> None:
        source_root = self._source_resolver.resolve_patched(context)
        self._ensure_tool(context, source_root)

    def _run(
        self,
        context: ExecutionContext,
        inputs: list[Path],
        request: dict[str, object],
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
        request_inputs: list[object] | None = None,
        *,
        inputs_validated: bool = False,
    ) -> tuple[ProcessResult, dict[str, object]]:
        normalized_inputs = sorted(
            (
                path if inputs_validated else path.resolve(strict=True)
                for path in inputs
            ),
            key=lambda path: str(path).casefold(),
        )
        if not normalized_inputs:
            raise AssetRipperExportError("AssetRipper requires input files.")

        source_root = self._source_resolver.resolve_patched(context)
        tool_dll = self._ensure_tool(context, source_root)
        job_root = (
            Path(context.workspace.temp_state) / "assetripper" / f"job-{uuid4().hex}"
        )
        job_root.mkdir(parents=True)
        request_path = job_root / "request.json"
        result_path = job_root / "result.json"
        request["inputs"] = request_inputs or [str(path) for path in normalized_inputs]
        request["schema_version"] = 0
        write_json_atomic(
            request_path,
            request,
            indent=2,
            sort_keys=True,
        )
        try:
            command = ProcessCommand(
                ("dotnet", str(tool_dll), str(request_path), str(result_path)),
                cwd=job_root,
            )
            try:
                process_result = self._process_runner.run(
                    command,
                    output_observer=(
                        _AssetRipperOutputObserver(event_callback)
                        if event_callback is not None
                        else None
                    ),
                )
            except ProcessExecutionError as exc:
                process_result = ProcessResult(
                    command,
                    exc.returncode,
                    exc.stdout,
                    exc.stderr,
                )
            result = self._read_payload(result_path)
            return process_result, result
        finally:
            shutil.rmtree(job_root, ignore_errors=True)

    def _ensure_tool(self, context: ExecutionContext, source_root: Path) -> Path:
        cache_key = self.build_spec.cache_key_factory()
        build_root = self._tool_cache_root(context, self.build_spec, cache_key)
        tool_dll = build_root / self.build_spec.assembly_name
        if self._is_valid_tool_cache(build_root, cache_key):
            return tool_dll
        lock_name = hashlib.sha256(cache_key.encode()).hexdigest()[:20]
        with wait_for_interprocess_lock(
            context.workspace.locks / f"assetripper-build-{lock_name}.lock",
            operation=f"{self.build_spec.display_name} build",
            cancellation_check=self._cancellation.raise_if_cancelled,
        ):
            if self._is_valid_tool_cache(build_root, cache_key):
                return tool_dll
            staging = build_root.with_name(f".{build_root.name}.staging-{uuid4().hex}")
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True)
            project = (
                Path(__file__)
                .with_name("tool")
                .joinpath(*self.build_spec.project_parts)
            )
            if self._logger is not None:
                self._logger.info(f"Building {self.build_spec.display_name}...")
            try:
                result = self._process_runner.run(
                    ProcessCommand(
                        (
                            "dotnet",
                            "build",
                            "--disable-build-servers",
                            str(project),
                            "--configuration",
                            "Release",
                            "--output",
                            str(staging),
                            f"-p:AssetRipperSource={source_root}",
                        ),
                        cwd=self._repository_root,
                    )
                )
                staged_dll = staging / self.build_spec.assembly_name
                if not result.succeeded or not staged_dll.is_file():
                    raise AssetRipperToolError(
                        f"{self.build_spec.display_name} build failed: "
                        f"{self._process_error(result.stderr or result.stdout)}"
                    )
                stem = Path(self.build_spec.assembly_name).stem
                write_build_manifest(
                    staging,
                    cache_key,
                    required=(
                        self.build_spec.assembly_name,
                        f"{stem}.deps.json",
                        f"{stem}.runtimeconfig.json",
                    ),
                )
                if not self._is_valid_tool_cache(staging, cache_key):
                    raise AssetRipperToolError(
                        f"{self.build_spec.display_name} build produced incomplete "
                        "runtime artifacts."
                    )
                publish_staged_directory(staging, build_root)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        return tool_dll

    def _is_valid_tool_cache(self, build_root: Path, cache_key: str) -> bool:
        assembly = Path(self.build_spec.assembly_name)
        stem = assembly.stem
        return validate_build_manifest(
            build_root,
            cache_key,
            required=(
                self.build_spec.assembly_name,
                f"{stem}.deps.json",
                f"{stem}.runtimeconfig.json",
            ),
        )

    @staticmethod
    def _read_payload(path: Path) -> dict[str, object]:
        try:
            payload = json.loads(path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise AssetRipperToolError(
                "AssetRipper exporter did not produce a valid result."
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 0
            or not isinstance(payload.get("succeeded"), bool)
        ):
            raise AssetRipperToolError("AssetRipper result schema is invalid.")
        return payload

    @staticmethod
    def _read_export_result(payload: dict[str, object]) -> _ExportResultPayload:
        try:
            raw_files = cast(list[dict[str, object]], payload["files"])
            assets_payload = cast(list[object], payload.get("assets", []))
            failures_payload = cast(list[object], payload.get("failures", []))
            return {
                "succeeded": cast(bool, payload["succeeded"]),
                "error": cast(str | None, payload.get("error")),
                "files": [
                    {
                        "path": cast(str, item["path"]),
                        "size": cast(int, item["size"]),
                        "mtime_ns": cast(int, item["mtime_ns"]),
                    }
                    for item in raw_files
                ],
                "requested_target_ids": cast(
                    list[str], payload["requested_target_ids"]
                ),
                "resolved_target_ids": cast(list[str], payload["resolved_target_ids"]),
                "exported_target_ids": cast(list[str], payload["exported_target_ids"]),
                "assets": [
                    _AssetRipperTool._read_exported_asset(item)
                    for item in assets_payload
                ],
                "failures": [
                    _AssetRipperTool._read_collection_failure(item)
                    for item in failures_payload
                ],
                "failure_kind": cast(str | None, payload.get("failure_kind")),
            }
        except (KeyError, TypeError) as exc:
            raise AssetRipperToolError(
                "AssetRipper export result is incomplete."
            ) from exc

    @staticmethod
    def _read_exported_asset(payload: object) -> AssetRipperExportedAsset:
        if not isinstance(payload, dict):
            raise AssetRipperToolError("AssetRipper exported asset is invalid.")
        try:
            files = cast(list[dict[str, object]], payload["files"])
            return AssetRipperExportedAsset(
                cast(str, payload["stable_id"]),
                cast(str, payload["asset_type"]),
                cast(str, payload["readable_name"]),
                cast(str, payload["collection"]),
                cast(str, payload["normalized_collection"]),
                cast(int, payload["path_id"]),
                cast(int, payload["class_id"]),
                tuple(cast(list[str], payload["source_target_ids"])),
                tuple(
                    AssetRipperExportedFile(
                        cast(str, item["path"]),
                        cast(int, item["size"]),
                        cast(int, item["mtime_ns"]),
                    )
                    for item in files
                ),
            )
        except (KeyError, TypeError) as exc:
            raise AssetRipperToolError(
                "AssetRipper exported asset is incomplete."
            ) from exc

    @staticmethod
    def _read_collection_failure(payload: object) -> AssetRipperCollectionFailure:
        if not isinstance(payload, dict):
            raise AssetRipperToolError("AssetRipper collection failure is invalid.")
        try:
            return AssetRipperCollectionFailure(
                cast(str, payload["stable_id"]),
                tuple(cast(list[str], payload["source_target_ids"])),
                cast(str, payload["error"]),
            )
        except (KeyError, TypeError) as exc:
            raise AssetRipperToolError(
                "AssetRipper collection failure is incomplete."
            ) from exc

    @staticmethod
    def _process_error(value: str) -> str:
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        return lines[-1] if lines else "process exited without diagnostics"

    @staticmethod
    def _tool_cache_root(
        context: ExecutionContext,
        build_spec: _AssetRipperToolBuildSpec,
        cache_key: str,
    ) -> Path:
        return (
            context.workspace.tools_cache
            / "assetripper"
            / build_spec.cache_directory
            / hashlib.sha256(cache_key.encode()).hexdigest()[:20]
        )


class AssetRipperBatchExporter(_AssetRipperTool):
    def materialize_entries(
        self,
        context: ExecutionContext,
        entries: list[BundleEntryInput],
        destinations: dict[str, Path],
        *,
        concurrency: int,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> dict[str, int]:
        if not entries or set(destinations) != {entry.node_id for entry in entries}:
            raise ValueError("Bundle entry cache destinations do not match inputs.")
        request_inputs: list[object] = [
            {
                "path": str(entry.archive.path.resolve(strict=True)),
                "node_id": entry.node_id,
                "entry_path": entry.entry_path,
                "sha256": entry.sha256,
                "size": entry.size,
                "crc32": entry.crc32,
                "marker_identity": bundle_entry_cache_identity(entry),
                "destination": str(destinations[entry.node_id].resolve(strict=False)),
            }
            for entry in entries
        ]
        process_result, payload = self._run(
            context,
            [entry.archive.path for entry in entries],
            {
                "operation": "materialize_bundle_entries",
                "output_directory": str(
                    next(iter(destinations.values())).parents[2].resolve(strict=False)
                ),
                "concurrency": concurrency,
            },
            event_callback,
            request_inputs,
        )
        error = payload.get("error")
        if payload.get("succeeded") is not True or not process_result.succeeded:
            detail = (
                error
                if isinstance(error, str)
                else self._process_error(process_result.stderr)
            )
            raise AssetRipperExportError(
                f"AssetRipper entry cache materialization failed: {detail}"
            )
        items = payload.get("materialized_entries")
        if not isinstance(items, list):
            raise AssetRipperToolError(
                "AssetRipper entry cache result schema is invalid."
            )
        result: dict[str, int] = {}
        try:
            for raw_item in items:
                item = cast(dict[str, object], raw_item)
                node_id = cast(str, item["node_id"])
                destination = destinations[node_id]
                if node_id in result or Path(cast(str, item["path"])).resolve(
                    strict=False
                ) != destination.resolve(strict=False):
                    raise AssetRipperToolError(
                        "AssetRipper entry cache result does not match its request."
                    )
                result[node_id] = cast(int, item["bytes_written"])
        except (KeyError, TypeError) as exc:
            raise AssetRipperToolError(
                "AssetRipper entry cache result is incomplete."
            ) from exc
        if set(result) != set(destinations):
            raise AssetRipperToolError(
                "AssetRipper entry cache result does not cover every input."
            )
        return result

    def export(
        self,
        context: ExecutionContext,
        inputs: list[AssetRipperExportInput],
        output_directory: Path,
        *,
        concurrency: int = 1,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> AssetRipperExportResult:
        normalized_inputs = sorted(
            inputs,
            key=lambda item: str(item.path.resolve(strict=True)).casefold(),
        )
        request_inputs: list[object] = [
            {
                "path": str(item.path.resolve(strict=True)),
                "node_id": item.node_id,
                "target": item.target,
            }
            for item in normalized_inputs
        ]
        process_result, payload = self._run(
            context,
            [item.path for item in normalized_inputs],
            {
                "operation": "export_primary_content",
                "output_directory": str(output_directory.resolve(strict=False)),
                "concurrency": concurrency,
            },
            event_callback,
            request_inputs,
        )
        result = self._read_export_result(payload)
        if not process_result.succeeded or not result["succeeded"]:
            error = result.get("error") or self._process_error(process_result.stderr)
            failure_kind = result.get("failure_kind")
            if failure_kind == "out_of_memory" or "OutOfMemoryException" in str(error):
                raise AssetRipperOutOfMemoryError(
                    f"AssetRipper export failed: {error}",
                    kind="out_of_memory",
                )
            raise AssetRipperExportError(
                f"AssetRipper export failed: {error}",
                kind=failure_kind,
            )
        return AssetRipperExportResult(
            tuple(
                AssetRipperExportedFile(
                    item["path"],
                    item["size"],
                    item["mtime_ns"],
                )
                for item in result["files"]
            ),
            tuple(result["requested_target_ids"]),
            tuple(result["resolved_target_ids"]),
            tuple(result["exported_target_ids"]),
            tuple(result["assets"]),
            tuple(result["failures"]),
        )

    def export_grouped(
        self,
        context: ExecutionContext,
        groups: list[AssetRipperExportGroup],
        output_directory: Path,
        *,
        concurrency: int = 1,
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> AssetRipperExportResult:
        if not groups or any(not group.inputs for group in groups):
            raise ValueError("AssetRipper export groups must not be empty.")
        group_ids = [group.group_id for group in groups]
        if any(not value for value in group_ids) or len(set(group_ids)) != len(
            group_ids
        ):
            raise ValueError("AssetRipper export group IDs must be unique.")

        by_node_id: dict[str, AssetRipperExportInput] = {}
        normalized_groups: list[AssetRipperExportGroup] = []
        for group in groups:
            normalized_group_inputs: list[AssetRipperExportInput] = []
            for item in group.inputs:
                existing = by_node_id.get(item.node_id)
                if existing is None:
                    path = item.path.resolve(strict=True)
                    if not path.is_file():
                        raise FileNotFoundError(path)
                    normalized = AssetRipperExportInput(
                        path,
                        item.node_id,
                        item.target,
                    )
                    by_node_id[item.node_id] = normalized
                else:
                    if (
                        item.path != existing.path
                        and item.path.absolute() != existing.path
                    ):
                        raise ValueError(
                            "AssetRipper grouped input paths must be stable by node ID."
                        )
                    normalized = AssetRipperExportInput(
                        existing.path,
                        item.node_id,
                        item.target or existing.target,
                    )
                    by_node_id[item.node_id] = normalized
                normalized_group_inputs.append(normalized)
            normalized_groups.append(
                AssetRipperExportGroup(
                    group.group_id,
                    tuple(
                        sorted(
                            normalized_group_inputs,
                            key=lambda item: str(item.path).casefold(),
                        )
                    ),
                )
            )
        flattened = sorted(
            by_node_id.values(),
            key=lambda item: str(item.path).casefold(),
        )
        request_inputs: list[object] = [
            {
                "path": str(item.path),
                "node_id": item.node_id,
                "target": item.target,
            }
            for item in flattened
        ]
        process_result, payload = self._run(
            context,
            [item.path for item in flattened],
            {
                "operation": "export_primary_content",
                "output_directory": str(output_directory.resolve(strict=False)),
                "concurrency": concurrency,
                "groups": [
                    {
                        "group_id": group.group_id,
                        "inputs": [
                            {"node_id": item.node_id, "target": item.target}
                            for item in group.inputs
                        ],
                    }
                    for group in normalized_groups
                ],
            },
            event_callback,
            request_inputs,
            inputs_validated=True,
        )
        result = self._read_export_result(payload)
        if not process_result.succeeded or not result["succeeded"]:
            error = result.get("error") or self._process_error(process_result.stderr)
            failure_kind = result.get("failure_kind")
            if failure_kind == "out_of_memory" or "OutOfMemoryException" in str(error):
                raise AssetRipperOutOfMemoryError(
                    f"AssetRipper export failed: {error}",
                    kind="out_of_memory",
                )
            raise AssetRipperExportError(
                f"AssetRipper export failed: {error}",
                kind=failure_kind,
            )
        return AssetRipperExportResult(
            tuple(
                AssetRipperExportedFile(
                    item["path"],
                    item["size"],
                    item["mtime_ns"],
                )
                for item in result["files"]
            ),
            tuple(result["requested_target_ids"]),
            tuple(result["resolved_target_ids"]),
            tuple(result["exported_target_ids"]),
            tuple(result["assets"]),
            tuple(result["failures"]),
        )


class AssetRipperDependencyScanner(_AssetRipperTool):
    def scan(
        self,
        context: ExecutionContext,
        archives: list[BundleArchiveInput],
        event_callback: Callable[[AssetRipperProcessEvent], None] | None = None,
    ) -> tuple[BundleArchiveScan, ...]:
        ordered = sorted(
            archives,
            key=lambda item: str(item.path).casefold(),
        )
        process_result, payload = self._run(
            context,
            [item.path for item in ordered],
            {
                "operation": "scan_bundle_dependencies",
                "archive_ids": [item.archive_id for item in ordered],
            },
            event_callback,
        )
        error = payload.get("error")
        if payload.get("succeeded") is not True or not process_result.succeeded:
            detail = (
                error
                if isinstance(error, str)
                else self._process_error(process_result.stderr)
            )
            raise AssetRipperExportError(
                f"AssetRipper dependency scan failed: {detail}"
            )
        scans_payload = payload.get("scans")
        if not isinstance(scans_payload, list):
            raise AssetRipperExportError(
                "AssetRipper dependency scan result schema is invalid."
            )
        scans = tuple(self._read_archive_scan(item) for item in scans_payload)
        expected_ids = sorted(
            (item.archive_id for item in archives),
            key=str.casefold,
        )
        actual_ids = sorted((item.archive_id for item in scans), key=str.casefold)
        if len(set(actual_ids)) != len(actual_ids) or actual_ids != expected_ids:
            raise AssetRipperExportError(
                "AssetRipper dependency scan results do not match bundle inputs."
            )
        return scans

    @staticmethod
    def _read_archive_scan(payload: object) -> BundleArchiveScan:
        if not isinstance(payload, dict):
            raise AssetRipperExportError("AssetRipper archive scan result is invalid.")
        try:
            return BundleArchiveScan(
                archive_id=cast(str, payload["archive_id"]),
                entries=tuple(
                    AssetRipperDependencyScanner._read_entry_scan(item)
                    for item in cast(list[object], payload["entries"])
                ),
                error=cast(str | None, payload.get("error")),
            )
        except (KeyError, TypeError) as exc:
            raise AssetRipperExportError(
                "AssetRipper archive scan result is incomplete."
            ) from exc

    @staticmethod
    def _read_entry_scan(payload: object) -> BundleEntryScan:
        if not isinstance(payload, dict):
            raise AssetRipperExportError("AssetRipper bundle entry scan is invalid.")
        try:
            serialized_files = cast(
                list[dict[str, object]], payload["serialized_files"]
            )
            streamed_resources = cast(
                list[dict[str, object]], payload["streamed_resources"]
            )
            return BundleEntryScan(
                entry_path=cast(str, payload["entry_path"]),
                sha256=cast(str, payload["sha256"]),
                size=cast(int, payload["size"]),
                crc32=cast(int | None, payload.get("crc32")),
                serialized_files=tuple(
                    SerializedFileScan(
                        cast(str, item["logical_name"]),
                        tuple(cast(list[str], item["dependencies"])),
                    )
                    for item in serialized_files
                ),
                resource_files=tuple(cast(list[str], payload["resource_files"])),
                streamed_resources=tuple(
                    StreamedResourceScan(
                        cast(str, item["source_serialized_file"]),
                        cast(str, item["resource_path"]),
                        cast(str, item["asset_type"]),
                    )
                    for item in streamed_resources
                ),
                error=cast(str | None, payload.get("error")),
            )
        except (KeyError, TypeError) as exc:
            raise AssetRipperExportError(
                "AssetRipper bundle entry scan is incomplete."
            ) from exc


class AssetRipperRuntimeMetadataInspector(_AssetRipperTool):
    build_spec = _RUNTIME_INSPECTOR_BUILD_SPEC

    def inspect(
        self,
        context: ExecutionContext,
        data_root: Path,
    ) -> AssetRipperRuntimeMetadata:
        process_result, payload = self._run(
            context,
            [data_root],
            {"operation": "inspect_jp_runtime"},
        )
        succeeded = payload.get("succeeded")
        error = payload.get("error")
        if succeeded is not True or not process_result.succeeded:
            detail = (
                error
                if isinstance(error, str)
                else self._process_error(process_result.stderr)
            )
            raise AssetRipperExportError(
                f"AssetRipper runtime metadata inspection failed: {detail}"
            )
        encoded_config = payload.get("game_main_config_base64")
        bundle_version = payload.get("bundle_version")
        if not isinstance(encoded_config, str) or not encoded_config:
            raise AssetRipperExportError(
                "AssetRipper runtime metadata is missing GameMainConfig."
            )
        if not isinstance(bundle_version, str):
            raise AssetRipperExportError(
                "AssetRipper runtime metadata bundle version is invalid."
            )
        try:
            game_main_config = base64.b64decode(encoded_config, validate=True)
        except ValueError as exc:
            raise AssetRipperExportError(
                "AssetRipper runtime metadata GameMainConfig is invalid."
            ) from exc
        return AssetRipperRuntimeMetadata(game_main_config, bundle_version)
