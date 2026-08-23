from __future__ import annotations

import json
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Self

import pytest

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.process import (
    ProcessCommand,
    ProcessOutputLine,
    ProcessOutputObserverPort,
    ProcessResult,
)
from ba_downloader.infrastructure.extraction.errors import ExtractionFailureError
from ba_downloader.infrastructure.extraction.media import exporter as exporter_module
from ba_downloader.infrastructure.extraction.media.exporter import (
    MEDIA_EXTRACTOR_SCHEMA_VERSION,
    MediaArchiveExtractor,
    MediaArchiveExtractorError,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from support.fixtures import build_execution_context


def _build_context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="jp",
        version="1.0.0",
        max_retries=1,
    )


class FakeProcessRunner:
    def __init__(self) -> None:
        self.build_calls = 0
        self.extract_calls = 0
        self.requests: list[dict[str, Any]] = []
        self.result_payloads: list[dict[str, object]] = []
        self.failures: set[str] = set()
        self.malicious_staging_path: Path | None = None
        self.cancel_extraction = False
        self.job_roots: list[Path] = []

    def run(
        self,
        command: ProcessCommand,
        *,
        output_observer: ProcessOutputObserverPort | None = None,
    ) -> ProcessResult:
        if command.argv[1] == "build":
            self.build_calls += 1
            output = Path(command.argv[command.argv.index("--output") + 1])
            assert "-p:RestoreSources=" in command.argv
            assert any(
                argument.startswith("-p:SharpZipLibSource=")
                for argument in command.argv
            )
            output.mkdir(parents=True, exist_ok=True)
            (output / "MediaArchiveExtractor.dll").write_bytes(b"tool")
            (output / "ICSharpCode.SharpZipLib.dll").write_bytes(b"dependency")
            (output / "MediaArchiveExtractor.runtimeconfig.json").write_text(
                "{}", encoding="utf8"
            )
            (output / "MediaArchiveExtractor.deps.json").write_text(
                "{}", encoding="utf8"
            )
            return ProcessResult(command, 0, "", "")

        self.extract_calls += 1
        request_path = Path(command.argv[-2])
        result_path = Path(command.argv[-1])
        self.job_roots.append(request_path.parent)
        if self.cancel_extraction:
            raise OperationCancelledError("Media extraction cancelled by user.")
        request = json.loads(request_path.read_text(encoding="utf8"))
        self.requests.append(request)
        results: list[dict[str, object]] = []
        archives = request["archives"]
        staging_root = Path(request["staging_root"])
        for index, archive in enumerate(archives):
            archive_path = Path(archive["archive_path"])
            if archive_path.name in self.failures:
                results.append(
                    {
                        "archive_path": str(archive_path),
                        "output_name": archive["output_name"],
                        "staging_path": None,
                        "succeeded": False,
                        "error": "invalid password or archive",
                        "member_count": 0,
                        "output_bytes": 0,
                    }
                )
                continue
            staging = staging_root / f"archive-{index:06d}"
            staging.mkdir()
            (staging / "member.bin").write_bytes(archive_path.name.encode("ascii"))
            results.append(
                {
                    "archive_path": str(archive_path),
                    "output_name": archive["output_name"],
                    "staging_path": str(self.malicious_staging_path or staging),
                    "succeeded": True,
                    "error": None,
                    "member_count": 1,
                    "output_bytes": len(archive_path.name),
                }
            )
        if output_observer is not None:
            output_observer.on_output(
                ProcessOutputLine(
                    "stdout",
                    json.dumps(
                        {
                            "schema_version": MEDIA_EXTRACTOR_SCHEMA_VERSION,
                            "kind": "progress",
                            "completed_archives": len(archives),
                            "total_archives": len(archives),
                            "completed_members": len(archives),
                            "total_members": len(archives),
                        }
                    ),
                )
            )
        result_payload: dict[str, object] = {
            "schema_version": MEDIA_EXTRACTOR_SCHEMA_VERSION,
            "succeeded": True,
            "archives": results,
        }
        self.result_payloads.append(result_payload)
        result_path.write_text(json.dumps(result_payload), encoding="utf8")
        return ProcessResult(command, 0, "", "")


class StaticSourceResolver:
    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root
        self.calls = 0

    def resolve(self, _context: ExecutionContext) -> Path:
        self.calls += 1
        return self.source_root


class RecordingProgress(AbstractContextManager["RecordingProgress"]):
    def __init__(self) -> None:
        self.total = 0
        self.completed = 0
        self.status = ""
        self.secondary_status = ""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def advance(self, amount: int = 1) -> None:
        self.completed += amount

    def set_total(self, total: int) -> None:
        self.total = total

    def set_description(self, description: str) -> None:
        _ = description

    def set_status(self, status: str) -> None:
        self.status = status

    def set_secondary_status(self, status: str) -> None:
        self.secondary_status = status

    def set_progress(
        self,
        completed: int,
        total: int,
        *,
        stage: str,
        unit: str,
        status: str = "",
        secondary_status: str = "",
    ) -> None:
        _ = (completed, total, stage, unit, status, secondary_status)

    def set_failed_status(self, status: str) -> None:
        _ = status

    def set_completed(self, completed: int) -> None:
        self.completed = completed

    def stop(self) -> None:
        return None


class RecordingProgressFactory:
    def __init__(self) -> None:
        self.progress = RecordingProgress()

    def create(
        self, total: int, description: str, **kwargs: object
    ) -> RecordingProgress:
        _ = (description, kwargs)
        self.progress.total = total
        return self.progress


def _write_archives(context: ExecutionContext, *names: str) -> list[Path]:
    context.workspace.raw_media.mkdir(parents=True, exist_ok=True)
    archives = []
    for name in names:
        archive = context.workspace.raw_media / name
        archive.write_bytes(b"archive")
        archives.append(archive)
    return archives


def test_batch_request_uses_one_process_and_structured_progress(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    archive_names = ["voice.zip", *(f"archive-{index:03d}.zip" for index in range(299))]
    archives = _write_archives(context, *archive_names)
    runner = FakeProcessRunner()
    progress_factory = RecordingProgressFactory()
    source_resolver = StaticSourceResolver(tmp_path)
    extractor = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=source_resolver,
        progress_factory=progress_factory,
    )

    extractor.extract(context, archives, concurrency=30)

    assert runner.build_calls == 1
    assert runner.extract_calls == 1
    assert source_resolver.calls == 1
    assert runner.requests[0]["concurrency"] == 30
    assert len(runner.requests[0]["archives"]) == 300
    assert all("password_base64" in item for item in runner.requests[0]["archives"])
    assert progress_factory.progress.completed == 300
    assert progress_factory.progress.secondary_status == "300/300 members"
    assert (
        context.workspace.extracted_media / "voice" / "member.bin"
    ).read_bytes() == b"voice.zip"
    assert "password" not in json.dumps(runner.result_payloads[0])


def test_consecutive_runs_extract_twice_but_build_once(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    archives = _write_archives(context, "voice.zip")
    runner = FakeProcessRunner()
    source_resolver = StaticSourceResolver(tmp_path)
    extractor = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=source_resolver,
    )

    extractor.extract(context, archives, concurrency=1)
    stale = context.workspace.extracted_media / "voice" / "stale.bin"
    stale.write_bytes(b"stale")
    extractor.extract(context, archives, concurrency=1)

    assert runner.build_calls == 1
    assert runner.extract_calls == 2
    assert source_resolver.calls == 1
    assert not stale.exists()
    assert all(not job_root.exists() for job_root in runner.job_roots)


def test_wrapper_version_change_uses_a_new_content_addressed_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    runner = FakeProcessRunner()
    extractor = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=StaticSourceResolver(tmp_path),
    )

    first = extractor.prepare(context)
    monkeypatch.setattr(exporter_module, "MEDIA_EXTRACTOR_WRAPPER_VERSION", "next")
    second = extractor.prepare(context)

    assert runner.build_calls == 2
    assert first.parent != second.parent


def test_incomplete_tool_cache_is_rebuilt_atomically(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    runner = FakeProcessRunner()
    extractor = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=StaticSourceResolver(tmp_path),
    )

    tool = extractor.prepare(context)
    (tool.parent / "ICSharpCode.SharpZipLib.dll").unlink()
    rebuilt = extractor.prepare(context)

    assert rebuilt == tool
    assert runner.build_calls == 2
    assert (tool.parent / "ICSharpCode.SharpZipLib.dll").is_file()


def test_archive_failure_preserves_old_output_and_publishes_successes(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    archives = _write_archives(context, "bad.zip", "good.zip")
    old_output = context.workspace.extracted_media / "bad"
    old_output.mkdir(parents=True)
    (old_output / "old.bin").write_bytes(b"old")
    runner = FakeProcessRunner()
    runner.failures.add("bad.zip")

    with pytest.raises(ExtractionFailureError) as captured:
        MediaArchiveExtractor(
            runner,
            NullLogger(),
            source_resolver=StaticSourceResolver(tmp_path),
        ).extract(
            context,
            archives,
            concurrency=2,
        )

    assert len(captured.value.failures) == 1
    assert (old_output / "old.bin").read_bytes() == b"old"
    assert (
        context.workspace.extracted_media / "good" / "member.bin"
    ).read_bytes() == b"good.zip"


def test_duplicate_output_name_is_rejected_before_build(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    first = context.workspace.raw_media / "one" / "voice.zip"
    second = context.workspace.raw_media / "two" / "VOICE.zip"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    runner = FakeProcessRunner()

    with pytest.raises(MediaArchiveExtractorError):
        MediaArchiveExtractor(
            runner,
            NullLogger(),
            source_resolver=StaticSourceResolver(tmp_path),
        ).extract(
            context,
            [first, second],
            concurrency=2,
        )

    assert runner.build_calls == 0
    assert runner.extract_calls == 0


def test_unsafe_result_path_is_rejected_before_publication(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    archives = _write_archives(context, "voice.zip")
    old_output = context.workspace.extracted_media / "voice"
    old_output.mkdir(parents=True)
    (old_output / "old.bin").write_bytes(b"old")
    outside = tmp_path / "outside"
    outside.mkdir()
    runner = FakeProcessRunner()
    runner.malicious_staging_path = outside

    with pytest.raises(MediaArchiveExtractorError):
        MediaArchiveExtractor(
            runner,
            NullLogger(),
            source_resolver=StaticSourceResolver(tmp_path),
        ).extract(
            context,
            archives,
            concurrency=1,
        )

    assert (old_output / "old.bin").read_bytes() == b"old"
    assert outside.is_dir()


def test_cancellation_removes_job_staging_without_publication(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    archives = _write_archives(context, "voice.zip")
    old_output = context.workspace.extracted_media / "voice"
    old_output.mkdir(parents=True)
    (old_output / "old.bin").write_bytes(b"old")
    runner = FakeProcessRunner()
    runner.cancel_extraction = True

    with pytest.raises(OperationCancelledError):
        MediaArchiveExtractor(
            runner,
            NullLogger(),
            source_resolver=StaticSourceResolver(tmp_path),
        ).extract(
            context,
            archives,
            concurrency=1,
        )

    assert (old_output / "old.bin").read_bytes() == b"old"
    assert all(not job_root.exists() for job_root in runner.job_roots)
