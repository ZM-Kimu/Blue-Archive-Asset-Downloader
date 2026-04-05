from __future__ import annotations

import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.tools.dump_backend import (
    CPP2IL_COMMIT,
    EXPORTER_CSPROJ_TEMPLATE_PATH,
    EXPORTER_PROGRAM_CS_PATH,
    Cpp2IlDumpCsBackend,
    Cpp2ILSourceResolver,
    LegacyIl2CppDumperBackend,
    build_default_dumper_backend_registry,
)
from ba_downloader.infrastructure.tools.flatbuffer_workflow import FlatbufferWorkflow


class DummyHttpClient:
    def __init__(self) -> None:
        self.download_calls: list[tuple[str, str]] = []

    def request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        raise AssertionError("request should not be called in dump backend tests.")

    def download_to_file(self, url: str, dest_path: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        _ = kwargs
        self.download_calls.append((url, dest_path))
        raise AssertionError("download_to_file should not be called for this test.")

    def close(self) -> None:
        return None


class ArchiveHttpClient(DummyHttpClient):
    def download_to_file(self, url: str, dest_path: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        _ = kwargs
        self.download_calls.append((url, dest_path))
        archive_root = f"Cpp2IL-{CPP2IL_COMMIT}"
        with ZipFile(dest_path, "w") as archive:
            archive.writestr(f"{archive_root}/Cpp2IL/Cpp2IL.csproj", "<Project />")
            archive.writestr(f"{archive_root}/LibCpp2IL/LibCpp2IL.csproj", "<Project />")


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


def _build_context(tmp_path: Path, *, region: str = "jp") -> RuntimeContext:
    return RuntimeContext(
        region=region,
        threads=1,
        version="",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("table", "media", "bundle"),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _create_cpp2il_tree(root: Path) -> None:
    (root / "Cpp2IL").mkdir(parents=True, exist_ok=True)
    (root / "LibCpp2IL").mkdir(parents=True, exist_ok=True)
    (root / "Cpp2IL" / "Cpp2IL.csproj").write_text("<Project />", encoding="utf8")
    (root / "LibCpp2IL" / "LibCpp2IL.csproj").write_text("<Project />", encoding="utf8")


def test_default_dumper_policy_maps_regions_to_expected_backends() -> None:
    registry = build_default_dumper_backend_registry()
    logger = NullLogger()
    http_client = DummyHttpClient()

    assert isinstance(
        registry.resolve("jp")(http_client, logger),
        Cpp2IlDumpCsBackend,
    )
    assert isinstance(
        registry.resolve("gl")(http_client, logger),
        LegacyIl2CppDumperBackend,
    )
    assert isinstance(
        registry.resolve("cn")(http_client, logger),
        LegacyIl2CppDumperBackend,
    )


def test_flatbuffer_workflow_does_not_fallback_when_jp_backend_fails(
    tmp_path: Path,
) -> None:
    class FailingBackend:
        def dump(self, context: RuntimeContext, output_dir: str) -> None:
            _ = (context, output_dir)
            raise RuntimeError("jp backend failed")

    class ForbiddenBackend:
        called = False

        def dump(self, context: RuntimeContext, output_dir: str) -> None:
            _ = (context, output_dir)
            ForbiddenBackend.called = True

    class Registry:
        def resolve(self, region: str):  # type: ignore[no-untyped-def]
            if region == "jp":
                return lambda http_client, logger: FailingBackend()
            return lambda http_client, logger: ForbiddenBackend()

    workflow = FlatbufferWorkflow(DummyHttpClient(), NullLogger(), Registry())
    context = _build_context(tmp_path, region="jp")

    with pytest.raises(RuntimeError, match="jp backend failed"):
        workflow.dump(context)
    assert ForbiddenBackend.called is False


def test_cpp2il_framework_selection_prefers_net9(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.get_installed_dotnet_sdk_major_versions",
        lambda: {8, 9},
    )
    assert Cpp2IlDumpCsBackend._resolve_framework_order() == ("net9.0", "net8.0")


def test_cpp2il_framework_selection_uses_net8_when_only_net8_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.get_installed_dotnet_sdk_major_versions",
        lambda: {8},
    )
    assert Cpp2IlDumpCsBackend._resolve_framework_order() == ("net8.0",)


def test_cpp2il_framework_selection_raises_without_supported_dotnet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.get_installed_dotnet_sdk_major_versions",
        lambda: {7},
    )
    with pytest.raises(FileNotFoundError, match=r"NET 9 or \.NET 8"):
        Cpp2IlDumpCsBackend._resolve_framework_order()


def test_cpp2il_source_resolver_prefers_submodule_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_repo_root = tmp_path / "repo"
    submodule_root = fake_repo_root / "third_party" / "Cpp2IL"
    _create_cpp2il_tree(submodule_root)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend._repo_root",
        lambda: fake_repo_root,
    )
    resolver = Cpp2ILSourceResolver(DummyHttpClient(), NullLogger())
    context = _build_context(tmp_path)

    resolved = resolver.resolve(context)

    assert resolved == submodule_root


def test_cpp2il_source_resolver_uses_cache_when_submodule_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_repo_root = tmp_path / "repo"
    fake_repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend._repo_root",
        lambda: fake_repo_root,
    )

    context = _build_context(tmp_path)
    cache_root = (
        Path(context.work_dir)
        / ".ba-downloader"
        / "tools"
        / f"Cpp2IL-{CPP2IL_COMMIT[:12]}"
    )
    _create_cpp2il_tree(cache_root)

    resolver = Cpp2ILSourceResolver(DummyHttpClient(), NullLogger())
    resolved = resolver.resolve(context)
    assert resolved == cache_root


def test_cpp2il_source_resolver_downloads_and_reuses_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_repo_root = tmp_path / "repo"
    fake_repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend._repo_root",
        lambda: fake_repo_root,
    )

    http_client = ArchiveHttpClient()
    resolver = Cpp2ILSourceResolver(http_client, NullLogger())
    context = _build_context(tmp_path)

    first = resolver.resolve(context)
    second = resolver.resolve(context)

    assert first == second
    assert (first / "Cpp2IL" / "Cpp2IL.csproj").exists()
    assert len(http_client.download_calls) == 1


def test_cpp2il_exporter_project_is_generated_from_template_files(tmp_path: Path) -> None:
    context = _build_context(tmp_path, region="jp")
    cpp2il_root = tmp_path / "Cpp2IL"
    _create_cpp2il_tree(cpp2il_root)

    project_path = Cpp2IlDumpCsBackend._ensure_exporter_project(context, cpp2il_root)

    assert EXPORTER_CSPROJ_TEMPLATE_PATH.exists()
    assert EXPORTER_PROGRAM_CS_PATH.exists()
    assert "LibCpp2IL.csproj" in project_path.read_text(encoding="utf8")
    assert (project_path.parent / "Program.cs").read_text(encoding="utf8").startswith(
        "using System.Reflection;"
    )


def test_legacy_backend_logs_success_at_info_level(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeDumper:
        def get_il2cpp_dumper(self, http_client, temp_dir):  # type: ignore[no-untyped-def]
            _ = (http_client, temp_dir)

        def dump_il2cpp(self, output_dir, il2cpp_path, metadata_path, max_retries):  # type: ignore[no-untyped-def]
            _ = (output_dir, il2cpp_path, metadata_path, max_retries)

    context = _build_context(tmp_path, region="gl")
    temp_dir = Path(context.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "libil2cpp.so").write_bytes(b"binary")
    (temp_dir / "global-metadata.dat").write_bytes(b"metadata")
    logger = RecordingLogger()
    backend = LegacyIl2CppDumperBackend(DummyHttpClient(), logger)

    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.IL2CppDumper",
        lambda: FakeDumper(),
    )

    backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))

    assert logger.info_messages == [
        "Downloading il2cpp-dumper...",
        "Trying to dump il2cpp...",
        "Dumped il2cpp binary file successfully.",
    ]
    assert logger.warn_messages == []


def test_cpp2il_backend_logs_framework_retry_as_warning_and_success_as_info(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="jp")
    temp_dir = Path(context.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "GameAssembly.dll").write_bytes(b"binary")
    (temp_dir / "global-metadata.dat").write_bytes(b"metadata")
    logger = RecordingLogger()
    backend = Cpp2IlDumpCsBackend(DummyHttpClient(), logger)
    exporter_project = tmp_path / "DumpCsExporter.csproj"
    exporter_project.write_text("<Project />", encoding="utf8")
    run_calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        run_calls.append(command)
        if len(run_calls) == 1:
            raise subprocess.CalledProcessError(
                1,
                command,
                stderr="net9 failed",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(backend.source_resolver, "resolve", lambda _context: tmp_path / "Cpp2IL")
    monkeypatch.setattr(backend, "_ensure_exporter_project", lambda *_args, **_kwargs: exporter_project)
    monkeypatch.setattr(backend, "_resolve_unity_version", lambda *_args, **_kwargs: "2021.3.36f1")
    monkeypatch.setattr(backend, "_resolve_framework_order", lambda: ("net9.0", "net8.0"))
    monkeypatch.setattr("ba_downloader.infrastructure.tools.dump_backend.subprocess.run", fake_run)

    backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))

    assert logger.warn_messages == [
        "Retrying Cpp2IL exporter with framework net8.0.",
    ]
    assert logger.info_messages == ["Dumped il2cpp binary file successfully."]
    assert len(run_calls) == 2
