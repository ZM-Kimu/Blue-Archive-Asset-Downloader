from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.media.exporter import MediaExtractor
from support.fixtures import build_execution_context


def _build_context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="jp",
        version="1.0.0",
        max_retries=1,
    )


def test_extract_zip_reports_member_progress(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    zip_path = media_dir / "voice.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("first.ogg", b"first")
        archive.writestr("second.ogg", b"second")

    updates: list[str] = []

    MediaExtractor(context).extract_zip(
        str(zip_path),
        progress_callback=updates.append,
    )

    assert updates == ["1/2 members", "2/2 members"]
    assert (
        context.workspace.extracted_media / "voice" / "first.ogg"
    ).read_bytes() == b"first"
    assert (
        context.workspace.extracted_media / "voice" / "second.ogg"
    ).read_bytes() == b"second"


def test_v3_extract_zip_publishes_only_complete_output(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    media_dir = context.workspace.raw_media
    media_dir.mkdir(parents=True)
    zip_path = media_dir / "voice.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("first.ogg", b"first")
        archive.writestr("second.ogg", b"second")

    output = context.workspace.extracted_media / "voice"
    output.mkdir(parents=True)
    (output / "previous.ogg").write_bytes(b"previous")
    checks = iter((False, True))

    with pytest.raises(OperationCancelledError):
        MediaExtractor(context).extract_zip(
            str(zip_path),
            should_stop=lambda: next(checks),
        )

    assert (output / "previous.ogg").read_bytes() == b"previous"
    assert not (output / "first.ogg").exists()
    assert not list(output.parent.glob(".voice.staging-*"))
