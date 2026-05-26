from __future__ import annotations

import subprocess
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow
from ba_downloader.infrastructure.tools.dump_backend import (
    CPP2IL_COMMIT,
    EXPORTER_CSPROJ_TEMPLATE_PATH,
    EXPORTER_PROGRAM_CS_PATH,
    CnMetadataDumpBackend,
    CnMetadataDumpError,
    Cpp2IlDumpCsBackend,
    Cpp2ILSourceResolver,
    build_default_dumper_backend_registry,
)


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
            archive.writestr(
                f"{archive_root}/LibCpp2IL/LibCpp2IL.csproj", "<Project />"
            )


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


class FakePopen:
    def __init__(
        self,
        command: list[str],
        *,
        stdout_text: str = "",
        stderr_text: str = "",
        returncode: int = 0,
    ) -> None:
        self.command = command
        self.stdout = StringIO(stdout_text)
        self.stderr = StringIO(stderr_text)
        self.returncode = returncode

    def wait(self) -> int:
        return self.returncode

    def __enter__(self) -> FakePopen:
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> bool:  # type: ignore[no-untyped-def]
        _ = (exc_type, exc, exc_tb)
        return False


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
        Cpp2IlDumpCsBackend,
    )
    assert isinstance(
        registry.resolve("cn")(http_client, logger),
        CnMetadataDumpBackend,
    )


def test_schema_workflow_does_not_fallback_when_jp_backend_fails(
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

    workflow = SchemaWorkflow(DummyHttpClient(), NullLogger(), Registry())
    context = _build_context(tmp_path, region="jp")

    with pytest.raises(RuntimeError, match="jp backend failed"):
        workflow.dump(context)
    assert ForbiddenBackend.called is False


def test_cpp2il_framework_selection_requires_net10(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.get_installed_dotnet_sdk_major_versions",
        lambda: {8, 9, 10},
    )
    assert Cpp2IlDumpCsBackend._resolve_framework() == "net10.0"


def test_cpp2il_framework_selection_rejects_older_dotnet_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.get_installed_dotnet_sdk_major_versions",
        lambda: {8, 9},
    )
    with pytest.raises(FileNotFoundError, match=r"\.NET 10 SDK"):
        Cpp2IlDumpCsBackend._resolve_framework()


def test_tools_package_does_not_export_legacy_il2cpp_dumper() -> None:
    from ba_downloader.infrastructure import tools

    assert "IL2CppDumper" not in tools.__all__
    assert "LegacyIl2CppDumperBackend" not in tools.__all__
    assert not hasattr(tools, "IL2CppDumper")
    assert not hasattr(tools, "LegacyIl2CppDumperBackend")


def test_dump_backend_module_does_not_export_legacy_il2cpp_dumper() -> None:
    from ba_downloader.infrastructure.tools import dump_backend

    assert not hasattr(dump_backend, "IL2CppDumper")
    assert not hasattr(dump_backend, "LegacyIl2CppDumperBackend")


def test_legacy_il2cpp_dumper_module_is_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("ba_downloader.infrastructure.tools.il2cpp_dumper")


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


def test_cpp2il_exporter_project_targets_selected_framework(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="jp")
    cpp2il_root = tmp_path / "Cpp2IL"
    _create_cpp2il_tree(cpp2il_root)

    project_path = Cpp2IlDumpCsBackend._ensure_exporter_project(
        context,
        cpp2il_root,
        "net10.0",
    )

    project_text = project_path.read_text(encoding="utf8")
    assert EXPORTER_CSPROJ_TEMPLATE_PATH.exists()
    assert EXPORTER_PROGRAM_CS_PATH.exists()
    assert "<TargetFramework>net10.0</TargetFramework>" in project_text
    assert "<TargetFrameworks>" not in project_text
    assert "LibCpp2IL.csproj" in project_text
    assert 'SetTargetFramework="TargetFramework=net10.0"' in project_text
    assert (
        (project_path.parent / "Program.cs")
        .read_text(encoding="utf8")
        .startswith("using System.Reflection;")
    )


def test_cpp2il_backend_uses_single_net10_framework_and_logs_success_as_info(
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
    ensure_calls: list[str] = []

    def fake_run(command: list[str], **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        run_calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        backend.source_resolver, "resolve", lambda _context: tmp_path / "Cpp2IL"
    )

    def fake_ensure_exporter_project(
        _context: RuntimeContext,
        _cpp2il_root: Path,
        framework: str,
    ) -> Path:
        ensure_calls.append(framework)
        return exporter_project

    monkeypatch.setattr(
        backend,
        "_ensure_exporter_project",
        fake_ensure_exporter_project,
    )
    monkeypatch.setattr(
        backend, "_resolve_unity_version", lambda *_args, **_kwargs: "2021.3.36f1"
    )
    monkeypatch.setattr(backend, "_resolve_framework", lambda: "net10.0")
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.subprocess.run", fake_run
    )

    backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))

    assert logger.warn_messages == []
    assert logger.info_messages == ["Dumped il2cpp binary file successfully."]
    assert ensure_calls == ["net10.0"]
    assert len(run_calls) == 1
    assert "--framework" in run_calls[0]
    assert "net10.0" in run_calls[0]
    assert (
        f"--formatter-output="
        f"{(tmp_path / 'Extracted' / 'Dumps' / 'memorypack_formatters.json').resolve()}"
    ) in run_calls[-1]


def test_cn_metadata_backend_uses_metadata_only_exporter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    metadata_dir = Path(context.temp_dir) / "CN_Metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / "global-metadata.dat"
    metadata_path.write_bytes(b"metadata")
    logger = RecordingLogger()
    backend = CnMetadataDumpBackend(DummyHttpClient(), logger)
    popen_calls: list[list[str]] = []

    def fake_popen(command: list[str], **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        popen_calls.append(command)
        return FakePopen(
            command,
            stdout_text="exporter started\nexporter finished\n",
            stderr_text=(
                "[############............] [1/2] parse metadata\n"
                "    member signature build [#############.....] 70% (20147/28491,  20983/s)\n"
            ),
        )

    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        CnMetadataDumpBackend,
        "_resolve_project_path",
        staticmethod(lambda: tmp_path / "third_party" / "cn_metadata_exporter.csproj"),
    )

    backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))

    assert logger.info_messages[0] == "Trying to dump CN metadata..."
    assert logger.info_messages[-1] == "Dumped CN metadata successfully."
    assert "exporter started" in logger.info_messages
    assert "exporter finished" in logger.info_messages
    assert "[############............] [1/2] parse metadata" in logger.info_messages
    assert all(
        "member signature build" not in message for message in logger.info_messages
    )
    assert logger.warn_messages == []
    assert popen_calls == [
        [
            "dotnet",
            "run",
            "--project",
            str(tmp_path / "third_party" / "cn_metadata_exporter.csproj"),
            "-c",
            "Release",
            "--",
            "--metadata",
            str(metadata_path.resolve()),
            "--output",
            str((tmp_path / "Extracted" / "Dumps" / "dump.cs").resolve()),
            "--formatter-output",
            str(
                (
                    tmp_path / "Extracted" / "Dumps" / "memorypack_formatters.json"
                ).resolve()
            ),
        ]
    ]


def test_cn_metadata_backend_raises_on_exporter_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    metadata_dir = Path(context.temp_dir) / "CN_Metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "global-metadata.dat").write_bytes(b"metadata")
    logger = RecordingLogger()
    backend = CnMetadataDumpBackend(DummyHttpClient(), logger)

    def fake_popen(command: list[str], **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return FakePopen(
            command,
            stdout_text="phase 1\n",
            stderr_text=(
                "    member signature build [#############.....] 70% (20147/28491,  20983/s)\n"
                "dump failed\n"
            ),
            returncode=1,
        )

    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        CnMetadataDumpBackend,
        "_resolve_project_path",
        staticmethod(lambda: tmp_path / "third_party" / "cn_metadata_exporter.csproj"),
    )

    with pytest.raises(CnMetadataDumpError, match="dump failed"):
        backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))
    assert logger.info_messages == [
        "Trying to dump CN metadata...",
        "phase 1",
    ]
    assert logger.warn_messages == ["dump failed"]


def test_cn_metadata_backend_propagates_startup_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    metadata_dir = Path(context.temp_dir) / "CN_Metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "global-metadata.dat").write_bytes(b"metadata")
    backend = CnMetadataDumpBackend(DummyHttpClient(), RecordingLogger())

    def fake_popen(command: list[str], **kwargs):  # type: ignore[no-untyped-def]
        _ = (command, kwargs)
        raise FileNotFoundError("dotnet not found")

    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        CnMetadataDumpBackend,
        "_resolve_project_path",
        staticmethod(lambda: tmp_path / "third_party" / "cn_metadata_exporter.csproj"),
    )

    with pytest.raises(FileNotFoundError, match="dotnet not found"):
        backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))
