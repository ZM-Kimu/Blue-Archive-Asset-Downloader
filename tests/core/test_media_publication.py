from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.infrastructure.extraction.errors import ExtractionFailureError
from ba_downloader.infrastructure.extraction.media import exporter as media_exporter
from ba_downloader.infrastructure.extraction.media.exporter import (
    MediaArchiveExtractor,
    MediaArchiveExtractorError,
)


class UnusedProcessRunner:
    def run(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("Publication tests must not start the media tool.")


class UnusedSourceResolver:
    def resolve(self, context: object) -> Path:
        raise AssertionError(f"Source resolution was unexpected: {context}")


def test_media_result_rejects_staging_path_outside_expected_archive_directory(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "archive-000000").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    request = media_exporter._ArchiveRequest(tmp_path / "one.zip", "one", b"")
    payload = {
        "archives": [
            {
                "succeeded": True,
                "staging_path": str(outside),
                "error": None,
                "member_count": 1,
                "output_bytes": 1,
            }
        ]
    }

    with pytest.raises(MediaArchiveExtractorError, match="unsafe staging"):
        MediaArchiveExtractor._validate_archive_results(payload, [request], staging)


def test_media_archive_failures_do_not_block_successful_publication(
    context_factory: object,
    recording_logger: object,
    tmp_path: Path,
) -> None:
    context = context_factory()  # type: ignore[operator]
    successful = tmp_path / "archive-000000"
    successful.mkdir()
    (successful / "audio.ogg").write_bytes(b"audio")
    requests = [
        media_exporter._ArchiveRequest(tmp_path / "one.zip", "one", b""),
        media_exporter._ArchiveRequest(tmp_path / "two.zip", "two", b""),
    ]
    results = [
        {
            "archive_path": str(requests[0].path),
            "output_name": "one",
            "staging_path": str(successful),
            "succeeded": True,
            "error": None,
            "member_count": 1,
            "output_bytes": 5,
        },
        {
            "archive_path": str(requests[1].path),
            "output_name": "two",
            "staging_path": None,
            "succeeded": False,
            "error": "bad password",
            "member_count": 0,
            "output_bytes": 0,
        },
    ]
    extractor = MediaArchiveExtractor(
        UnusedProcessRunner(),  # type: ignore[arg-type]
        recording_logger,  # type: ignore[arg-type]
        source_resolver=UnusedSourceResolver(),
    )

    with pytest.raises(ExtractionFailureError):
        extractor._publish_results(context, requests, results)  # type: ignore[arg-type]

    assert (
        context.workspace.extracted_media / "one" / "audio.ogg"
    ).read_bytes() == b"audio"
