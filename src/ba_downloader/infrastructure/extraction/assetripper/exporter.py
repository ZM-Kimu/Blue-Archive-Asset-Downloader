from __future__ import annotations

import base64
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from ba_downloader.domain.exceptions import ProcessExecutionError
from ba_downloader.domain.models.execution import ExecutionContext
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
    BundleEntryScan,
    SerializedFileScan,
    StreamedResourceScan,
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
from ba_downloader.infrastructure.files.atomic import write_json_atomic

ASSETRIPPER_EXPORTER_WRAPPER_VERSION = "7"
ASSETRIPPER_DEPENDENCY_SCANNER_VERSION = "1"


def assetripper_exporter_cache_key() -> str:
    return (
        f"{ASSETRIPPER_COMMIT}\n"
        f"overlay-version={ASSETRIPPER_OVERLAY_VERSION}\n"
        f"overlay-hash={AssetRipperSourceResolver.overlay_hash()}\n"
        f"wrapper-version={ASSETRIPPER_EXPORTER_WRAPPER_VERSION}"
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
    pass


class AssetRipperToolError(AssetRipperExportError):
    """AssetRipper source, build, or process protocol is unavailable."""


class _ExportedFilePayload(TypedDict):
    path: str
    size: int


class _ExportResultPayload(TypedDict):
    succeeded: bool
    error: str | None
    files: list[_ExportedFilePayload]
    requested_target_ids: list[str]
    resolved_target_ids: list[str]
    exported_target_ids: list[str]


@dataclass(frozen=True, slots=True)
class AssetRipperExportedFile:
    path: str
    size: int


@dataclass(frozen=True, slots=True)
class AssetRipperExportInput:
    path: Path
    node_id: str
    target: bool


@dataclass(frozen=True, slots=True)
class AssetRipperExportResult:
    files: tuple[AssetRipperExportedFile, ...]
    requested_target_ids: tuple[str, ...] = ()
    resolved_target_ids: tuple[str, ...] = ()
    exported_target_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AssetRipperRuntimeMetadata:
    game_main_config: bytes
    bundle_version: str


class _AssetRipperTool:
    def __init__(
        self,
        source_resolver: AssetRipperSourceResolver,
        process_runner: ProcessRunnerPort,
        *,
        repository_root: Path | None = None,
    ) -> None:
        self._source_resolver = source_resolver
        self._process_runner = process_runner
        self._repository_root = repository_root or Path(__file__).resolve().parents[5]

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
        exporter_dll = self._ensure_exporter(context, source_root)
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
                ("dotnet", str(exporter_dll), str(request_path), str(result_path)),
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

    def _ensure_exporter(self, context: ExecutionContext, source_root: Path) -> Path:
        build_root = self._tool_cache_root(context)
        exporter_dll = build_root / "AssetRipperExporter.dll"
        marker = build_root / "source-commit.txt"
        cache_key = assetripper_exporter_cache_key()
        if (
            exporter_dll.is_file()
            and marker.is_file()
            and marker.read_text(encoding="utf8").strip() == cache_key
        ):
            return exporter_dll

        shutil.rmtree(build_root, ignore_errors=True)
        build_root.mkdir(parents=True)
        project = Path(__file__).with_name("tool") / "AssetRipperExporter.csproj"
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
                    str(build_root),
                    f"-p:AssetRipperSource={source_root}",
                ),
                cwd=self._repository_root,
            )
        )
        if not result.succeeded or not exporter_dll.is_file():
            raise AssetRipperToolError(
                "AssetRipper exporter build failed: "
                f"{self._process_error(result.stderr or result.stdout)}"
            )
        marker.write_text(f"{cache_key}\n", encoding="ascii")
        return exporter_dll

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
            normalized_files.append({"path": item["path"], "size": item["size"]})
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
        return {
            "succeeded": bool(payload["succeeded"]),
            "error": error,
            "files": normalized_files,
            "requested_target_ids": coverage["requested_target_ids"],
            "resolved_target_ids": coverage["resolved_target_ids"],
            "exported_target_ids": coverage["exported_target_ids"],
        }

    @staticmethod
    def _process_error(value: str) -> str:
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        return lines[-1] if lines else "process exited without diagnostics"

    @staticmethod
    def _tool_cache_root(context: ExecutionContext) -> Path:
        return context.workspace.tools_cache / "assetripper" / "exporter"


class AssetRipperBatchExporter(_AssetRipperTool):
    def prepare(self, context: ExecutionContext) -> None:
        source_root = self._source_resolver.resolve_patched(context)
        self._ensure_exporter(context, source_root)

    def export(
        self,
        context: ExecutionContext,
        inputs: list[AssetRipperExportInput],
        output_directory: Path,
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
            },
            event_callback,
            request_inputs,
        )
        result = self._read_export_result(payload)
        if not process_result.succeeded or not result["succeeded"]:
            error = result.get("error") or self._process_error(process_result.stderr)
            raise AssetRipperExportError(f"AssetRipper export failed: {error}")
        if not result["files"]:
            raise AssetRipperExportError(
                "AssetRipper export failed: no files were exported."
            )
        return AssetRipperExportResult(
            tuple(
                AssetRipperExportedFile(item["path"], item["size"])
                for item in result["files"]
            ),
            tuple(result["requested_target_ids"]),
            tuple(result["resolved_target_ids"]),
            tuple(result["exported_target_ids"]),
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
        sha256 = payload.get("sha256")
        entries = payload.get("entries")
        error = payload.get("error")
        if (
            not isinstance(archive_id, str)
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
            or not isinstance(entries, list)
            or (error is not None and not isinstance(error, str))
        ):
            raise AssetRipperExportError(
                "AssetRipper archive scan result schema is invalid."
            )

        return BundleArchiveScan(
            archive_id=archive_id,
            sha256=sha256,
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
            serialized_files=tuple(parsed_serialized),
            resource_files=tuple(resource_files),
            streamed_resources=tuple(parsed_streamed),
            error=error,
        )


class AssetRipperRuntimeMetadataInspector(_AssetRipperTool):
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
