from __future__ import annotations

import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow
from ba_downloader.infrastructure.tools.cn_metadata_recovery import (
    CnMetadataRecoveryError,
    CnMetadataRecoveryResult,
)
from ba_downloader.infrastructure.tools.dump_backend import (
    CPP2IL_COMMIT,
    EXPORTER_CSPROJ_TEMPLATE_PATH,
    EXPORTER_PROGRAM_CS_PATH,
    CnMetadataRecoveryDumpBackend,
    CnMetadataRecoveryDumpError,
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
        _write_cpp2il_archive(Path(dest_path))


class FlakyArchiveHttpClient(DummyHttpClient):
    def download_to_file(self, url: str, dest_path: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        _ = kwargs
        self.download_calls.append((url, dest_path))
        if len(self.download_calls) == 1:
            Path(dest_path).write_bytes(b"PK\x03\x04truncated")
            return
        _write_cpp2il_archive(Path(dest_path))


class TraversalArchiveHttpClient(DummyHttpClient):
    def download_to_file(self, url: str, dest_path: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        _ = kwargs
        self.download_calls.append((url, dest_path))
        with ZipFile(dest_path, "w") as archive:
            archive.writestr("../escape.txt", "owned")


class HashMismatchArchiveHttpClient(ArchiveHttpClient):
    pass


class StaticSourceResolver:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.contexts: list[RuntimeContext] = []

    def resolve(self, context: RuntimeContext) -> Path:
        self.contexts.append(context)
        return self.root


def _write_cpp2il_archive(dest_path: Path) -> None:
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
        Cpp2IlDumpCsBackend,
    )
    assert isinstance(
        registry.resolve("cn")(http_client, logger),
        CnMetadataRecoveryDumpBackend,
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


def test_schema_workflow_builds_supplemental_memorypack_formatters(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    dumps_dir = Path(context.extract_dir) / "Dumps"
    dumps_dir.mkdir(parents=True, exist_ok=True)
    (dumps_dir / "dump.cs").write_text(
        """// Namespace: FlatData
public struct CharacterExcel : FlatBuffers.IFlatbufferObject // TypeDefIndex: 1 Token: 0x02000001
{
}

// Namespace: MX.GameData.DAO.Battle
public abstract class LogicEffectDAO : MemoryPack.IMemoryPackable`1<MX.GameData.DAO.Battle.LogicEffectDAO>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 10 Token: 0x0200000A
{
    // Properties
    public System.Int32 Level { get; set; } // Token: 0x17000001
    public FlatData.LogicEffectCategory Category { get; set; } // Token: 0x17000002
}

// Namespace: MX.GameData.DAO.Battle
public class DamageEffectDAO : MX.GameData.DAO.Battle.LogicEffectDAO, MemoryPack.IMemoryPackable`1<MX.GameData.DAO.Battle.DamageEffectDAO>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 11 Token: 0x0200000B
{
    // Properties
    public System.String TemplateId { get; set; } // Token: 0x17000003
}
""",
        encoding="utf8",
    )
    (dumps_dir / "memorypack_formatters.json").write_text(
        json.dumps(
            {
                "version": 1,
                "formatters": [
                    {
                        "target_type": "MX.GameData.DAO.Battle.LogicEffectDAO",
                        "kind": "union",
                        "tag_type": "byte",
                        "union_tags": {"17": "MX.GameData.DAO.Battle.DamageEffectDAO"},
                    }
                ],
            }
        ),
        encoding="utf8",
    )
    workflow = SchemaWorkflow(DummyHttpClient(), NullLogger())

    workflow.compile(context)

    sidecar = json.loads((dumps_dir / "memorypack_formatters.json").read_text())
    formatter_map = {
        formatter["target_type"]: formatter for formatter in sidecar["formatters"]
    }
    damage = formatter_map["MX.GameData.DAO.Battle.DamageEffectDAO"]
    assert damage["kind"] == "object"
    assert damage["members"][0]["name"] == "Level"
    assert damage["members"][1]["name"] == "Category"
    assert damage["members"][1]["wire_type"] == "int32_enum"
    assert damage["members"][2]["name"] == "TemplateId"


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
    resolver = Cpp2ILSourceResolver(
        http_client,
        NullLogger(),
        archive_sha256="",
    )
    context = _build_context(tmp_path)

    first = resolver.resolve(context)
    second = resolver.resolve(context)

    assert first == second
    assert (first / "Cpp2IL" / "Cpp2IL.csproj").exists()
    assert len(http_client.download_calls) == 1


def test_cpp2il_source_resolver_retries_truncated_fallback_archive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_repo_root = tmp_path / "repo"
    fake_repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend._repo_root",
        lambda: fake_repo_root,
    )

    http_client = FlakyArchiveHttpClient()
    resolver = Cpp2ILSourceResolver(
        http_client,
        NullLogger(),
        archive_sha256="",
    )
    context = _build_context(tmp_path)

    resolved = resolver.resolve(context)

    assert (resolved / "Cpp2IL" / "Cpp2IL.csproj").exists()
    assert len(http_client.download_calls) == 2


def test_cpp2il_source_resolver_rejects_archive_path_traversal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_repo_root = tmp_path / "repo"
    fake_repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend._repo_root",
        lambda: fake_repo_root,
    )

    resolver = Cpp2ILSourceResolver(
        TraversalArchiveHttpClient(),
        NullLogger(),
        archive_sha256="",
    )
    context = _build_context(tmp_path)

    with pytest.raises(FileNotFoundError, match="unsafe path"):
        resolver.resolve(context)
    assert not (tmp_path / "escape.txt").exists()


def test_cpp2il_source_resolver_rejects_archive_checksum_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_repo_root = tmp_path / "repo"
    fake_repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend._repo_root",
        lambda: fake_repo_root,
    )

    resolver = Cpp2ILSourceResolver(
        HashMismatchArchiveHttpClient(),
        NullLogger(),
        archive_sha256="0" * 64,
    )
    context = _build_context(tmp_path)

    with pytest.raises(FileNotFoundError, match="checksum"):
        resolver.resolve(context)


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
    assert "Cpp2IL.Core.csproj" not in project_text
    assert "LibCpp2IL.csproj" in project_text
    assert 'SetTargetFramework="TargetFramework=net10.0"' in project_text
    program_text = (project_path.parent / "Program.cs").read_text(encoding="utf8")
    assert program_text.startswith("using System.Reflection;")
    assert "if (options.EnableCnMetadataRecoveryShim)" in program_text
    assert "CnMetadataRecoveryInputShim.Register();" in program_text
    assert "memorypack_union_attrs.json" in program_text
    shim_text = (project_path.parent / "CnMetadataRecoveryInputShim.cs").read_text(
        encoding="utf8"
    )
    assert "Il2CppBinary.OnRegistrationStructLocationFailure" in shim_text
    assert "private static bool IsRegistered" in shim_text
    assert "if (IsRegistered)" in shim_text
    assert "auto-scanned" in shim_text


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


class RecordingMetadataRecoveryPipeline:
    def __init__(self, standard_v29_metadata: bytes = b"standard v29 metadata") -> None:
        self.standard_v29_metadata = standard_v29_metadata
        self.calls: list[tuple[bytes, Path]] = []

    def run(
        self,
        *,
        protected_metadata: bytes,
        binary_path: Path,
    ) -> CnMetadataRecoveryResult:
        self.calls.append((protected_metadata, binary_path))
        return CnMetadataRecoveryResult(
            standard_v29_metadata=self.standard_v29_metadata,
            validation_summary={"valid": True, "errorCount": 0, "warningCount": 0},
        )


def test_cn_metadata_recovery_backend_runs_pipeline_and_writes_only_final_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    metadata_dir = Path(context.temp_dir) / "CN_Metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / "global-metadata.dat"
    metadata_path.write_bytes(b"metadata")
    runtime_dir = Path(context.temp_dir) / "CN_Runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    binary_path = runtime_dir / "libil2cpp.so"
    binary_path.write_bytes(b"binary")
    (runtime_dir / "globalgamemanagers").write_bytes(b"Unity 2021.3.45f1")

    logger = RecordingLogger()
    cpp2il_root = tmp_path / "fallback" / "Cpp2IL"
    source_resolver = StaticSourceResolver(cpp2il_root)
    final_metadata_path = (
        Path(context.temp_dir)
        / "CN_MetadataRecovery"
        / "global-metadata.standard-v29.dat"
    )
    pipeline = RecordingMetadataRecoveryPipeline()
    backend = CnMetadataRecoveryDumpBackend(
        DummyHttpClient(),
        logger,
        source_resolver,
        recovery_pipeline=pipeline,
    )
    exporter_project = tmp_path / "DumpCsExporter.csproj"
    exporter_project.write_text("<Project />", encoding="utf8")
    run_calls: list[list[str]] = []
    ensure_calls: list[str] = []

    def fake_run(command: list[str], **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        run_calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

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
    monkeypatch.setattr(backend, "_resolve_framework", lambda: "net10.0")
    monkeypatch.setattr(
        "ba_downloader.infrastructure.tools.dump_backend.subprocess.run", fake_run
    )

    backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))

    assert logger.warn_messages == []
    assert logger.info_messages == [
        "Recovered CN metadata successfully.",
        "Dumped CN metadata recovery il2cpp binary file successfully.",
    ]
    assert ensure_calls == ["net10.0"]
    assert pipeline.calls == [(b"metadata", binary_path)]
    assert final_metadata_path.read_bytes() == b"standard v29 metadata"
    assert sorted(path.name for path in final_metadata_path.parent.iterdir()) == [
        "global-metadata.standard-v29.dat"
    ]
    assert run_calls == [
        [
            "dotnet",
            "run",
            "--project",
            str(exporter_project),
            "--framework",
            "net10.0",
            "--",
            f"--binary-path={binary_path.resolve()}",
            f"--metadata-path={final_metadata_path.resolve()}",
            "--unity-version=2021.3.45f1",
            f"--output={(tmp_path / 'Extracted' / 'Dumps' / 'dump.cs').resolve()}",
            f"--formatter-output="
            f"{(tmp_path / 'Extracted' / 'Dumps' / 'memorypack_formatters.json').resolve()}",
            "--enable-cn-metadata-recovery-shim",
        ]
    ]
    assert source_resolver.contexts == [context]


def test_cn_metadata_recovery_backend_raises_actionable_pipeline_error(
    tmp_path: Path,
) -> None:
    class FailingPipeline:
        def run(
            self,
            *,
            protected_metadata: bytes,
            binary_path: Path,
        ) -> CnMetadataRecoveryResult:
            _ = (protected_metadata, binary_path)
            raise CnMetadataRecoveryError(
                "sanitize_default_values",
                "default value section is invalid",
            )

    context = _build_context(tmp_path, region="cn")
    metadata_dir = Path(context.temp_dir) / "CN_Metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "global-metadata.dat").write_bytes(b"metadata")
    runtime_dir = Path(context.temp_dir) / "CN_Runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "libil2cpp.so").write_bytes(b"binary")
    (runtime_dir / "globalgamemanagers").write_bytes(b"Unity 2021.3.45f1")
    logger = RecordingLogger()
    backend = CnMetadataRecoveryDumpBackend(
        DummyHttpClient(),
        logger,
        StaticSourceResolver(tmp_path / "Cpp2IL"),
        recovery_pipeline=FailingPipeline(),
    )

    with pytest.raises(CnMetadataRecoveryDumpError, match="sanitize_default_values"):
        backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))


def test_cn_metadata_recovery_backend_requires_prepared_metadata_and_binary(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    metadata_dir = Path(context.temp_dir) / "CN_Metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "global-metadata.dat").write_bytes(b"metadata")
    backend = CnMetadataRecoveryDumpBackend(
        DummyHttpClient(),
        RecordingLogger(),
        StaticSourceResolver(tmp_path / "Cpp2IL"),
    )

    with pytest.raises(FileNotFoundError, match="CN metadata recovery binary"):
        backend.dump(context, str(tmp_path / "Extracted" / "Dumps"))
