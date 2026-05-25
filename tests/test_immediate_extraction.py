from __future__ import annotations

from pathlib import Path

from ba_downloader.domain.models.asset import AssetRecord, AssetType, ChecksumSpec
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.immediate import ImmediateResourceExtractor


class NullLogger:
    def info(self, message: str) -> None:
        _ = message

    def warn(self, message: str) -> None:
        _ = message

    def error(self, message: str) -> None:
        _ = message


class RecordingBundleExtractor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str] | None]] = []

    def extract_bundle(
        self,
        res_path: str,
        extract_types: list[str] | None = None,
    ) -> None:
        self.calls.append((res_path, extract_types))


class RecordingMediaExtractor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def extract_zip(self, file_path: str) -> None:
        self.calls.append(file_path)


class RecordingTableExtractor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def extract_table(self, file_path: str) -> None:
        self.calls.append(file_path)


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="cn",
        threads=1,
        version="1.0.0",
        raw_dir=str(tmp_path / "RawData"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=True,
        resource_type=("all",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _resource(path: str, asset_type: AssetType) -> AssetRecord:
    return AssetRecord(
        url="https://example.invalid/" + path,
        path=path,
        size=1,
        checksum=ChecksumSpec("md5", "deadbeef"),
        asset_type=asset_type,
    )


def test_immediate_resource_extractor_routes_downloaded_assets(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    bundle = RecordingBundleExtractor()
    media = RecordingMediaExtractor()
    table = RecordingTableExtractor()
    extractor = ImmediateResourceExtractor(
        NullLogger(),
        bundle_factory=lambda _context, _logger: bundle,
        media_factory=lambda _context: media,
        table_factory=lambda _context, _logger: table,
    )

    extractor(_resource("Bundle/a.bundle", AssetType.bundle), context)
    extractor(_resource("Media/a.zip", AssetType.media), context)
    extractor(_resource("Table/ExcelDB.db", AssetType.table), context)

    assert bundle.calls == [
        (
            str(Path(context.raw_dir) / "Bundle/a.bundle"),
            ["Texture2D", "Sprite", "AudioClip", "Font", "TextAsset", "Mesh"],
        )
    ]
    assert media.calls == [str(Path(context.raw_dir) / "Media/a.zip")]
    assert table.calls == [str(Path(context.raw_dir) / "Table/ExcelDB.db")]


def test_immediate_resource_extractor_skips_non_zip_media(tmp_path: Path) -> None:
    media = RecordingMediaExtractor()
    extractor = ImmediateResourceExtractor(
        NullLogger(),
        media_factory=lambda _context: media,
    )

    extractor(_resource("Media/raw.dat", AssetType.media), _build_context(tmp_path))

    assert media.calls == []
