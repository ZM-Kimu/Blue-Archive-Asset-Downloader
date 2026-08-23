from __future__ import annotations

import base64
import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict
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
    ASSETRIPPER_OVERLAY_VERSION,
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    write_json_atomic,
)
from ba_downloader.infrastructure.files.lock import wait_for_interprocess_lock

ASSETRIPPER_EXPORTER_WRAPPER_VERSION = "15"
ASSETRIPPER_RUNTIME_INSPECTOR_WRAPPER_VERSION = "1"
ASSETRIPPER_DEPENDENCY_SCANNER_VERSION = "2"


def assetripper_exporter_cache_key() -> str:
    return (
        f"{ASSETRIPPER_COMMIT}\n"
        f"overlay-version={ASSETRIPPER_OVERLAY_VERSION}\n"
        f"overlay-hash={AssetRipperSourceResolver.overlay_hash()}\n"
        f"wrapper-version={ASSETRIPPER_EXPORTER_WRAPPER_VERSION}"
    )


def assetripper_runtime_inspector_cache_key() -> str:
    return (
        f"{ASSETRIPPER_COMMIT}\n"
        f"overlay-version={ASSETRIPPER_OVERLAY_VERSION}\n"
        f"overlay-hash={AssetRipperSourceResolver.overlay_hash()}\n"
        f"runtime-inspector-version={ASSETRIPPER_RUNTIME_INSPECTOR_WRAPPER_VERSION}"
    )


def assetripper_dependency_scan_cache_key() -> str:
    return (
        f"{ASSETRIPPER_COMMIT}\n"
        f"scanner-version={ASSETRIPPER_DEPENDENCY_SCANNER_VERSION}"
    )


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
    sha256: str


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
    sha256: str


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
    ) -> tuple[ProcessResult, dict[str, object]]:
        normalized_inputs = sorted(
            (path.resolve(strict=True) for path in inputs),
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
                write_json_atomic(
                    staging / "build.json",
                    {"cache_key": cache_key},
                    sort_keys=True,
                )
                (staging / "source-commit.txt").write_text(
                    f"{cache_key}\n", encoding="ascii"
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
        required = (
            build_root / assembly,
            build_root / f"{stem}.deps.json",
            build_root / f"{stem}.runtimeconfig.json",
        )
        marker = build_root / "source-commit.txt"
        try:
            marker_value = marker.read_text(encoding="utf8").strip()
            dependencies = json.loads(required[1].read_text(encoding="utf8"))
            runtime_config = json.loads(required[2].read_text(encoding="utf8"))
        except OSError:
            return False
        except ValueError:
            return False
        return (
            marker_value == cache_key
            and all(path.is_file() and path.stat().st_size > 0 for path in required)
            and isinstance(dependencies, dict)
            and isinstance(runtime_config, dict)
        )

    @staticmethod
    def _read_payload(path: Path) -> dict[str, object]:
        try:
            payload = json.loads(path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise AssetRipperToolError(
                "AssetRipper exporter did not produce a valid result."
            ) from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("succeeded"), bool
        ):
            raise AssetRipperToolError("AssetRipper result schema is invalid.")
        return payload

    @staticmethod
    def _read_export_result(payload: dict[str, object]) -> _ExportResultPayload:
        files = payload.get("files")
        if not isinstance(files, list):
            raise AssetRipperToolError("AssetRipper result files are invalid.")
        normalized_files: list[_ExportedFilePayload] = []
        for item in files:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("path"), str)
                or not isinstance(item.get("size"), int)
            ):
                raise AssetRipperToolError("AssetRipper result file is invalid.")
            mtime_ns = item.get("mtime_ns")
            sha256 = item.get("sha256")
            if (
                not isinstance(mtime_ns, int)
                or isinstance(mtime_ns, bool)
                or mtime_ns < 0
                or not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdef" for character in sha256)
            ):
                raise AssetRipperToolError("AssetRipper result file is invalid.")
            normalized_files.append(
                {
                    "path": item["path"],
                    "size": item["size"],
                    "mtime_ns": mtime_ns,
                    "sha256": sha256,
                }
            )
        error = payload.get("error")
        if error is not None and not isinstance(error, str):
            raise AssetRipperToolError("AssetRipper result error is invalid.")
        coverage: dict[str, list[str]] = {}
        for key in (
            "requested_target_ids",
            "resolved_target_ids",
            "exported_target_ids",
        ):
            value = payload.get(key)
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise AssetRipperToolError(
                    "AssetRipper result target coverage is invalid."
                )
            coverage[key] = value
        assets_payload = payload.get("assets")
        if assets_payload is None and payload.get("succeeded") is False:
            assets_payload = []
        if not isinstance(assets_payload, list):
            raise AssetRipperToolError("AssetRipper result assets are invalid.")
        assets = [
            _AssetRipperTool._read_exported_asset(item) for item in assets_payload
        ]
        failures_payload = payload.get("failures")
        if failures_payload is None and payload.get("succeeded") is False:
            failures_payload = []
        if not isinstance(failures_payload, list):
            raise AssetRipperToolError("AssetRipper result failures are invalid.")
        failures = [
            _AssetRipperTool._read_collection_failure(item) for item in failures_payload
        ]
        failure_kind = payload.get("failure_kind")
        if failure_kind is not None and not isinstance(failure_kind, str):
            raise AssetRipperToolError("AssetRipper failure kind is invalid.")
        return {
            "succeeded": bool(payload["succeeded"]),
            "error": error,
            "files": normalized_files,
            "requested_target_ids": coverage["requested_target_ids"],
            "resolved_target_ids": coverage["resolved_target_ids"],
            "exported_target_ids": coverage["exported_target_ids"],
            "assets": assets,
            "failures": failures,
            "failure_kind": failure_kind,
        }

    @staticmethod
    def _read_exported_asset(payload: object) -> AssetRipperExportedAsset:
        if not isinstance(payload, dict):
            raise AssetRipperToolError("AssetRipper exported asset is invalid.")
        stable_id = payload.get("stable_id")
        asset_type = payload.get("asset_type")
        readable_name = payload.get("readable_name")
        collection = payload.get("collection")
        normalized_collection = payload.get("normalized_collection")
        path_id = payload.get("path_id")
        class_id = payload.get("class_id")
        source_ids = payload.get("source_target_ids")
        files = payload.get("files")
        if (
            not isinstance(stable_id, str)
            or len(stable_id) != 20
            or any(character not in "0123456789abcdef" for character in stable_id)
            or not isinstance(asset_type, str)
            or not asset_type
            or not isinstance(readable_name, str)
            or not readable_name
            or not isinstance(collection, str)
            or not isinstance(normalized_collection, str)
            or not normalized_collection
            or not isinstance(path_id, int)
            or isinstance(path_id, bool)
            or not isinstance(class_id, int)
            or isinstance(class_id, bool)
            or not isinstance(source_ids, list)
            or not all(isinstance(item, str) and item for item in source_ids)
            or not isinstance(files, list)
            or not files
        ):
            raise AssetRipperToolError("AssetRipper exported asset is invalid.")
        parsed_files: list[AssetRipperExportedFile] = []
        for item in files:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("path"), str)
                or not item["path"]
                or not isinstance(item.get("size"), int)
                or isinstance(item["size"], bool)
                or item["size"] < 0
                or not isinstance(item.get("mtime_ns"), int)
                or isinstance(item["mtime_ns"], bool)
                or item["mtime_ns"] < 0
                or not isinstance(item.get("sha256"), str)
                or len(item["sha256"]) != 64
                or any(
                    character not in "0123456789abcdef" for character in item["sha256"]
                )
            ):
                raise AssetRipperToolError(
                    "AssetRipper exported asset file is invalid."
                )
            parsed_files.append(
                AssetRipperExportedFile(
                    item["path"],
                    item["size"],
                    item["mtime_ns"],
                    item["sha256"],
                )
            )
        return AssetRipperExportedAsset(
            stable_id,
            asset_type,
            readable_name,
            collection,
            normalized_collection,
            path_id,
            class_id,
            tuple(source_ids),
            tuple(parsed_files),
        )

    @staticmethod
    def _read_collection_failure(payload: object) -> AssetRipperCollectionFailure:
        if not isinstance(payload, dict):
            raise AssetRipperToolError("AssetRipper collection failure is invalid.")
        stable_id = payload.get("stable_id")
        source_ids = payload.get("source_target_ids")
        error = payload.get("error")
        if (
            not isinstance(stable_id, str)
            or len(stable_id) != 20
            or any(character not in "0123456789abcdef" for character in stable_id)
            or not isinstance(source_ids, list)
            or not all(isinstance(item, str) and item for item in source_ids)
            or not isinstance(error, str)
            or not error
        ):
            raise AssetRipperToolError("AssetRipper collection failure is invalid.")
        return AssetRipperCollectionFailure(stable_id, tuple(source_ids), error)

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
        for item in items:
            if not isinstance(item, dict):
                raise AssetRipperToolError("AssetRipper entry cache result is invalid.")
            node_id = item.get("node_id")
            path = item.get("path")
            written = item.get("bytes_written")
            if (
                not isinstance(node_id, str)
                or node_id not in destinations
                or node_id in result
                or not isinstance(path, str)
                or Path(path).resolve(strict=False)
                != destinations[node_id].resolve(strict=False)
                or not isinstance(written, int)
                or isinstance(written, bool)
                or written < 0
            ):
                raise AssetRipperToolError("AssetRipper entry cache result is invalid.")
            result[node_id] = written
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
                    item["sha256"],
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

        normalized_groups = [
            AssetRipperExportGroup(
                group.group_id,
                tuple(
                    sorted(
                        group.inputs,
                        key=lambda item: str(item.path.resolve(strict=True)).casefold(),
                    )
                ),
            )
            for group in groups
        ]
        by_node_id: dict[str, AssetRipperExportInput] = {}
        for group in normalized_groups:
            for item in group.inputs:
                existing = by_node_id.get(item.node_id)
                if existing is not None and existing.path.resolve(
                    strict=True
                ) != item.path.resolve(strict=True):
                    raise ValueError(
                        "AssetRipper grouped input paths must be stable by node ID."
                    )
                by_node_id[item.node_id] = AssetRipperExportInput(
                    item.path,
                    item.node_id,
                    item.target or (existing.target if existing is not None else False),
                )
        flattened = sorted(
            by_node_id.values(),
            key=lambda item: str(item.path.resolve(strict=True)).casefold(),
        )
        request_inputs: list[object] = [
            {
                "path": str(item.path.resolve(strict=True)),
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
                    item["sha256"],
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
        archive_id = payload.get("archive_id")
        entries = payload.get("entries")
        error = payload.get("error")
        if (
            not isinstance(archive_id, str)
            or not isinstance(entries, list)
            or (error is not None and not isinstance(error, str))
        ):
            raise AssetRipperExportError(
                "AssetRipper archive scan result schema is invalid."
            )

        return BundleArchiveScan(
            archive_id=archive_id,
            entries=tuple(
                AssetRipperDependencyScanner._read_entry_scan(item) for item in entries
            ),
            error=error,
        )

    @staticmethod
    def _read_entry_scan(payload: object) -> BundleEntryScan:
        if not isinstance(payload, dict):
            raise AssetRipperExportError("AssetRipper bundle entry scan is invalid.")
        entry_path = payload.get("entry_path")
        sha256 = payload.get("sha256")
        size = payload.get("size")
        crc32 = payload.get("crc32")
        serialized_files = payload.get("serialized_files")
        resource_files = payload.get("resource_files")
        streamed_resources = payload.get("streamed_resources")
        error = payload.get("error")
        if (
            not isinstance(entry_path, str)
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or (
                crc32 is not None
                and (
                    not isinstance(crc32, int)
                    or isinstance(crc32, bool)
                    or not 0 <= crc32 <= 0xFFFFFFFF
                )
            )
            or not isinstance(serialized_files, list)
            or not isinstance(resource_files, list)
            or not all(isinstance(item, str) for item in resource_files)
            or not isinstance(streamed_resources, list)
            or (error is not None and not isinstance(error, str))
        ):
            raise AssetRipperExportError(
                "AssetRipper bundle entry scan schema is invalid."
            )

        parsed_serialized: list[SerializedFileScan] = []
        for item in serialized_files:
            if not isinstance(item, dict):
                raise AssetRipperExportError(
                    "AssetRipper serialized file scan is invalid."
                )
            logical_name = item.get("logical_name")
            dependencies = item.get("dependencies")
            if (
                not isinstance(logical_name, str)
                or not isinstance(dependencies, list)
                or not all(isinstance(value, str) for value in dependencies)
            ):
                raise AssetRipperExportError(
                    "AssetRipper serialized file scan is invalid."
                )
            parsed_serialized.append(
                SerializedFileScan(logical_name, tuple(dependencies))
            )

        parsed_streamed: list[StreamedResourceScan] = []
        for item in streamed_resources:
            if not isinstance(item, dict):
                raise AssetRipperExportError(
                    "AssetRipper streamed resource scan is invalid."
                )
            source = item.get("source_serialized_file")
            resource_path = item.get("resource_path")
            asset_type = item.get("asset_type")
            if (
                not isinstance(source, str)
                or not isinstance(resource_path, str)
                or not isinstance(asset_type, str)
            ):
                raise AssetRipperExportError(
                    "AssetRipper streamed resource scan is invalid."
                )
            parsed_streamed.append(
                StreamedResourceScan(source, resource_path, asset_type)
            )

        return BundleEntryScan(
            entry_path=entry_path,
            sha256=sha256,
            size=size,
            crc32=crc32,
            serialized_files=tuple(parsed_serialized),
            resource_files=tuple(resource_files),
            streamed_resources=tuple(parsed_streamed),
            error=error,
        )


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
