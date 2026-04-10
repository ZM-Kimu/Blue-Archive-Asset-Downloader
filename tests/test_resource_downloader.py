from __future__ import annotations

from binascii import crc32
from contextlib import nullcontext
from pathlib import Path
from threading import Event
from typing import Any, ClassVar

import pytest

from ba_downloader.domain.exceptions import NetworkError
from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import DownloadResult
from ba_downloader.infrastructure.apk import ZipEntry
from ba_downloader.infrastructure.download.resource_downloader import ResourceDownloader
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.shared.crypto.encryption import calculate_crc, calculate_md5


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
            else self._payloads.pop(0) if self._payloads else b"x" * 10
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


class RecordingProgressReporter:
    instances: ClassVar[list[RecordingProgressReporter]] = []

    def __init__(
        self, total: int, description: str, *, download_mode: bool = False
    ) -> None:
        self.total = total
        self.description = description
        self.download_mode = download_mode
        self.advances: list[int] = []
        self.descriptions: list[str] = [description]
        self.statuses: list[str] = []
        self.secondary_statuses: list[str] = []
        self.failed_statuses: list[str] = []
        RecordingProgressReporter.instances.append(self)

    def __enter__(self) -> RecordingProgressReporter:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def advance(self, amount: int = 1) -> None:
        self.advances.append(amount)

    def set_total(self, total: int) -> None:
        self.total = total

    def set_description(self, description: str) -> None:
        self.description = description
        self.descriptions.append(description)

    def set_status(self, status: str) -> None:
        self.statuses.append(status)

    def set_secondary_status(self, status: str) -> None:
        self.secondary_statuses.append(status)

    def set_failed_status(self, status: str) -> None:
        self.failed_statuses.append(status)

    def set_completed(self, completed: int) -> None:
        _ = completed

    def stop(self) -> None:
        return None


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


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=2,
        version="1.0.0",
        raw_dir=str(tmp_path / "raw"),
        extract_dir=str(tmp_path / "extract"),
        temp_dir=str(tmp_path / "temp"),
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
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


def _write_asset_file(context: RuntimeContext, path: str, content: bytes) -> Path:
    asset_path = Path(context.raw_dir) / path
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(content)
    return asset_path


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
        "ba_downloader.infrastructure.download.resource_downloader.RichProgressReporter",
        RecordingProgressReporter,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(list(resources), context)

    progress = RecordingProgressReporter.instances[-1]
    assert failed == []
    assert progress.download_mode is True
    assert progress.total == 20
    assert sum(progress.advances) == 20
    assert progress.descriptions[0] == "Downloading assets..."
    assert progress.descriptions[-1] == "b.bundle"
    assert progress.statuses[0] == "0/2 files"
    assert progress.statuses[-1] == "2/2 files"
    assert progress.secondary_statuses[0] == "conc. 2/2"
    assert progress.secondary_statuses[-1] == "conc. 2/2"
    assert progress.failed_statuses[0] == "failed 0"
    assert progress.failed_statuses[-1] == "failed 0"
    assert client.download_calls
    assert client.download_calls[0]["timeout"] == downloader.DOWNLOAD_TIMEOUT_SECONDS
    assert callable(client.download_calls[0]["should_stop"])


def test_handle_interrupt_closes_client_and_force_exits_on_second_interrupt(
    tmp_path: Path,
) -> None:
    client = RecordingHttpClient()
    exit_codes: list[int] = []
    downloader = ResourceDownloader(client, NullLogger(), force_exit=exit_codes.append)
    stop_event = Event()

    downloader._handle_interrupt(stop_event, 1)
    assert stop_event.is_set()
    assert client.closed == 1
    downloader._handle_interrupt(stop_event, 2)
    assert client.closed == 2
    assert exit_codes == [130]


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("The read operation timed out.", "timeout"),
        ("HTTP 429 Too Many Requests", "throttled"),
        ("Received 403 Forbidden", "throttled"),
        ("Connection reset by peer", "connection"),
        ("Broken pipe while writing response", "connection"),
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
    context = _build_context(tmp_path).with_updates(threads=5)
    state = downloader._create_adaptive_download_state(
        list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle", "Bundle/c.bundle")),
        context,
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
        _build_context(tmp_path).with_updates(threads=3),
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
    state = downloader._create_adaptive_download_state(resources, context)
    RecordingProgressReporter.instances.clear()

    def fake_download_resource(resource, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        if resource.path.endswith("a.bundle"):
            raise RuntimeError("checksum mismatch")
        return resource

    monkeypatch.setattr(downloader, "_download_resource", fake_download_resource)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.download.resource_downloader.RichProgressReporter",
        RecordingProgressReporter,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(resources, context, adaptive_state=state)

    assert [resource.path for resource in failed] == ["Bundle/a.bundle"]
    assert state.target_concurrency == 2
    assert not [
        message
        for message in logger.warn_messages
        if "Adaptive download concurrency" in message
    ]
    assert not [
        message
        for message in logger.info_messages
        if "Adaptive download concurrency" in message
    ]
    assert logger.error_messages == []
    progress = RecordingProgressReporter.instances[-1]
    assert progress.statuses[-1] == "1/2 files"
    assert progress.secondary_statuses[-1] == "conc. 2/2"
    assert progress.failed_statuses[-1] == "failed 1"


def test_download_resources_reduces_concurrency_for_timeout_failures(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    resources = list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle"))
    state = downloader._create_adaptive_download_state(resources, context)
    RecordingProgressReporter.instances.clear()

    def fake_download_resource(resource, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        if resource.path.endswith("a.bundle"):
            raise RuntimeError("The read operation timed out.")
        return resource

    monkeypatch.setattr(downloader, "_download_resource", fake_download_resource)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.download.resource_downloader.RichProgressReporter",
        RecordingProgressReporter,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(resources, context, adaptive_state=state)

    assert [resource.path for resource in failed] == ["Bundle/a.bundle"]
    assert state.target_concurrency == 1
    assert logger.warn_messages == []
    assert logger.error_messages == []
    progress = RecordingProgressReporter.instances[-1]
    assert progress.statuses[-1] == "1/2 files"
    assert progress.secondary_statuses[-1] == "conc. 1/2"
    assert progress.failed_statuses[-1] == "failed 1"


def test_download_resources_treats_network_timeout_as_retryable_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    resources = list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle"))
    state = downloader._create_adaptive_download_state(resources, context)
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
        "ba_downloader.infrastructure.download.resource_downloader.RichProgressReporter",
        RecordingProgressReporter,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(resources, context, adaptive_state=state)

    assert [resource.path for resource in failed] == ["Bundle/a.bundle"]
    assert state.target_concurrency == 1
    assert logger.warn_messages == []
    assert logger.error_messages == []
    progress = RecordingProgressReporter.instances[-1]
    assert progress.statuses[-1] == "1/2 files"
    assert progress.secondary_statuses[-1] == "conc. 1/2"
    assert progress.failed_statuses[-1] == "failed 1"


def test_retry_rounds_reuse_adaptive_state(monkeypatch, tmp_path: Path) -> None:
    client = RecordingHttpClient()
    logger = RecordingLogger()
    downloader = ResourceDownloader(client, logger)
    context = _build_context(tmp_path)
    initial_resources = list(_build_resources("Bundle/a.bundle", "Bundle/b.bundle"))
    retry_resources = list(_build_checked_resources(tmp_path, "Bundle/retry.bundle"))
    state = downloader._create_adaptive_download_state(initial_resources, context)
    RecordingProgressReporter.instances.clear()

    assert downloader._decrease_target_concurrency(state) is True

    monkeypatch.setattr(
        "ba_downloader.infrastructure.download.resource_downloader.RichProgressReporter",
        RecordingProgressReporter,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )

    failed = downloader._download_resources(
        retry_resources,
        context,
        adaptive_state=state,
    )

    assert failed == []
    assert state.target_concurrency == 1
    progress = RecordingProgressReporter.instances[-1]
    assert progress.statuses[0] == "0/1 files"
    assert progress.secondary_statuses[0] == "conc. 1/2"
    assert progress.failed_statuses[0] == "failed 0"


def test_download_resource_rejects_http_error_status(tmp_path: Path) -> None:
    client = RecordingHttpClient(status_codes=[403])
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resource = next(iter(_build_resources("Bundle/a.bundle")))
    asset_path = Path(context.raw_dir) / resource.path

    with pytest.raises(RuntimeError, match="403"):
        downloader._download_resource(resource, context)

    assert not asset_path.exists()


def test_download_resource_rejects_post_download_size_mismatch(tmp_path: Path) -> None:
    client = RecordingHttpClient(payloads=[b"short"])
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resource = next(iter(_build_resources("Bundle/a.bundle")))
    asset_path = Path(context.raw_dir) / resource.path

    with pytest.raises(RuntimeError, match="size mismatch"):
        downloader._download_resource(resource, context)

    assert not asset_path.exists()


def test_download_resource_rejects_post_download_checksum_mismatch(
    tmp_path: Path,
) -> None:
    client = RecordingHttpClient(payloads=[b"x" * 10])
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path)
    resource = next(iter(_build_resources("Bundle/a.bundle")))
    asset_path = Path(context.raw_dir) / resource.path

    with pytest.raises(RuntimeError, match="checksum mismatch"):
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
    assert (Path(context.raw_dir) / resource.path).read_bytes() == payload


def test_download_resource_extracts_apk_entry_media_without_download_to_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = RecordingHttpClient()
    downloader = ResourceDownloader(client, NullLogger())
    context = _build_context(tmp_path).with_updates(resource_type=("media",))
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
            str(Path(context.raw_dir) / "Media/video/title.mp4"),
        )
    ]


def test_verify_resource_accepts_existing_apk_entry_media(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path).with_updates(resource_type=("media",))
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


def test_verify_and_download_logs_when_everything_is_already_present(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    resources = _build_resources("Bundle/a.bundle")

    monkeypatch.setattr(downloader, "_verify_resources", lambda *_args, **_kwargs: [])

    downloader.verify_and_download(resources, context)

    assert logger.info_messages[-1] == "All files have already been downloaded."


def test_verify_and_download_logs_successful_completion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    pending_resources = list(_build_resources("Bundle/a.bundle"))

    monkeypatch.setattr(
        downloader, "_verify_resources", lambda *_args, **_kwargs: pending_resources
    )
    monkeypatch.setattr(downloader, "_download_resources", lambda *_args, **_kwargs: [])

    downloader.verify_and_download(_build_resources("Bundle/a.bundle"), context)

    assert (
        logger.info_messages[-1] == "All files have been downloaded to your computer."
    )


def test_verify_and_download_retries_failed_downloads_before_logging_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    pending_resources = list(_build_resources("Bundle/a.bundle"))
    results = [pending_resources, []]

    monkeypatch.setattr(
        downloader,
        "_verify_resources",
        lambda *_args, **_kwargs: pending_resources,
    )
    monkeypatch.setattr(
        downloader,
        "_download_resources",
        lambda *_args, **_kwargs: results.pop(0),
    )

    downloader.verify_and_download(_build_resources("Bundle/a.bundle"), context)

    assert logger.warn_messages[-1] == "Retrying 1 failed files. Attempt 1/1."
    assert (
        logger.info_messages[-1] == "All files have been downloaded to your computer."
    )
    assert not logger.error_messages


def test_verify_and_download_does_not_log_success_when_retries_are_exhausted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    downloader = ResourceDownloader(RecordingHttpClient(), logger)
    context = _build_context(tmp_path)
    pending_resources = list(_build_resources("Bundle/a.bundle"))

    monkeypatch.setattr(
        downloader,
        "_verify_resources",
        lambda *_args, **_kwargs: pending_resources,
    )
    monkeypatch.setattr(
        downloader,
        "_download_resources",
        lambda *_args, **_kwargs: pending_resources,
    )

    downloader.verify_and_download(_build_resources("Bundle/a.bundle"), context)

    assert (
        "All files have been downloaded to your computer." not in logger.info_messages
    )
    assert logger.error_messages[-1] == "Failed to download 1 files after retries."


def test_download_resources_does_not_extract_when_post_download_validation_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    logger = RecordingLogger()
    client = RecordingHttpClient(payloads=[b"short"])
    downloader = ResourceDownloader(client, logger)
    context = _build_context(tmp_path).with_updates(extract_while_download=True)
    resources = list(_build_resources("Bundle/a.bundle"))
    extract_calls: list[str] = []
    RecordingProgressReporter.instances.clear()

    monkeypatch.setattr(
        "ba_downloader.infrastructure.download.resource_downloader.RichProgressReporter",
        RecordingProgressReporter,
    )
    monkeypatch.setattr(
        downloader, "_install_interrupt_handler", lambda stop_event: nullcontext()
    )
    monkeypatch.setattr(
        downloader,
        "_extract_resource",
        lambda resource, _context: extract_calls.append(resource.path),
    )

    failed = downloader._download_resources(resources, context)

    assert [resource.path for resource in failed] == ["Bundle/a.bundle"]
    assert extract_calls == []
    progress = RecordingProgressReporter.instances[-1]
    assert progress.statuses[-1] == "0/1 files"
    assert progress.secondary_statuses[-1] == "conc. 1/1"
    assert progress.failed_statuses[-1] == "failed 1"
    assert logger.error_messages == []


def test_extract_resource_reuses_media_extractor_instances(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    init_count = {"value": 0}

    class FakeMediaExtractor:
        def __init__(self, extract_dir: str) -> None:
            _ = extract_dir
            init_count["value"] += 1

        def extract_zip(self, file_path: str) -> None:
            _ = file_path

    monkeypatch.setattr(
        "ba_downloader.infrastructure.download.resource_downloader.MediaExtractor",
        FakeMediaExtractor,
    )

    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path).with_updates(resource_type=("media",))
    resources = AssetCollection()
    resources.add(
        "https://example.com/Media/a.zip",
        "Media/a.zip",
        10,
        "deadbeef",
        "md5",
        AssetType.media,
    )
    resources.add(
        "https://example.com/Media/b.zip",
        "Media/b.zip",
        10,
        "deadbeef",
        "md5",
        AssetType.media,
    )
    resource_one = resources[0]
    resource_two = resources[1]

    downloader._extract_resource(resource_one, context)
    downloader._extract_resource(resource_two, context)

    assert init_count["value"] == 1


def test_extract_resource_reuses_table_extractor_instances(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    init_count = {"value": 0}

    class FakeTableExtractor:
        @classmethod
        def from_context(
            cls,
            context: RuntimeContext,
            logger: NullLogger,
        ) -> FakeTableExtractor:
            _ = (context, logger)
            init_count["value"] += 1
            return cls()

        def extract_table(self, file_path: str) -> bool:
            _ = file_path
            return True

    monkeypatch.setattr(
        "ba_downloader.infrastructure.download.resource_downloader.TableExtractor",
        FakeTableExtractor,
    )

    downloader = ResourceDownloader(RecordingHttpClient(), NullLogger())
    context = _build_context(tmp_path).with_updates(resource_type=("table",))
    resources = AssetCollection()
    resources.add(
        "https://example.com/Table/a.bytes",
        "Table/a.bytes",
        10,
        "deadbeef",
        "md5",
        AssetType.table,
    )
    resources.add(
        "https://example.com/Table/b.bytes",
        "Table/b.bytes",
        10,
        "deadbeef",
        "md5",
        AssetType.table,
    )
    resource_one = resources[0]
    resource_two = resources[1]

    downloader._extract_resource(resource_one, context)
    downloader._extract_resource(resource_two, context)

    assert init_count["value"] == 1


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
