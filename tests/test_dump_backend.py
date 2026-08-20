from __future__ import annotations

import json
from pathlib import Path
from threading import Event
from zipfile import ZipFile

import pytest

from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.ports.execution import EventCancellation, NeverCancelled
from ba_downloader.domain.ports.process import ProcessCommand, ProcessResult
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.regions.cn.dump_backend import (
    CnMetadataRecoveryDumpBackend,
    CnMetadataRecoveryDumpError,
)
from ba_downloader.infrastructure.schema.workflow import SchemaWorkflow
from ba_downloader.infrastructure.tools.cn_metadata_recovery import (
    CnMetadataRecoveryError,
    CnMetadataRecoveryResult,
)
from ba_downloader.infrastructure.tools.dump_backend import (
    CPP2IL_COMMIT,
    EXPORTER_CSPROJ_TEMPLATE_PATH,
    EXPORTER_PROGRAM_CS_PATH,
    Cpp2IlDumpCsBackend,
    Cpp2ILSourceResolver,
)
from support.fixtures import build_execution_context


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
        self.contexts: list[ExecutionContext] = []

    def resolve(self, context: ExecutionContext) -> Path:
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


def _build_context(tmp_path: Path, *, region: str = "jp") -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region=region,
        version="1.2.3",
        max_retries=1,
    )


def _create_cpp2il_tree(root: Path) -> None:
    (root / "Cpp2IL").mkdir(parents=True, exist_ok=True)
    (root / "LibCpp2IL").mkdir(parents=True, exist_ok=True)
    (root / "Cpp2IL" / "Cpp2IL.csproj").write_text("<Project />", encoding="utf8")
    (root / "LibCpp2IL" / "LibCpp2IL.csproj").write_text("<Project />", encoding="utf8")


def _prepared_runtime(
    context: ExecutionContext,
    *,
    binary_name: str = "libil2cpp.so",
) -> PreparedRuntimeAssets:
    runtime_dir = context.workspace.temp_state / context.resource_version / "Runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    binary_path = runtime_dir / binary_name
    binary_path.write_bytes(b"binary")
    metadata_path = runtime_dir / "global-metadata.dat"
    metadata_path.write_bytes(b"metadata")
    managers_path = runtime_dir / "globalgamemanagers"
    managers_path.write_bytes(b"Unity 2021.3.45f1")
    return PreparedRuntimeAssets(
        version=context.resource_version,
        root_dir=runtime_dir,
        binary_path=binary_path,
        metadata_path=metadata_path,
        globalgamemanagers_path=managers_path,
    )


def test_default_dumper_policy_maps_regions_to_expected_backends(
    tmp_path: Path,
) -> None:
    logger = NullLogger()
    http_client = DummyHttpClient()

    assert isinstance(
        DEFAULT_REGION_GATEWAY_REGISTRY.resolve("jp").runtime.dump_backend(
            http_client, logger, NeverCancelled()
        ),
        Cpp2IlDumpCsBackend,
    )
    gl_backend = DEFAULT_REGION_GATEWAY_REGISTRY.resolve("gl").runtime.dump_backend(
        http_client, logger, NeverCancelled()
    )
    assert isinstance(gl_backend, Cpp2IlDumpCsBackend)
    assert isinstance(
        DEFAULT_REGION_GATEWAY_REGISTRY.resolve("cn").runtime.dump_backend(
            http_client, logger, NeverCancelled()
        ),
        CnMetadataRecoveryDumpBackend,
    )


def test_schema_workflow_does_not_fallback_when_jp_backend_fails(
    tmp_path: Path,
) -> None:
    class FailingBackend:
        def dump(
            self,
            context: ExecutionContext,
            output_dir: str,
            runtime_assets: PreparedRuntimeAssets,
        ) -> None:
            _ = (context, output_dir, runtime_assets)
            raise RuntimeError("jp backend failed")

    workflow = SchemaWorkflow(
        DummyHttpClient(),
        NullLogger(),
        dumper_backend_factory=lambda _http_client, _logger, _cancellation: (
            FailingBackend()
        ),
    )
    context = _build_context(tmp_path, region="jp")
    runtime_assets = _prepared_runtime(context)

    with pytest.raises(RuntimeError, match="jp backend failed"):
        workflow.dump(context, runtime_assets)


def test_schema_workflow_discards_cancelled_staging_snapshot(
    tmp_path: Path,
) -> None:
    class CancellingBackend:
        def dump(
            self,
            context: ExecutionContext,
            output_dir: str,
            runtime_assets: PreparedRuntimeAssets,
        ) -> None:
            _ = (context, runtime_assets)
            output = Path(output_dir)
            output.mkdir(parents=True, exist_ok=True)
            (output / "dump.cs").write_text("new", encoding="utf8")
            cancellation_event.set()

    cancellation_event = Event()
    context = _build_context(tmp_path, region="jp")
    dumps_dir = context.workspace.dumps
    dumps_dir.mkdir(parents=True)
    (dumps_dir / "dump.cs").write_text("previous", encoding="utf8")
    workflow = SchemaWorkflow(
        DummyHttpClient(),
        NullLogger(),
        dumper_backend_factory=lambda _http, _logger, _cancel: CancellingBackend(),
        cancellation=EventCancellation(cancellation_event),
    )

    with pytest.raises(Exception, match="cancelled"):
        workflow.dump(context, _prepared_runtime(context))

    assert (dumps_dir / "dump.cs").read_text(encoding="utf8") == "previous"
    assert not (context.workspace.extracted / ".staging").exists()


def test_schema_workflow_reuses_matching_runtime_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dump_calls = 0

    class Backend:
        def dump(
            self,
            context: ExecutionContext,
            output_dir: str,
            runtime_assets: PreparedRuntimeAssets,
        ) -> None:
            nonlocal dump_calls
            _ = (context, runtime_assets)
            dump_calls += 1
            output = Path(output_dir)
            output.mkdir(parents=True)
            (output / "dump.cs").write_text("dump", encoding="utf8")

    def compile_artifacts(root: Path) -> None:
        for relative in ("schemas/flatbuffers", "schemas/memorypack"):
            directory = root / relative
            directory.mkdir(parents=True)
            (directory / "schema.py").write_text("VALUE = 1\n", encoding="utf8")

    context = _build_context(tmp_path, region="jp")
    runtime = _prepared_runtime(context)
    first = SchemaWorkflow(
        DummyHttpClient(),
        NullLogger(),
        dumper_backend_factory=lambda *_: Backend(),
    )
    monkeypatch.setattr(first, "_compile", compile_artifacts)
    first.dump(context, runtime)
    first.compile(context)

    second = SchemaWorkflow(
        DummyHttpClient(),
        NullLogger(),
        dumper_backend_factory=lambda *_: Backend(),
    )
    monkeypatch.setattr(
        second,
        "_compile",
        lambda _context: pytest.fail("cached schema must not be compiled"),
    )
    second.dump(context, runtime)
    second.compile(context)

    assert dump_calls == 1
    assert (context.workspace.dumps / "dump.cs").read_text() == "dump"


def test_schema_workflow_dump_requires_configured_backend(tmp_path: Path) -> None:
    workflow = SchemaWorkflow(DummyHttpClient(), NullLogger())
    context = _build_context(tmp_path, region="jp")
    runtime_assets = _prepared_runtime(context)

    with pytest.raises(ValueError, match="dumper backend"):
        workflow.dump(context, runtime_assets)


def test_schema_workflow_builds_supplemental_memorypack_formatters(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    dumps_dir = context.workspace.dumps
    dumps_dir.mkdir(parents=True, exist_ok=True)
    (dumps_dir / "dump.cs").write_text(
        """// Namespace: FlatData
public struct CharacterExcel : FlatBuffers.IFlatbufferObject // TypeDefIndex: 1 Token: 0x02000001
{
}

// Namespace: MX.GameData.DAO.Battle
public abstract class LogicEffectDAO : MemoryPack.IMemoryPackable`1<MX.GameData.DAO.Battle.LogicEffectDAO>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 10 Token: 0x0200000A
{
    // Fields
    private System.Int32 <Level>k__BackingField; // Token: 0x04000001
    private FlatData.LogicEffectCategory <Category>k__BackingField; // Token: 0x04000002
    // Properties
    public System.Int32 Level { get; set; } // Token: 0x17000001
    public FlatData.LogicEffectCategory Category { get; set; } // Token: 0x17000002
}

// Namespace: MX.GameData.DAO.Battle
public class DamageEffectDAO : MX.GameData.DAO.Battle.LogicEffectDAO, MemoryPack.IMemoryPackable`1<MX.GameData.DAO.Battle.DamageEffectDAO>, MemoryPack.IMemoryPackFormatterRegister // TypeDefIndex: 11 Token: 0x0200000B
{
    // Fields
    private System.String <TemplateId>k__BackingField; // Token: 0x04000003
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
    cache_root = context.workspace.tools_cache / f"Cpp2IL-{CPP2IL_COMMIT[:12]}"
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
    assert "RegisterCnMetadataRecoveryShim();" in program_text
    assert "memorypack_union_attrs.json" in program_text
    assert 'Regex.Replace(raw, @"`\\d+", string.Empty)' in program_text
    assert "TryConvertUnionTag" in program_text
    assert "IL2CPP_TYPE_ENUM => ReadCustomAttributeEnum(reader)" in program_text
    assert not (project_path.parent / "CnMetadataRecoveryInputShim.cs").exists()


def test_cpp2il_backend_uses_single_net10_framework_and_logs_success_as_info(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="jp")
    runtime_assets = _prepared_runtime(context, binary_name="GameAssembly.dll")
    logger = RecordingLogger()
    backend = Cpp2IlDumpCsBackend(DummyHttpClient(), logger)
    exporter_project = tmp_path / "DumpCsExporter.csproj"
    exporter_project.write_text("<Project />", encoding="utf8")
    run_calls: list[ProcessCommand] = []
    ensure_calls: list[str] = []

    def fake_run(command: ProcessCommand) -> ProcessResult:
        run_calls.append(command)
        return ProcessResult(command, 0, "", "")

    monkeypatch.setattr(
        backend.source_resolver, "resolve", lambda _context: tmp_path / "Cpp2IL"
    )

    def fake_ensure_exporter_project(
        _context: ExecutionContext,
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
    monkeypatch.setattr(backend.process_runner, "run", fake_run)

    backend.dump(
        context,
        str(tmp_path / "Extracted" / "Dumps"),
        runtime_assets,
    )

    assert logger.warn_messages == []
    assert logger.info_messages == ["Dumped il2cpp binary file successfully."]
    assert ensure_calls == ["net10.0"]
    assert len(run_calls) == 1
    assert "--framework" in run_calls[0].argv
    assert "net10.0" in run_calls[0].argv
    assert (
        f"--formatter-output="
        f"{(tmp_path / 'Extracted' / 'Dumps' / 'memorypack_formatters.json').resolve()}"
    ) in run_calls[-1].argv


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
    runtime_assets = _prepared_runtime(context)
    binary_path = runtime_assets.binary_path

    logger = RecordingLogger()
    cpp2il_root = tmp_path / "fallback" / "Cpp2IL"
    source_resolver = StaticSourceResolver(cpp2il_root)
    final_metadata_path = (
        context.workspace.temp_state
        / context.resource_version
        / "MetadataRecovery"
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
    run_calls: list[ProcessCommand] = []
    ensure_calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_run(command: ProcessCommand) -> ProcessResult:
        run_calls.append(command)
        return ProcessResult(command, 0, "", "")

    def fake_ensure_exporter_project(
        _context: ExecutionContext,
        _cpp2il_root: Path,
        framework: str,
        extra_source_templates=None,  # type: ignore[no-untyped-def]
    ) -> Path:
        ensure_calls.append(
            (
                framework,
                tuple(sorted((extra_source_templates or {}).keys())),
            )
        )
        return exporter_project

    monkeypatch.setattr(
        backend,
        "_ensure_exporter_project",
        fake_ensure_exporter_project,
    )
    monkeypatch.setattr(backend, "_resolve_framework", lambda: "net10.0")
    monkeypatch.setattr(backend.process_runner, "run", fake_run)

    backend.dump(
        context,
        str(tmp_path / "Extracted" / "Dumps"),
        runtime_assets,
    )

    assert logger.warn_messages == []
    assert logger.info_messages == [
        "Starting CN metadata recovery.",
        "Recovered CN metadata successfully.",
        "Dumped CN metadata recovery il2cpp binary file successfully.",
    ]
    assert ensure_calls == [("net10.0", ("CnMetadataRecoveryInputShim.cs",))]
    assert pipeline.calls == [(b"metadata", binary_path)]
    assert final_metadata_path.read_bytes() == b"standard v29 metadata"
    assert sorted(path.name for path in final_metadata_path.parent.iterdir()) == [
        "global-metadata.standard-v29.dat"
    ]
    assert [call.argv for call in run_calls] == [
        (
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
        )
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
    runtime_assets = _prepared_runtime(context)
    logger = RecordingLogger()
    backend = CnMetadataRecoveryDumpBackend(
        DummyHttpClient(),
        logger,
        StaticSourceResolver(tmp_path / "Cpp2IL"),
        recovery_pipeline=FailingPipeline(),
    )

    with pytest.raises(
        CnMetadataRecoveryDumpError, match="sanitize_default_values"
    ) as exc:
        backend.dump(
            context,
            str(tmp_path / "Extracted" / "Dumps"),
            runtime_assets,
        )

    assert "Input:" in str(exc.value)
    assert "Binary:" in str(exc.value)
    assert "Output:" in str(exc.value)


def test_cn_metadata_recovery_backend_requires_prepared_metadata_and_binary(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path, region="cn")
    runtime_dir = context.workspace.temp_state / context.resource_version / "Runtime"
    runtime_dir.mkdir(parents=True)
    metadata_path = runtime_dir / "global-metadata.dat"
    metadata_path.write_bytes(b"metadata")
    runtime_assets = PreparedRuntimeAssets(
        version=context.resource_version,
        root_dir=runtime_dir,
        binary_path=runtime_dir / "libil2cpp.so",
        metadata_path=metadata_path,
        globalgamemanagers_path=runtime_dir / "globalgamemanagers",
    )
    backend = CnMetadataRecoveryDumpBackend(
        DummyHttpClient(),
        RecordingLogger(),
        StaticSourceResolver(tmp_path / "Cpp2IL"),
    )

    with pytest.raises(FileNotFoundError):
        backend.dump(
            context,
            str(tmp_path / "Extracted" / "Dumps"),
            runtime_assets,
        )
