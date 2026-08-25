from __future__ import annotations

import base64
import json
import os
import shutil
import struct
from pathlib import Path
from typing import NoReturn
from zipfile import ZipFile

import pytest

from ba_downloader.infrastructure.extraction.errors import ExtractionFailureError
from ba_downloader.infrastructure.extraction.media.exporter import (
    MediaArchiveExtractor,
    media_extractor_cache_fingerprint,
)
from ba_downloader.infrastructure.extraction.media.source import (
    SHARPZIPLIB_COMMIT,
    SharpZipLibSourceResolver,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.runtime.process import CancellableProcessRunner
from ba_downloader.infrastructure.schema.crypto import zip_password
from support.fixtures import build_execution_context

pytestmark = pytest.mark.skipif(
    os.environ.get("BAAD_RUN_DOTNET_BUILD") != "1",
    reason="Set BAAD_RUN_DOTNET_BUILD=1 to run the media extractor .NET build.",
)


class _OfflineHttpClient:
    def download_to_file(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError(
            "Media extractor integration must use the checked-out SharpZipLib submodule"
        )


def _encrypted_fixture() -> bytes:
    fixture = Path(__file__).parent / "fixtures" / "media" / "voice_zipcrypto.zip.b64"
    return base64.b64decode(fixture.read_text(encoding="ascii"))


def _write_zip(path: Path, entries: list[tuple[str, bytes]]) -> None:
    with ZipFile(path, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)


def _corrupt_declared_crc(path: Path) -> None:
    payload = bytearray(path.read_bytes())
    local = payload.index(b"PK\x03\x04")
    central = payload.index(b"PK\x01\x02")
    struct.pack_into("<I", payload, local + 14, 0x12345678)
    struct.pack_into("<I", payload, central + 16, 0x12345678)
    path.write_bytes(payload)


def test_media_extractor_builds_and_enforces_archive_boundaries(
    tmp_path: Path,
) -> None:
    assert shutil.which("dotnet") is not None, ".NET 10 SDK is required"
    repository = Path(__file__).parents[1]
    context = build_execution_context(tmp_path, region="jp", version="1")
    raw = context.workspace.raw_media
    raw.mkdir(parents=True)
    encrypted = _encrypted_fixture()
    voice = raw / "voice.zip"
    voice.write_bytes(encrypted)
    wrong_password = raw / "wrong.zip"
    wrong_password.write_bytes(encrypted)
    traversal = raw / "traversal.zip"
    _write_zip(traversal, [("../escape.txt", b"escape")])
    absolute = raw / "absolute.zip"
    _write_zip(absolute, [("/absolute.txt", b"absolute")])
    duplicate = raw / "duplicate.zip"
    with pytest.warns(UserWarning):
        _write_zip(
            duplicate,
            [("same.txt", b"first"), ("same.txt", b"second")],
        )
    bad_crc = raw / "bad_crc.zip"
    _write_zip(bad_crc, [("content.bin", b"crc-content")])
    _corrupt_declared_crc(bad_crc)

    with ZipFile(voice) as oracle:
        oracle.setpassword(zip_password("voice.zip"))
        assert oracle.read("nested/first.ogg") == b"first-content"
        assert oracle.read("second.ogg") == b"second-content"

    for name in ("wrong", "traversal", "absolute", "duplicate", "bad_crc"):
        old_output = context.workspace.extracted_media / name
        old_output.mkdir(parents=True, exist_ok=True)
        (old_output / "old.bin").write_bytes(b"old")

    source_resolver = SharpZipLibSourceResolver(
        _OfflineHttpClient(),  # type: ignore[arg-type]
        NullLogger(),
        repository_root=repository,
    )
    source_root = source_resolver.resolve(context)
    assert source_root == repository / "third_party" / "SharpZipLib"
    assert SHARPZIPLIB_COMMIT == "33f64eb0f28cdd2b084cb822fcc224c7c5aba553"
    extractor = MediaArchiveExtractor(
        CancellableProcessRunner(),
        NullLogger(),
        source_resolver=source_resolver,
        repository_root=repository,
    )
    with pytest.raises(ExtractionFailureError) as captured:
        extractor.extract(
            context,
            [voice, wrong_password, traversal, absolute, duplicate, bad_crc],
            concurrency=30,
        )

    assert len(captured.value.failures) == 5
    assert (
        context.workspace.extracted_media / "voice" / "nested" / "first.ogg"
    ).read_bytes() == b"first-content"
    assert (
        context.workspace.extracted_media / "voice" / "second.ogg"
    ).read_bytes() == b"second-content"
    for name in ("wrong", "traversal", "absolute", "duplicate", "bad_crc"):
        assert (
            context.workspace.extracted_media / name / "old.bin"
        ).read_bytes() == b"old"
    assert not (tmp_path / "escape.txt").exists()
    assert not list((context.workspace.temp_state / "media-extractor").glob("job-*"))

    cache_root = (
        context.workspace.tools_cache
        / "media-extractor"
        / media_extractor_cache_fingerprint()
    )
    assert (cache_root / "MediaArchiveExtractor.dll").is_file()
    assert (cache_root / "ICSharpCode.SharpZipLib.dll").is_file()
    dependencies = json.loads(
        (cache_root / "MediaArchiveExtractor.deps.json").read_text(encoding="utf8")
    )
    dependency_names = json.dumps(dependencies)
    assert "ICSharpCode.SharpZipLib/1.4.2" in dependency_names
    assert dependencies["libraries"]["ICSharpCode.SharpZipLib/1.4.2"]["type"] == (
        "project"
    )
    assert "AssetRipper" not in dependency_names
    assert "SharpCompress" not in dependency_names
    projects = tuple(
        (
            repository
            / "src"
            / "ba_downloader"
            / "infrastructure"
            / "extraction"
            / "media"
            / "tool"
            / name
        ).read_text(encoding="utf8")
        for name in ("MediaArchiveExtractor.csproj", "SharpZipLib.Source.csproj")
    )
    assert all("PackageReference" not in project for project in projects)
