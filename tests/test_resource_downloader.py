from __future__ import annotations

import re
import signal
from binascii import crc32
from collections import Counter
from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from typing import Any, ClassVar
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

import ba_downloader.infrastructure.download.resource_downloader as resource_downloader_module
from ba_downloader.domain.exceptions import (
    DownloadError,
    NetworkError,
    OperationCancelledError,
)
from ba_downloader.domain.models.asset import AssetCollection, AssetRecord, AssetType
from ba_downloader.domain.models.bundle import bundle_member_cache_resource_path
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import EventCancellation
from ba_downloader.domain.ports.http import DownloadResult, HttpResponse
from ba_downloader.domain.ports.progress import ProgressState
from ba_downloader.infrastructure.download.resource_downloader import ResourceDownloader
from ba_downloader.infrastructure.files.checksum import calculate_crc, calculate_md5
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.packages import ZipEntry
from support.fixtures import build_execution_context


class RecordingHttpClient:
    def __init__(
        self,
        *,
        status_codes: list[int] | None = None,
        payloads: list[bytes] | None = None,
    ) -> None:
        self.download_calls: list[dict[str, Any]] = []
        self.closed = 0
        self._status_codes = list(status_codes or [])
        self._payloads = list(payloads or [])

    def download_to_file(
        self,
        url: str,
        destination: str,
        *,
        headers: dict[str, str] | None = None,
        transport: str = "default",
        timeout: float = 300.0,
        progress_callback: Any = None,
        should_stop: Any = None,
    ) -> Any:
        _ = (headers, transport)
        self.download_calls.append(
            {
                "url": url,
                "destination": destination,
                "timeout": timeout,
                "should_stop": should_stop,
            }
        )
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        status_code = self._status_codes.pop(0) if self._status_codes else 200
        payload = (
            b""
            if status_code >= 400
            else self._payloads.pop(0)
            if self._payloads
            else b"x" * 10
        )
        if progress_callback is not None and payload:
            first_chunk = max(1, len(payload) // 2)
            progress_callback(first_chunk)
            if len(payload) > first_chunk:
                progress_callback(len(payload) - first_chunk)
        Path(destination).write_bytes(payload)
        return DownloadResult(
            path=destination,
            bytes_written=len(payload),
            status_code=status_code,
            headers={},
            url=url,
        )

    def close(self) -> None:
        self.closed += 1


class BundleArchiveHttpClient:
    def __init__(
        self,
        archives: dict[str, bytes],
        *,
        ignore_ranges: set[str] | None = None,
    ) -> None:
        self.archives = archives
        self.ignore_ranges = ignore_ranges or set()
        self.head_calls: list[str] = []
        self.range_calls: list[tuple[str, int, int]] = []
        self.download_calls: list[str] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: object | None = None,
        data: object | None = None,
        params: dict[str, object] | None = None,
        transport: str = "default",
        timeout: float = 10.0,
    ) -> HttpResponse:
        _ = (json, data, params, transport, timeout)
        payload = self.archives[url]
        if method == "HEAD":
            self.head_calls.append(url)
            return HttpResponse(200, {"Content-Length": str(len(payload))}, b"", url)
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", dict(headers or {}).get("Range", ""))
        assert match is not None
        start, end = int(match.group(1)), int(match.group(2))
        self.range_calls.append((url, start, end))
        if url in self.ignore_ranges:
            return HttpResponse(
                200, {"Content-Length": str(len(payload))}, payload, url
            )
        return HttpResponse(
            206,
            {"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
            payload[start : end + 1],
            url,
        )

    def download_to_file(
        self,
        url: str,
        destination: str,
        *,
        headers: dict[str, str] | None = None,
        transport: str = "default",
        timeout: float = 300.0,
        progress_callback: Any = None,
        should_stop: Any = None,
    ) -> DownloadResult:
        _ = (headers, transport, timeout, should_stop)
        payload = self.archives[url]
        self.download_calls.append(url)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(payload)
        if progress_callback is not None:
            progress_callback(len(payload))
        return DownloadResult(destination, len(payload), 200, {}, url)

    def close(self) -> None:
        return None


def _bundle_zip(entries: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path, payload in entries.items():
            archive.writestr(path, payload)
    return output.getvalue()


def _bundle_archive_resource(
    url: str,
    path: str,
    payload: bytes,
    *members: str,
) -> AssetRecord:
    resources = AssetCollection()
    resources.add(
        url,
        path,
        len(payload),
        str(crc32(payload) & 0xFFFFFFFF),
        "crc",
        AssetType.bundle,
        member_paths=members,
        selected_member_paths=members,
    )
    return resources[0]


class RecordingProgressReporter:
    instances: ClassVar[list[RecordingProgressReporter]] = []

    def __init__(self, initial_state: ProgressState) -> None:
        measure = initial_state.overall or initial_state.current
        self.total = measure.total if measure is not None else 0
        self.description = initial_state.label
        self.download_mode = measure is not None and measure.unit == "bytes"
        self.initial_state = initial_state
        self.states: list[ProgressState] = []
        RecordingProgressReporter.instances.append(self)

    def __enter__(self) -> RecordingProgressReporter:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def update(self, state: ProgressState) -> None:
        self.states.append(state)

    def stop(self) -> None:
        return None


def _create_recording_progress(
    _factory: object,
    initial_state: ProgressState,
) -> RecordingProgressReporter:
    return RecordingProgressReporter(initial_state)


class RecordingLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warn_messages: list[str] = []
        self.error_messages: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def warn(self, message: str) -> None:
        self.warn_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)


class CancelDuringPathPreparation:
    def __init__(self, allowed_checks: int) -> None:
        self.allowed_checks = allowed_checks
        self.checks = 0

    def is_cancelled(self) -> bool:
        return self.checks > self.allowed_checks

    def raise_if_cancelled(self) -> None:
        self.checks += 1
        if self.is_cancelled():
            raise OperationCancelledError("cancelled during path preparation")


def _build_context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="jp",
        version="1.0.0",
        max_retries=1,
    )


def _build_resources(*paths: str) -> AssetCollection:
    resources = AssetCollection()
    for path in paths:
        resources.add(
            f"https://example.com/{path}",
            path,
            10,
            f"crc-{path}",
            "crc",
            AssetType.bundle,
        )
    return resources


def _build_checked_resources(
    tmp_path: Path,
    *paths: str,
    payload: bytes = b"x" * 10,
    asset_type: AssetType = AssetType.bundle,
    algorithm: str = "crc",
) -> AssetCollection:
    resources = AssetCollection()
    for index, path in enumerate(paths):
        checksum_fixture = tmp_path / f"checksum-{index}.bin"
        checksum_fixture.write_bytes(payload)
        checksum = (
            str(calculate_crc(str(checksum_fixture)))
            if algorithm == "crc"
            else calculate_md5(str(checksum_fixture))
        )
        resources.add(
            f"https://example.com/{path}",
            path,
            len(payload),
            checksum,
            algorithm,
            asset_type,
        )
    return resources


def _write_asset_file(context: ExecutionContext, path: str, content: bytes) -> Path:
    asset_type = path.split("/", 1)[0].casefold()
    asset_path = context.workspace.raw_resource_path(asset_type, path)
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(content)
    return asset_path


def test_jp_bundle_member_download_uses_remote_ranges(tmp_path: Path) -> None:
    url = "https://example.invalid/FullPatch_044.zip"
    first = "character-ibuki-prefabs.bundle"
    second = "character-ibuki-textures.bundle"
    archive_payload = _bundle_zip({first: b"prefab", second: b"texture"})
    resource = _bundle_archive_resource(
        url,
        "Bundle/FullPatch_044.zip",
        archive_payload,
        first,
        second,
    )
    client = BundleArchiveHttpClient({url: archive_payload})
    context = _build_context(tmp_path)

    ResourceDownloader(client, NullLogger()).verify_and_download(
        AssetCollection((resource,)),
        context,
        concurrency=2,
    )

    first_path = context.workspace.raw_resource_path(
        "bundle", bundle_member_cache_resource_path(resource.path, first)
    )
    second_path = context.workspace.raw_resource_path(
        "bundle", bundle_member_cache_resource_path(resource.path, second)
    )
    assert first_path.read_bytes() == b"prefab"
    assert second_path.read_bytes() == b"texture"
    assert not context.workspace.raw_resource_path("bundle", resource.path).exists()
    assert client.download_calls == []
    assert len(client.range_calls) == 5


def test_jp_bundle_member_download_falls_back_to_full_archive(
    tmp_path: Path,
) -> None:
    url = "https://example.invalid/FullPatch_044.zip"
    member = "character-ibuki.bundle"
    archive_payload = _bundle_zip({member: b"bundle"})
    resource = _bundle_archive_resource(
        url,
        "Bundle/FullPatch_044.zip",
        archive_payload,
        member,
    )
    client = BundleArchiveHttpClient(
        {url: archive_payload},
        ignore_ranges={url},
    )
    context = _build_context(tmp_path)

    ResourceDownloader(client, NullLogger()).verify_and_download(
        AssetCollection((resource,)),
        context,
        concurrency=2,
    )

    archive_path = context.workspace.raw_resource_path("bundle", resource.path)
    member_path = context.workspace.raw_resource_path(
        "bundle", bundle_member_cache_resource_path(resource.path, member)
    )
    assert archive_path.read_bytes() == archive_payload
    assert member_path.read_bytes() == b"bundle"
    assert client.download_calls == [url]


def test_jp_bundle_member_download_deduplicates_exact_patch_entries(
    tmp_path: Path,
) -> None:
    first_url = "https://example.invalid/FullPatch_109.zip"
    second_url = "https://example.invalid/UpdatePatch_v7_004.zip"
    member = "assets-ibuki-timeline.bundle"
    member_payload = b"same timeline"
    first_payload = _bundle_zip({member: member_payload})
    second_payload = _bundle_zip({member: member_payload})
    first = _bundle_archive_resource(
        first_url,
        "Bundle/FullPatch_109.zip",
        first_payload,
        member,
    )
    second = _bundle_archive_resource(
        second_url,
        "Bundle/UpdatePatch_v7_004.zip",
        second_payload,
        member,
    )
    client = BundleArchiveHttpClient(
        {first_url: first_payload, second_url: second_payload}
    )
    context = _build_context(tmp_path)

    ResourceDownloader(client, NullLogger()).verify_and_download(
        AssetCollection((first, second)),
        context,
        concurrency=2,
    )

    first_cache = context.workspace.raw_resource_path(
        "bundle", bundle_member_cache_resource_path(first.path, member)
    )
    second_cache = context.workspace.raw_resource_path(
        "bundle", bundle_member_cache_resource_path(second.path, member)
    )
    assert first_cache.read_bytes() == member_payload
    assert second_cache.read_bytes() == member_payload
    assert len(client.range_calls) == 4
    assert client.download_calls == []


def test_jp_bundle_member_download_keeps_distinct_patch_entries(
    tmp_path: Path,
) -> None:
    first_url = "https://example.invalid/FullPatch_109.zip"
    second_url = "https://example.invalid/UpdatePatch_v7_004.zip"
    member = "assets-ibuki-timeline.bundle"
    first_payload = _bundle_zip({member: b"first timeline"})
    second_payload = _bundle_zip({member: b"other timeline"})
    first = _bundle_archive_resource(
        first_url,
        "Bundle/FullPatch_109.zip",
        first_payload,
        member,
    )
    second = _bundle_archive_resource(
        second_url,
        "Bundle/UpdatePatch_v7_004.zip",
        second_payload,
        member,
    )
    client = BundleArchiveHttpClient(
        {first_url: first_payload, second_url: second_payload}
    )
    context = _build_context(tmp_path)

    ResourceDownloader(client, NullLogger()).verify_and_download(
        AssetCollection((first, second)),
        context,
        concurrency=2,
    )

    first_cache = context.workspace.raw_resource_path(
        "bundle", bundle_member_cache_resource_path(first.path, member)
    )
    second_cache = context.workspace.raw_resource_path(
        "bundle", bundle_member_cache_resource_path(second.path, member)
    )
    assert first_cache.read_bytes() == b"first timeline"
    assert second_cache.read_bytes() == b"other timeline"
    assert len(client.range_calls) == 6
    assert client.download_calls == []


def test_jp_bundle_member_download_reuses_local_complete_archive(
    tmp_path: Path,
) -> None:
    url = "https://example.invalid/FullPatch_044.zip"
    member = "character-ibuki.bundle"
    archive_payload = _bundle_zip({member: b"bundle"})
    resource = _bundle_archive_resource(
        url,
        "Bundle/FullPatch_044.zip",
        archive_payload,
        member,
    )
    client = BundleArchiveHttpClient({url: archive_payload})
    context = _build_context(tmp_path)
    archive_path = context.workspace.raw_resource_path("bundle", resource.path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(archive_payload)

    ResourceDownloader(client, NullLogger()).verify_and_download(
        AssetCollection((resource,)),
        context,
        concurrency=2,
    )

    member_path = context.workspace.raw_resource_path(
        "bundle", bundle_member_cache_resource_path(resource.path, member)
    )
    assert member_path.read_bytes() == b"bundle"
    assert client.head_calls == []
    assert client.range_calls == []
    assert client.download_calls == []


def test_download_resources_tracks_aggregate_bytes(monkeypatch, tmp_path: Path) -> None:
    client = RecordingHttpClient()
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    RecordingProgressReporter.instances.clear()
    resources = _build_checked_resources(
        tmp_path,
        "Bundle/a.bundle",
        "Bundle/b.bundle",
    )

    monkeypatch.setattr(
        "ba_downloader.infrastructure.progress.NullProgressReporterFactory.create",
        _create_recording_progress,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(list(resources), context, concurrency=2)

    assert failed == []
    progress = RecordingProgressReporter.instances[-1]
    assert progress.download_mode is True
    assert progress.total == 20
    assert progress.states[-1].overall is not None
    assert progress.states[-1].overall.completed == 20
    assert any(
        state.workers is not None and state.workers.active == 2
        for state in progress.states
    )
    assert progress.states[-1].workers is not None
    assert progress.states[-1].workers.active == 0
    assert client.download_calls
    assert client.download_calls[0]["timeout"] == downloader.DOWNLOAD_TIMEOUT_SECONDS
    assert callable(client.download_calls[0]["should_stop"])


def test_download_interrupt_is_dispatched_outside_the_signal_handler() -> None:
    client = RecordingHttpClient()
    exit_codes: list[int] = []
    downloader = ResourceDownloader(client, NullLogger(), force_exit=exit_codes.append)
    stop_event = Event()

    with downloader._install_interrupt_handler(stop_event):
        signal.raise_signal(signal.SIGINT)
        deadline = monotonic() + 1.0
        while not stop_event.is_set() and monotonic() < deadline:
            sleep(0.01)

    assert stop_event.is_set()
    assert client.closed == 1
    assert exit_codes == []


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("The read operation timed out.", "timeout"),
        ("HTTP 429 Too Many Requests", "throttled"),
        ("Received 403 Forbidden", "throttled"),
        ("Connection reset by peer", "connection"),
        ("Broken pipe while writing response", "connection"),
        ("incomplete response body", "connection"),
        ("size mismatch (expected 10 bytes, got 3 bytes)", "connection"),
        ("unexpected checksum mismatch", "other"),
    ],
)
def test_classify_download_failure(message: str, expected: str) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())

    assert downloader._classify_download_failure(RuntimeError(message)) == expected


def test_adaptive_concurrency_decreases_and_resets_success_counter(
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    state = downloader._create_adaptive_download_state(
        list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle", "Bundle/c.bundle")),
        5,
    )
    state.success_since_adjustment = 1

    assert downloader._decrease_target_concurrency(state) is True
    assert state.target_concurrency == 2
    assert state.success_since_adjustment == 0
    assert downloader._decrease_target_concurrency(state) is True
    assert state.target_concurrency == 1
    assert downloader._decrease_target_concurrency(state) is False


def test_adaptive_concurrency_increases_every_two_successes(tmp_path: Path) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    state = downloader._create_adaptive_download_state(
        list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle", "Bundle/c.bundle")),
        3,
    )
    state.target_concurrency = 1

    assert downloader._record_download_success(state) is False
    assert state.target_concurrency == 1
    assert state.success_since_adjustment == 1

    assert downloader._record_download_success(state) is True
    assert state.target_concurrency == 2
    assert state.success_since_adjustment == 0

    assert downloader._record_download_success(state) is False
    assert downloader._record_download_success(state) is True
    assert state.target_concurrency == 3

    assert downloader._record_download_success(state) is False
    assert downloader._record_download_success(state) is False
    assert state.target_concurrency == 3
    assert state.success_since_adjustment == 0


def test_download_resources_keeps_concurrency_on_non_network_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    resources = list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle"))
    state = downloader._create_adaptive_download_state(resources, 2)
    RecordingProgressReporter.instances.clear()

    def fake_download_resource(resource, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        if resource.path.endswith("a.bundle"):
            raise RuntimeError("checksum mismatch")
        return resource

    monkeypatch.setattr(downloader, "_download_resource", fake_download_resource)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.progress.NullProgressReporterFactory.create",
        _create_recording_progress,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(
        resources, context, adaptive_state=state, concurrency=2
    )

    assert [resource.path for resource in failed] == ["Bundle/a.bundle"]
    assert state.target_concurrency == 2


def test_download_resources_reduces_concurrency_for_timeout_failures(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    resources = list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle"))
    state = downloader._create_adaptive_download_state(resources, 2)
    RecordingProgressReporter.instances.clear()

    def fake_download_resource(resource, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        if resource.path.endswith("a.bundle"):
            raise RuntimeError("The read operation timed out.")
        return resource

    monkeypatch.setattr(downloader, "_download_resource", fake_download_resource)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.progress.NullProgressReporterFactory.create",
        _create_recording_progress,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(
        resources, context, adaptive_state=state, concurrency=2
    )

    assert [resource.path for resource in failed] == ["Bundle/a.bundle"]
    assert state.target_concurrency == 1


def test_download_resources_treats_network_timeout_as_retryable_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    resources = list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle"))
    state = downloader._create_adaptive_download_state(resources, 2)
    RecordingProgressReporter.instances.clear()

    def fake_download_resource(resource, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        if resource.path.endswith("a.bundle"):
            raise NetworkError(
                "Failed to download https://example.com/Bundle/a.bundle: "
                "The read operation timed out"
            )
        return resource

    monkeypatch.setattr(downloader, "_download_resource", fake_download_resource)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.progress.NullProgressReporterFactory.create",
        _create_recording_progress,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(
        resources, context, adaptive_state=state, concurrency=2
    )

    assert [resource.path for resource in failed] == ["Bundle/a.bundle"]
    assert state.target_concurrency == 1


def test_retry_rounds_reuse_adaptive_state(monkeypatch, tmp_path: Path) -> None:
    client = RecordingHttpClient()
    logger = RecordingLogger()
    downloader = ResourceDownloader(client, logger)
    context = _build_context(tmp_path)
    initial_resources = list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle"))
    retry_resources = list(_build_checked_resources(tmp_path, "Bundle/retry.bundle"))
    state = downloader._create_adaptive_download_state(initial_resources, 2)
    RecordingProgressReporter.instances.clear()

    assert downloader._decrease_target_concurrency(state) is True

    monkeypatch.setattr(
        "ba_downloader.infrastructure.progress.NullProgressReporterFactory.create",
        _create_recording_progress,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(
        retry_resources,
        context,
        adaptive_state=state,
        concurrency=2,
    )

    assert failed == []
    assert state.target_concurrency == 1


def test_download_resource_rejects_http_error_status(tmp_path: Path) -> None:
    client = RecordingHttpClient(status_codes=[403])
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resource = next(iter(_build_resources("Bundle/a.bundle")))
    asset_path = context.workspace.raw_resource_path(
        resource.asset_type.value, resource.path
    )

    with pytest.raises(RuntimeError):
        downloader._download_resource(resource, context)

    assert not asset_path.exists()


def test_download_resource_rejects_post_download_size_mismatch(tmp_path: Path) -> None:
    client = RecordingHttpClient(payloads=[b"short"])
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resource = next(iter(_build_resources("Bundle/a.bundle")))
    asset_path = context.workspace.raw_resource_path(
        resource.asset_type.value, resource.path
    )

    with pytest.raises(RuntimeError):
        downloader._download_resource(resource, context)

    assert not asset_path.exists()


def test_download_resource_rejects_post_download_checksum_mismatch(
    tmp_path: Path,
) -> None:
    client = RecordingHttpClient(payloads=[b"x" * 10])
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resource = next(iter(_build_resources("Bundle/a.bundle")))
    asset_path = context.workspace.raw_resource_path(
        resource.asset_type.value, resource.path
    )

    with pytest.raises(RuntimeError):
        downloader._download_resource(resource, context)

    assert not asset_path.exists()


def test_download_resource_accepts_valid_downloaded_file(tmp_path: Path) -> None:
    payload = b"validated!"
    client = RecordingHttpClient(payloads=[payload])
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resource = next(
        iter(_build_checked_resources(tmp_path, "Bundle/a.bundle", payload=payload))
    )

    returned_resource = downloader._download_resource(resource, context)

    assert returned_resource == resource
    assert (
        context.workspace.raw_resource_path(
            resource.asset_type.value, resource.path
        ).read_bytes()
        == payload
    )


def test_download_resource_extracts_apk_entry_media_without_download_to_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = RecordingHttpClient()
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/BlueArchive.apk",
        "Media/video/title.mp4",
        0,
        "0",
        "crc",
        AssetType.media,
        {
            "source": ResourceDownloader.APK_ENTRY_SOURCE,
            "apk_entry_path": "assets/video/title.mp4",
            "media_type": "mp4",
        },
    )
    resource = resources[0]
    zip_entry = ZipEntry(
        path="assets/video/title.mp4",
        crc32=crc32(b"title.mp4") & 0xFFFFFFFF,
        local_header_offset=0,
        compressed_size=9,
        uncompressed_size=9,
        compression_method=0,
        file_name_length=0,
        extra_field_length=0,
    )
    extracted: list[tuple[str, str]] = []

    monkeypatch.setattr(
        downloader,
        "_resolve_apk_zip_entry",
        lambda _resource: zip_entry,
    )

    def fake_extract_zip_entry(url, entry, destination, http_client, **kwargs):  # type: ignore[no-untyped-def]
        _ = (http_client, kwargs)
        assert entry == zip_entry
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(b"title.mp4")
        extracted.append((url, str(destination)))
        return Path(destination)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.download.resource_downloader.extract_zip_entry",
        fake_extract_zip_entry,
    )

    returned_resource = downloader._download_resource(resource, context)

    assert returned_resource == resource
    assert client.download_calls == []
    assert extracted == [
        (
            "https://example.invalid/BlueArchive.apk",
            str(context.workspace.raw_media / "video/title.mp4"),
        )
    ]


def test_verify_resource_accepts_existing_apk_entry_media(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    asset_path = _write_asset_file(context, "Media/video/title.mp4", b"title.mp4")
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/BlueArchive.apk",
        "Media/video/title.mp4",
        0,
        "0",
        "crc",
        AssetType.media,
        {
            "source": ResourceDownloader.APK_ENTRY_SOURCE,
            "apk_entry_path": "assets/video/title.mp4",
            "media_type": "mp4",
        },
    )
    resource = resources[0]
    zip_entry = ZipEntry(
        path="assets/video/title.mp4",
        crc32=calculate_crc(str(asset_path)),
        local_header_offset=0,
        compressed_size=asset_path.stat().st_size,
        uncompressed_size=asset_path.stat().st_size,
        compression_method=0,
        file_name_length=0,
        extra_field_length=0,
    )
    monkeypatch.setattr(
        downloader,
        "_resolve_apk_zip_entry",
        lambda _resource: zip_entry,
    )

    returned_resource, verified = downloader._verify_resource(resource, context)

    assert returned_resource == resource
    assert verified is True


def test_verify_and_download_skips_download_when_everything_is_already_present(
    monkeypatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), RecordingLogger())
    context = _build_context(tmp_path)
    resources = _build_resources("Bundle/a.bundle")

    monkeypatch.setattr(downloader, "_verify_resources", lambda *_args, **_kwargs: [])
    download_calls: list[object] = []
    monkeypatch.setattr(
        downloader,
        "_download_resources",
        lambda *_args, **_kwargs: download_calls.append(object()),
    )

    downloader.verify_and_download(resources, context, concurrency=2)

    assert download_calls == []


def test_verify_and_download_retries_failed_downloads_once_before_succeeding(
    monkeypatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), RecordingLogger())
    context = _build_context(tmp_path)
    pending_resources = list(_build_resources("Bundle/a.bundle"))
    results = [pending_resources, []]
    download_calls = 0

    monkeypatch.setattr(
        downloader,
        "_verify_resources",
        lambda *_args, **_kwargs: pending_resources,
    )

    def download(*_args: object, **_kwargs: object) -> list[Any]:
        nonlocal download_calls
        download_calls += 1
        return results.pop(0)

    monkeypatch.setattr(downloader, "_download_resources", download)

    downloader.verify_and_download(
        _build_resources("Bundle/a.bundle"), context, concurrency=2
    )

    assert download_calls == 2


def test_verify_and_download_raises_when_retries_are_exhausted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), RecordingLogger())
    context = _build_context(tmp_path)
    resources = _build_resources("Bundle/a.bundle", "Media/b.zip")
    pending_resources = list(resources)

    monkeypatch.setattr(
        downloader,
        "_verify_resources",
        lambda *_args, **_kwargs: pending_resources,
    )
    download_calls = 0

    def download(*_args: object, **_kwargs: object) -> list[Any]:
        nonlocal download_calls
        download_calls += 1
        return pending_resources

    monkeypatch.setattr(downloader, "_download_resources", download)

    with pytest.raises(DownloadError):
        downloader.verify_and_download(resources, context, concurrency=2)

    assert download_calls == 2


def test_verify_resource_accepts_jp_crc_decimal_strings(tmp_path: Path) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    content = b"jp bundle payload"
    asset_path = _write_asset_file(context, "Bundle/jp.bundle", content)
    resources = AssetCollection()
    resources.add(
        "https://example.com/Bundle/jp.bundle",
        "Bundle/jp.bundle",
        asset_path.stat().st_size,
        str(calculate_crc(str(asset_path))),
        "crc",
        AssetType.bundle,
    )
    resource = resources[0]

    returned_resource, verified = downloader._verify_resource(resource, context)

    assert returned_resource == resource
    assert verified is True


def test_verify_resource_canonicalizes_existing_case_only_path(
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    payload = b"table payload"
    lower_path = _write_asset_file(
        context,
        "Table/tablepatchpack_groundstage_1.zip",
        payload,
    )
    checksum = str(calculate_crc(str(lower_path)))
    resources = AssetCollection()
    resources.add(
        "https://example.com/Table/TablePatchPack_GroundStage_1.zip",
        "Table/TablePatchPack_GroundStage_1.zip",
        len(payload),
        checksum,
        "crc",
        AssetType.table,
    )
    pending = downloader._verify_resources(resources, context, concurrency=2)

    table_names = {item.name for item in (context.workspace.raw_tables).iterdir()}
    assert pending == []
    assert table_names == {"TablePatchPack_GroundStage_1.zip"}


def test_verification_indexes_each_existing_parent_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    resources = AssetCollection()
    paths = (
        "Bundle/a.bundle",
        "Bundle/b.bundle",
        "Media/Audio/one.zip",
        "Media/Audio/two.zip",
        "Media/Video/three.zip",
    )
    expected_parents: set[Path] = set()
    for index, path in enumerate(paths):
        payload = f"payload-{index}".encode()
        asset_path = _write_asset_file(context, path, payload)
        expected_parents.add(asset_path.parent)
        resources.add(
            f"https://example.com/{path}",
            path,
            len(payload),
            calculate_md5(asset_path),
            "md5",
            AssetType(path.split("/", 1)[0].casefold()),
        )

    original_iterdir = Path.iterdir
    directory_scans: Counter[Path] = Counter()

    def count_iterdir(path: Path):  # type: ignore[no-untyped-def]
        if path in expected_parents:
            directory_scans[path] += 1
        return original_iterdir(path)

    checksum_calls: Counter[Path] = Counter()
    original_md5 = resource_downloader_module.calculate_md5

    def count_md5(path: str | Path) -> str:
        checksum_calls[Path(path)] += 1
        return original_md5(path)

    monkeypatch.setattr(Path, "iterdir", count_iterdir)
    monkeypatch.setattr(resource_downloader_module, "calculate_md5", count_md5)

    pending = downloader._verify_resources(resources, context, concurrency=5)

    assert pending == []
    assert directory_scans == Counter({parent: 1 for parent in expected_parents})
    assert checksum_calls == Counter(
        {
            context.workspace.raw_resource_path(
                resource.asset_type.value,
                resource.path,
            ): 1
            for resource in resources
        }
    )


def test_verify_and_download_does_not_rescan_parent_for_missing_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = RecordingHttpClient()
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resources = _build_checked_resources(
        tmp_path,
        "Bundle/present.bundle",
        "Bundle/missing.bundle",
    )
    _write_asset_file(context, "Bundle/present.bundle", b"x" * 10)
    original_iterdir = Path.iterdir
    directory_scans = 0

    def count_bundle_scans(path: Path):  # type: ignore[no-untyped-def]
        nonlocal directory_scans
        if path == context.workspace.raw_bundles:
            directory_scans += 1
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", count_bundle_scans)

    downloader.verify_and_download(resources, context, concurrency=2)

    assert directory_scans == 1
    assert (context.workspace.raw_bundles / "missing.bundle").is_file()


def test_path_preparation_skips_missing_parents_without_enumeration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    resources = _build_checked_resources(
        tmp_path,
        "Media/missing/voice.zip",
        asset_type=AssetType.media,
        algorithm="md5",
    )
    missing_parent = context.workspace.raw_media / "missing"
    original_iterdir = Path.iterdir

    def reject_missing_parent(path: Path):  # type: ignore[no-untyped-def]
        if path == missing_parent:
            raise AssertionError("missing parents must not be enumerated")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", reject_missing_parent)

    pending = downloader._verify_resources(resources, context, concurrency=2)

    assert list(pending) == list(resources)


def test_case_rename_planner_rejects_ambiguous_matches(tmp_path: Path) -> None:
    parent = tmp_path / "assets"
    entries = (parent / "voice.zip", parent / "VOICE.ZIP")

    assert (
        ResourceDownloader._plan_case_renames(
            parent,
            entries,
            {"Voice.zip"},
        )
        == ()
    )
    assert (
        ResourceDownloader._plan_case_renames(
            parent,
            (parent / "voice.zip",),
            {"Voice.zip", "VOICE.ZIP"},
        )
        == ()
    )
    assert (
        ResourceDownloader._plan_case_renames(
            parent,
            entries,
            {"voice.zip"},
        )
        == ()
    )


def test_path_preparation_restores_source_when_case_rename_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    source = _write_asset_file(context, "Table/lower.zip", b"payload")
    target = source.with_name("Lower.zip")
    resources = AssetCollection()
    resources.add(
        "https://example.com/Table/Lower.zip",
        "Table/Lower.zip",
        7,
        str(calculate_crc(source)),
        "crc",
        AssetType.table,
    )
    original_rename = Path.rename

    def fail_publication(path: Path, destination: str | Path) -> Path:
        destination_path = Path(destination)
        if (
            path.name.startswith(f".{target.name}.casefix-")
            and destination_path.name == target.name
        ):
            raise OSError("case-only rename failed")
        return original_rename(path, destination)

    monkeypatch.setattr(Path, "rename", fail_publication)

    downloader._canonicalize_resource_paths(resources, context)

    assert {item.name for item in source.parent.iterdir()} == {source.name}


def test_path_preparation_checks_cancellation(tmp_path: Path) -> None:
    cancellation = CancelDuringPathPreparation(allowed_checks=1)
    downloader = ResourceDownloader(
        RecordingHttpClient(),
        NullLogger(),
        cancellation=cancellation,
    )
    context = _build_context(tmp_path)
    resources = _build_resources("Bundle/a.bundle", "Media/b.zip")

    with pytest.raises(OperationCancelledError):
        downloader._canonicalize_resource_paths(resources, context)


def test_content_verification_checks_cancellation_after_hashing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cancellation_event = Event()
    downloader = ResourceDownloader(
        RecordingHttpClient(),
        NullLogger(),
        cancellation=EventCancellation(cancellation_event),
    )
    context = _build_context(tmp_path)
    resources = _build_checked_resources(
        tmp_path,
        "Media/one.zip",
        "Media/two.zip",
        asset_type=AssetType.media,
        algorithm="md5",
    )
    for resource in resources:
        _write_asset_file(context, resource.path, b"x" * 10)
    original_md5 = resource_downloader_module.calculate_md5

    def cancel_after_hash(path: str | Path) -> str:
        result = original_md5(path)
        cancellation_event.set()
        return result

    monkeypatch.setattr(resource_downloader_module, "calculate_md5", cancel_after_hash)

    with pytest.raises(OperationCancelledError):
        downloader._verify_resources(resources, context, concurrency=2)


def test_size_mismatch_does_not_hash_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    asset_path = _write_asset_file(context, "Media/short.zip", b"short")
    resources = AssetCollection()
    resources.add(
        "https://example.com/Media/short.zip",
        "Media/short.zip",
        99,
        "unused",
        "md5",
        AssetType.media,
    )

    def reject_hash(_path: str | Path) -> str:
        raise AssertionError("size mismatches must not be hashed")

    monkeypatch.setattr(resource_downloader_module, "calculate_md5", reject_hash)

    assert (
        downloader._get_validation_error(asset_path, resources[0])
        == "size mismatch (expected 99 bytes, got 5 bytes)"
    )


def test_validation_stats_a_matching_file_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    payload = b"one stat"
    asset_path = _write_asset_file(context, "Media/one-stat.zip", payload)
    resources = AssetCollection()
    resources.add(
        "https://example.com/Media/one-stat.zip",
        "Media/one-stat.zip",
        len(payload),
        calculate_md5(asset_path),
        "md5",
        AssetType.media,
    )
    original_stat = Path.stat
    stat_calls = 0

    def count_stat(path: Path, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal stat_calls
        if path == asset_path:
            stat_calls += 1
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", count_stat)

    assert downloader._get_validation_error(asset_path, resources[0]) is None
    assert stat_calls == 1


def test_verify_resource_accepts_crc_hex_strings(tmp_path: Path) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    content = b"hex crc payload"
    asset_path = _write_asset_file(context, "Bundle/hex.bundle", content)
    resources = AssetCollection()
    resources.add(
        "https://example.com/Bundle/hex.bundle",
        "Bundle/hex.bundle",
        asset_path.stat().st_size,
        f"{calculate_crc(str(asset_path)):08x}",
        "crc",
        AssetType.bundle,
    )
    resource = resources[0]

    _, verified = downloader._verify_resource(resource, context)

    assert verified is True


def test_verify_resource_accepts_md5_case_insensitively(tmp_path: Path) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    content = b"md5 payload"
    asset_path = _write_asset_file(context, "Media/example.zip", content)
    resources = AssetCollection()
    resources.add(
        "https://example.com/Media/example.zip",
        "Media/example.zip",
        asset_path.stat().st_size,
        calculate_md5(str(asset_path)).upper(),
        "md5",
        AssetType.media,
    )
    resource = resources[0]

    _, verified = downloader._verify_resource(resource, context)

    assert verified is True


@pytest.mark.parametrize("checksum_value", ["", "not-a-valid-crc", "0x"])
def test_verify_resource_returns_false_for_invalid_checksum_values(
    tmp_path: Path,
    checksum_value: str,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path)
    content = b"invalid checksum payload"
    asset_path = _write_asset_file(context, "Bundle/invalid.bundle", content)
    resources = AssetCollection()
    resources.add(
        "https://example.com/Bundle/invalid.bundle",
        "Bundle/invalid.bundle",
        asset_path.stat().st_size,
        checksum_value,
        "crc",
        AssetType.bundle,
    )
    resource = resources[0]

    _, verified = downloader._verify_resource(resource, context)

    assert verified is False
