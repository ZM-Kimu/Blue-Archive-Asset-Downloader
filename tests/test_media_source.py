from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Event
from zipfile import ZipFile

from ba_downloader.infrastructure.extraction.media.source import (
    SharpZipLibSourceResolver,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from support.fixtures import build_execution_context


class ArchiveHttpClient:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0

    def download_to_file(self, _url: str, destination: str) -> None:
        self.calls += 1
        Path(destination).write_bytes(self.payload)


class BlockingArchiveHttpClient(ArchiveHttpClient):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.download_started = Event()
        self.release_download = Event()

    def download_to_file(self, url: str, destination: str) -> None:
        self.download_started.set()
        assert self.release_download.wait(timeout=10)
        super().download_to_file(url, destination)


def _create_source_tree(root: Path) -> None:
    source = root / "src" / "ICSharpCode.SharpZipLib"
    (source / "Zip").mkdir(parents=True)
    (source / "Checksum").mkdir()
    (source / "ICSharpCode.SharpZipLib.csproj").write_text(
        "<Project />\n", encoding="utf8"
    )
    (source / "Zip" / "ZipFile.cs").write_text(
        "namespace ICSharpCode.SharpZipLib.Zip;\n", encoding="utf8"
    )
    (source / "Checksum" / "Crc32.cs").write_text(
        "namespace ICSharpCode.SharpZipLib.Checksum;\n", encoding="utf8"
    )


def _source_archive(source_root: Path, *, prefix: str = "SharpZipLib-source") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            archive.write(
                source, f"{prefix}/{source.relative_to(source_root).as_posix()}"
            )
    return buffer.getvalue()


def test_source_resolver_prefers_submodule(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    submodule = repository / "third_party" / "SharpZipLib"
    _create_source_tree(submodule)
    http = ArchiveHttpClient(b"unused")
    resolver = SharpZipLibSourceResolver(
        http,  # type: ignore[arg-type]
        NullLogger(),
        repository_root=repository,
    )

    resolved = resolver.resolve(build_execution_context(tmp_path / "workspace"))

    assert resolved == submodule
    assert http.calls == 0


def test_source_resolver_downloads_and_reuses_fallback_archive(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    _create_source_tree(fixture)
    payload = _source_archive(fixture)
    http = ArchiveHttpClient(payload)
    context = build_execution_context(tmp_path / "workspace")
    resolver = SharpZipLibSourceResolver(
        http,  # type: ignore[arg-type]
        NullLogger(),
        repository_root=tmp_path / "missing-repository",
    )

    first = resolver.resolve(context)
    second = resolver.resolve(context)

    assert first == second
    assert (first / "src/ICSharpCode.SharpZipLib/Zip/ZipFile.cs").is_file()
    assert http.calls == 1


def test_concurrent_fallback_resolution_downloads_source_once(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    _create_source_tree(fixture)
    payload = _source_archive(fixture)
    http = BlockingArchiveHttpClient(payload)
    context = build_execution_context(tmp_path / "workspace")
    resolver = SharpZipLibSourceResolver(
        http,  # type: ignore[arg-type]
        NullLogger(),
        repository_root=tmp_path / "missing-repository",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_result = executor.submit(resolver.resolve, context)
        assert http.download_started.wait(timeout=10)
        second_result = executor.submit(resolver.resolve, context)
        http.release_download.set()
        first_source = first_result.result(timeout=10)
        second_source = second_result.result(timeout=10)

    assert first_source == second_source
    assert http.calls == 1
