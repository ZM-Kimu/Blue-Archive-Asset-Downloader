from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from pathlib import Path
from threading import Event
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
from ba_downloader.domain.ports.progress import ProgressMeasure, ProgressState
from ba_downloader.infrastructure.extraction.errors import (
    ExtractionFailureError,
    MediaExtractionError,
)
from ba_downloader.infrastructure.extraction.media import exporter as exporter_module
from ba_downloader.infrastructure.extraction.media.exporter import (
    MEDIA_EXTRACTOR_SCHEMA_VERSION,
    MediaArchiveExtractor,
    MediaArchiveExtractorError,
    media_extraction_lock_path,
    media_extractor_cache_fingerprint,
)
from ba_downloader.infrastructure.files.lock import InterprocessFileLock
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
                            "active_workers": 0,
                            "worker_limit": min(30, len(archives)),
                            "failed_archives": len(self.failures),
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


class BlockingBuildRunner(FakeProcessRunner):
    def __init__(self) -> None:
        super().__init__()
        self.build_started = Event()
        self.release_build = Event()

    def run(
        self,
        command: ProcessCommand,
        *,
        output_observer: ProcessOutputObserverPort | None = None,
    ) -> ProcessResult:
        if command.argv[1] == "build":
            self.build_started.set()
            assert self.release_build.wait(timeout=10)
        return super().run(command, output_observer=output_observer)


class StaticSourceResolver:
    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root
        self.calls = 0

    def resolve(self, _context: ExecutionContext) -> Path:
        self.calls += 1
        return self.source_root


class SignallingCancellation:
    def __init__(self) -> None:
        self.checked = Event()
        self.cancelled = Event()

    def is_cancelled(self) -> bool:
        return self.cancelled.is_set()

    def raise_if_cancelled(self) -> None:
        self.checked.set()
        if self.is_cancelled():
            raise OperationCancelledError("Operation cancelled.")


class RecordingProgress(AbstractContextManager["RecordingProgress"]):
    def __init__(self) -> None:
        self.states: list[ProgressState] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def update(self, state: ProgressState) -> None:
        self.states.append(state)

    def stop(self) -> None:
        return None


class RecordingProgressFactory:
    def __init__(self) -> None:
        self.progress = RecordingProgress()

    def create(self, initial_state: ProgressState) -> RecordingProgress:
        _ = initial_state
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
    state = progress_factory.progress.states[-1]
    assert state.stage == "complete"
    assert state.overall is not None and state.overall.completed == 300
    assert state.current is not None and state.current.completed == 300
    assert state.workers is not None
    assert state.workers.active == 0
    assert state.workers.limit == 30
    assert state.failures == 0
    assert (
        context.workspace.extracted_media / "voice" / "member.bin"
    ).read_bytes() == b"voice.zip"
    assert "password" not in json.dumps(runner.result_payloads[0])


def test_media_progress_does_not_regress_on_reordered_worker_events() -> None:
    progress = RecordingProgress()
    initial = ProgressState(
        "Media",
        "extracting",
        overall=ProgressMeasure(0, 2, "archives"),
    )
    observer = exporter_module._MediaProgressObserver(progress, initial)

    for completed, members, failures in ((2, 10, 1), (1, 5, 0)):
        observer.on_output(
            ProcessOutputLine(
                "stdout",
                json.dumps(
                    {
                        "schema_version": MEDIA_EXTRACTOR_SCHEMA_VERSION,
                        "kind": "progress",
                        "completed_archives": completed,
                        "total_archives": 2,
                        "completed_members": members,
                        "total_members": 10,
                        "active_workers": 1,
                        "worker_limit": 2,
                        "failed_archives": failures,
                    }
                ),
            )
        )

    state = progress.states[-1]
    assert state.overall is not None and state.overall.completed == 2
    assert state.current is not None and state.current.completed == 10
    assert state.failures == 1


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


def test_source_change_uses_a_new_content_addressed_build(
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

    source_root = tmp_path / "media-tool"
    source_root.mkdir()
    source = source_root / "Program.cs"
    source.write_text("first", encoding="utf8")
    (source_root / "MediaArchiveExtractor.csproj").write_text(
        "<Project />", encoding="utf8"
    )
    monkeypatch.setattr(exporter_module, "_media_tool_root", lambda: source_root)

    first = extractor.prepare(context)
    source.write_text("second", encoding="utf8")
    second = extractor.prepare(context)
    monkeypatch.setattr(exporter_module, "SHARPZIPLIB_COMMIT", "changed-commit")
    third = extractor.prepare(context)

    assert runner.build_calls == 3
    assert len({first.parent, second.parent, third.parent}) == 3


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
    progress_factory = RecordingProgressFactory()

    with pytest.raises(ExtractionFailureError) as captured:
        MediaArchiveExtractor(
            runner,
            NullLogger(),
            source_resolver=StaticSourceResolver(tmp_path),
            progress_factory=progress_factory,
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
    state = progress_factory.progress.states[-1]
    assert state.stage == "failed"
    assert state.overall is not None and state.overall.completed == 2
    assert state.workers is not None and state.workers.active == 0
    assert state.failures == 1


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
    with InterprocessFileLock(
        media_extraction_lock_path(context),
        operation="media extraction lock release verification",
    ):
        pass


def test_active_media_extraction_rejects_duplicate_without_starting_tool(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    archives = _write_archives(context, "voice.zip")
    old_output = context.workspace.extracted_media / "voice"
    old_output.mkdir(parents=True)
    (old_output / "old.bin").write_bytes(b"old")
    runner = FakeProcessRunner()
    extractor = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=StaticSourceResolver(tmp_path),
    )
    lock_path = media_extraction_lock_path(context)

    with InterprocessFileLock(lock_path, operation="first media extraction"):
        with pytest.raises(MediaExtractionError):
            extractor.extract(context, archives, concurrency=1)
        owner = json.loads(
            lock_path.with_name(f"{lock_path.name}.owner.json").read_text(
                encoding="utf8"
            )
        )

    assert owner["operation"] == "first media extraction"
    assert isinstance(owner["pid"], int)
    assert runner.build_calls == 0
    assert runner.extract_calls == 0
    assert (old_output / "old.bin").read_bytes() == b"old"


def test_media_extraction_locks_are_scoped_by_region_and_platform(
    tmp_path: Path,
) -> None:
    jp_context = _build_context(tmp_path)
    gl_context = build_execution_context(
        tmp_path,
        region="gl",
        platform="android",
        version="1.0.0",
    )
    archives = _write_archives(gl_context, "voice.zip")
    runner = FakeProcessRunner()
    extractor = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=StaticSourceResolver(tmp_path),
    )

    with InterprocessFileLock(
        media_extraction_lock_path(jp_context),
        operation="JP media extraction",
    ):
        extractor.extract(gl_context, archives, concurrency=1)

    assert media_extraction_lock_path(jp_context) != media_extraction_lock_path(
        gl_context
    )
    assert runner.extract_calls == 1


def test_concurrent_cold_prepare_builds_tool_once(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    runner = BlockingBuildRunner()
    source_resolver = StaticSourceResolver(tmp_path)
    first = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=source_resolver,
    )
    second = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=source_resolver,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_result = executor.submit(first.prepare, context)
        assert runner.build_started.wait(timeout=10)
        second_result = executor.submit(second.prepare, context)
        runner.release_build.set()
        first_tool = first_result.result(timeout=10)
        second_tool = second_result.result(timeout=10)

    assert first_tool == second_tool
    assert runner.build_calls == 1
    assert source_resolver.calls == 1


def test_waiting_for_cold_build_lock_honors_cancellation(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    cancellation = SignallingCancellation()
    runner = FakeProcessRunner()
    extractor = MediaArchiveExtractor(
        runner,
        NullLogger(),
        source_resolver=StaticSourceResolver(tmp_path),
        cancellation=cancellation,
    )
    fingerprint = media_extractor_cache_fingerprint()
    lock_path = (
        context.workspace.locks / f"media-extractor-build-{fingerprint[:20]}.lock"
    )

    with (
        InterprocessFileLock(lock_path, operation="first media extractor build"),
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        result = executor.submit(extractor.prepare, context)
        assert cancellation.checked.wait(timeout=10)
        cancellation.cancelled.set()
        with pytest.raises(OperationCancelledError):
            result.result(timeout=10)

    assert runner.build_calls == 0
