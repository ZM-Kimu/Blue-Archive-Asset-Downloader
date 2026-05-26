from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.media.exporter import MediaExtractor


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=2,
        version="1.0.0",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("media",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def test_extract_zip_reports_member_progress(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    media_dir = Path(context.raw_dir) / "Media"
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
        Path(context.extract_dir) / "Media" / "voice" / "first.ogg"
    ).read_bytes() == b"first"
    assert (
        Path(context.extract_dir) / "Media" / "voice" / "second.ogg"
    ).read_bytes() == b"second"
