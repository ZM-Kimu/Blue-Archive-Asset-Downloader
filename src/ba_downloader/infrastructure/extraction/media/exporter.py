from __future__ import annotations

import base64
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from ba_downloader.domain.exceptions import ExternalToolError, ProcessExecutionError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.process import (
    ProcessCommand,
    ProcessOutputLine,
    ProcessOutputObserverPort,
    ProcessResult,
    ProcessRunnerPort,
)
from ba_downloader.domain.ports.progress import (
    ProgressReporterFactoryPort,
    ProgressReporterPort,
)
from ba_downloader.infrastructure.extraction.errors import (
    ExtractionFailure,
    ExtractionFailureError,
)
from ba_downloader.infrastructure.extraction.media.source import (
    SHARPZIPLIB_COMMIT,
    SHARPZIPLIB_SOURCE_TREE_SHA256,
    SHARPZIPLIB_VERSION,
    SharpZipLibSourcePort,
)
from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    write_json_atomic,
)
from ba_downloader.infrastructure.files.checksum import calculate_sha256
from ba_downloader.infrastructure.progress import NullProgressReporterFactory
from ba_downloader.infrastructure.schema.crypto import zip_password

MEDIA_EXTRACTOR_SCHEMA_VERSION = 1
MEDIA_EXTRACTOR_WRAPPER_VERSION = "1"


class MediaArchiveExtractorError(ExternalToolError):
    """The media extraction tool build or protocol is unavailable."""


@dataclass(frozen=True, slots=True)
class _ArchiveRequest:
    path: Path
    output_name: str
    password: bytes


class _ArchiveResultPayload(TypedDict):
    archive_path: str
    output_name: str
    staging_path: str | None
    succeeded: bool
    error: str | None
    member_count: int
    output_bytes: int


class _MediaProgressObserver(ProcessOutputObserverPort):
    def __init__(self, progress: ProgressReporterPort) -> None:
        self._progress = progress

    def on_output(self, output: ProcessOutputLine) -> None:
        if output.stream != "stdout":
            return
        try:
            payload = json.loads(output.text)
        except ValueError:
            return
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != MEDIA_EXTRACTOR_SCHEMA_VERSION
            or payload.get("kind") != "progress"
        ):
            return
        completed_archives = _event_count(payload, "completed_archives")
        total_archives = _event_count(payload, "total_archives")
        completed_members = _event_count(payload, "completed_members")
        total_members = _event_count(payload, "total_members")
        if (
            completed_archives is None
            or total_archives is None
            or completed_members is None
            or total_members is None
        ):
            return
        self._progress.set_total(total_archives)
        self._progress.set_completed(min(completed_archives, total_archives))
        self._progress.set_status(f"{completed_archives}/{total_archives} archives")
        self._progress.set_secondary_status(
            f"{completed_members}/{total_members} members"
        )


class MediaArchiveExtractor:
    def __init__(
        self,
        process_runner: ProcessRunnerPort,
        logger: LoggerPort,
        *,
        source_resolver: SharpZipLibSourcePort,
        progress_factory: ProgressReporterFactoryPort | None = None,
        repository_root: Path | None = None,
    ) -> None:
        self._process_runner = process_runner
        self._logger = logger
        self._source_resolver = source_resolver
        self._progress_factory = progress_factory or NullProgressReporterFactory()
        self._repository_root = repository_root or Path(__file__).resolve().parents[5]

    def prepare(self, context: ExecutionContext) -> Path:
        return self._ensure_tool(context)

    def extract(
        self,
        context: ExecutionContext,
        archives: list[Path],
        *,
        concurrency: int,
    ) -> None:
        requests = self._build_archive_requests(archives)
        if not requests:
            return

        tool_dll = self._ensure_tool(context)
        job_root = (
            context.workspace.temp_state / "media-extractor" / f"job-{uuid4().hex}"
        )
        staging_root = job_root / "staging"
        request_path = job_root / "request.json"
        result_path = job_root / "result.json"
        staging_root.mkdir(parents=True)
        write_json_atomic(
            request_path,
            {
                "schema_version": MEDIA_EXTRACTOR_SCHEMA_VERSION,
                "concurrency": max(concurrency, 1),
                "staging_root": str(staging_root.resolve(strict=True)),
                "archives": [
                    {
                        "archive_path": str(item.path),
                        "output_name": item.output_name,
                        "password_base64": base64.b64encode(item.password).decode(
                            "ascii"
                        ),
                    }
                    for item in requests
                ],
            },
            indent=2,
            sort_keys=True,
        )
        try:
            command = ProcessCommand(
                ("dotnet", str(tool_dll), str(request_path), str(result_path)),
                cwd=job_root,
            )
            with self._progress_factory.create(
                len(requests),
                "Extracting media...",
                extract_mode=True,
            ) as progress:
                observer = _MediaProgressObserver(progress)
                process_result = self._run_tool(command, observer)
            payload = self._read_result(result_path, process_result)
            try:
                results = self._validate_archive_results(
                    payload,
                    requests,
                    staging_root,
                )
            except OSError as exc:
                raise MediaArchiveExtractorError(
                    "Media archive extractor returned missing or unsafe staging data."
                ) from exc
            self._publish_results(context, requests, results)
        finally:
            shutil.rmtree(job_root, ignore_errors=True)

    def _ensure_tool(self, context: ExecutionContext) -> Path:
        fingerprint = media_extractor_cache_fingerprint()
        cache_root = context.workspace.tools_cache / "media-extractor" / fingerprint
        tool_dll = cache_root / "MediaArchiveExtractor.dll"
        dependency = cache_root / "ICSharpCode.SharpZipLib.dll"
        runtime_config = cache_root / "MediaArchiveExtractor.runtimeconfig.json"
        dependency_manifest = cache_root / "MediaArchiveExtractor.deps.json"
        marker = cache_root / "fingerprint.txt"
        if (
            tool_dll.is_file()
            and dependency.is_file()
            and runtime_config.is_file()
            and dependency_manifest.is_file()
            and marker.is_file()
            and marker.read_text(encoding="ascii").strip() == fingerprint
        ):
            return tool_dll

        cache_root.parent.mkdir(parents=True, exist_ok=True)
        build_root = cache_root.with_name(f".{fingerprint}.staging-{uuid4().hex}")
        artifacts_root = cache_root.with_name(f".{fingerprint}.artifacts-{uuid4().hex}")
        source_root = self._source_resolver.resolve(context)
        project = _media_tool_root() / "MediaArchiveExtractor.csproj"
        try:
            build_root.mkdir()
            self._logger.info("Building media archive extractor...")
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
                        "--artifacts-path",
                        str(artifacts_root),
                        f"-p:SharpZipLibSource={source_root}",
                        "-p:RestoreSources=",
                    ),
                    cwd=self._repository_root,
                )
            )
            if (
                not result.succeeded
                or not (build_root / tool_dll.name).is_file()
                or not (build_root / dependency.name).is_file()
                or not (build_root / runtime_config.name).is_file()
                or not (build_root / dependency_manifest.name).is_file()
            ):
                raise MediaArchiveExtractorError(
                    "Media archive extractor build failed: "
                    f"{_process_error(result.stderr or result.stdout)}"
                )
            (build_root / marker.name).write_text(f"{fingerprint}\n", encoding="ascii")
            publish_staged_directory(build_root, cache_root)
        except ProcessExecutionError as exc:
            raise MediaArchiveExtractorError(
                "Media archive extractor build failed: "
                f"{_process_error(exc.stderr or exc.stdout)}"
            ) from exc
        except OSError as exc:
            raise MediaArchiveExtractorError(
                "Media archive extractor requires the .NET 10 SDK and a writable "
                f"tool cache: {exc}"
            ) from exc
        finally:
            shutil.rmtree(build_root, ignore_errors=True)
            shutil.rmtree(artifacts_root, ignore_errors=True)
        return tool_dll

    @staticmethod
    def _build_archive_requests(archives: list[Path]) -> list[_ArchiveRequest]:
        requests: list[_ArchiveRequest] = []
        output_names: dict[str, Path] = {}
        for archive in archives:
            normalized = archive.resolve(strict=True)
            output_name = normalized.stem
            output_key = output_name.casefold()
            previous = output_names.get(output_key)
            if previous is not None:
                raise MediaArchiveExtractorError(
                    "Media archive output name is ambiguous for "
                    f"'{previous.name}' and '{normalized.name}'."
                )
            output_names[output_key] = normalized
            requests.append(
                _ArchiveRequest(
                    normalized,
                    output_name,
                    zip_password(normalized.name.lower()),
                )
            )
        return requests

    def _run_tool(
        self,
        command: ProcessCommand,
        observer: ProcessOutputObserverPort,
    ) -> ProcessResult:
        try:
            return self._process_runner.run(command, output_observer=observer)
        except ProcessExecutionError as exc:
            raise MediaArchiveExtractorError(
                "Media archive extractor process failed: "
                f"{_process_error(exc.stderr or exc.stdout)}"
            ) from exc
        except OSError as exc:
            raise MediaArchiveExtractorError(
                f"Media archive extractor could not be started: {exc}"
            ) from exc

    @staticmethod
    def _read_result(
        result_path: Path,
        process_result: ProcessResult,
    ) -> dict[str, object]:
        if not process_result.succeeded:
            raise MediaArchiveExtractorError(
                "Media archive extractor process failed: "
                f"{_process_error(process_result.stderr or process_result.stdout)}"
            )
        try:
            payload = json.loads(result_path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise MediaArchiveExtractorError(
                "Media archive extractor did not produce a valid result."
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != MEDIA_EXTRACTOR_SCHEMA_VERSION
            or payload.get("succeeded") is not True
            or not isinstance(payload.get("archives"), list)
        ):
            raise MediaArchiveExtractorError(
                "Media archive extractor result schema is invalid."
            )
        return payload

    @staticmethod
    def _validate_archive_results(
        payload: dict[str, object],
        requests: list[_ArchiveRequest],
        staging_root: Path,
    ) -> list[_ArchiveResultPayload]:
        raw_results = payload["archives"]
        assert isinstance(raw_results, list)
        if len(raw_results) != len(requests):
            raise MediaArchiveExtractorError(
                "Media archive extractor returned incomplete archive results."
            )
        results: list[_ArchiveResultPayload] = []
        staging_root_resolved = staging_root.resolve(strict=True)
        for index, (raw_result, request) in enumerate(
            zip(raw_results, requests, strict=True)
        ):
            if not isinstance(raw_result, dict):
                raise MediaArchiveExtractorError(
                    "Media archive extractor archive result is invalid."
                )
            succeeded = raw_result.get("succeeded")
            error = raw_result.get("error")
            staging_path = raw_result.get("staging_path")
            member_count = raw_result.get("member_count")
            output_bytes = raw_result.get("output_bytes")
            if (
                raw_result.get("archive_path") != str(request.path)
                or raw_result.get("output_name") != request.output_name
                or not isinstance(succeeded, bool)
                or (error is not None and not isinstance(error, str))
                or not isinstance(member_count, int)
                or isinstance(member_count, bool)
                or member_count < 0
                or not isinstance(output_bytes, int)
                or isinstance(output_bytes, bool)
                or output_bytes < 0
            ):
                raise MediaArchiveExtractorError(
                    "Media archive extractor archive result schema is invalid."
                )
            if succeeded:
                if not isinstance(staging_path, str):
                    raise MediaArchiveExtractorError(
                        "Successful media extraction has no staging directory."
                    )
                candidate = Path(staging_path).resolve(strict=True)
                expected = (staging_root_resolved / f"archive-{index:06d}").resolve(
                    strict=True
                )
                if (
                    candidate != expected
                    or not candidate.is_relative_to(staging_root_resolved)
                    or not candidate.is_dir()
                ):
                    raise MediaArchiveExtractorError(
                        "Media archive extractor returned an unsafe staging path."
                    )
            elif staging_path is not None:
                raise MediaArchiveExtractorError(
                    "Failed media extraction returned a staging directory."
                )
            results.append(
                {
                    "archive_path": str(request.path),
                    "output_name": request.output_name,
                    "staging_path": staging_path,
                    "succeeded": succeeded,
                    "error": error,
                    "member_count": member_count,
                    "output_bytes": output_bytes,
                }
            )
        return results

    def _publish_results(
        self,
        context: ExecutionContext,
        requests: list[_ArchiveRequest],
        results: list[_ArchiveResultPayload],
    ) -> None:
        failures: list[ExtractionFailure] = []
        output_root = context.workspace.extracted_media
        for request, result in zip(requests, results, strict=True):
            if not result["succeeded"]:
                error = RuntimeError(result["error"] or "archive extraction failed")
                failures.append(ExtractionFailure(str(request.path), error))
                self._logger.error(f"Failed to extract {request.path}: {error}")
                continue
            staging_path = result["staging_path"]
            assert staging_path is not None
            try:
                publish_staged_directory(
                    Path(staging_path),
                    output_root / request.output_name,
                )
            except OSError as exc:
                failures.append(ExtractionFailure(str(request.path), exc))
                self._logger.error(f"Failed to publish {request.path}: {exc}")
        if failures:
            raise ExtractionFailureError("media extraction", failures)


def media_extractor_cache_fingerprint() -> str:
    digest = hashlib.sha256()
    digest.update(f"schema={MEDIA_EXTRACTOR_SCHEMA_VERSION}\n".encode("ascii"))
    digest.update(f"wrapper={MEDIA_EXTRACTOR_WRAPPER_VERSION}\n".encode("ascii"))
    digest.update(f"sharpziplib={SHARPZIPLIB_VERSION}\n".encode("ascii"))
    digest.update(f"sharpziplib-commit={SHARPZIPLIB_COMMIT}\n".encode("ascii"))
    digest.update(
        f"sharpziplib-source={SHARPZIPLIB_SOURCE_TREE_SHA256}\n".encode("ascii")
    )
    for source in sorted(_media_tool_root().glob("*"), key=lambda path: path.name):
        if source.is_file() and source.suffix in {".cs", ".csproj"}:
            digest.update(source.name.encode("utf8"))
            digest.update(calculate_sha256(source).encode("ascii"))
    return digest.hexdigest()


def _media_tool_root() -> Path:
    return Path(__file__).with_name("tool")


def _process_error(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return lines[-1] if lines else "process exited without diagnostics"


def _event_count(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
