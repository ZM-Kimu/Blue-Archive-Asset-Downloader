from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.http import DownloadResult
from ba_downloader.domain.ports.process import (
    ProcessCommand,
    ProcessOutputLine,
    ProcessOutputObserverPort,
    ProcessResult,
)
from ba_downloader.infrastructure.extraction.assetripper import (
    exporter as exporter_module,
)
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
)
from ba_downloader.infrastructure.extraction.assetripper.events import (
    EVENT_VERSION,
    AssetRipperHeartbeatEvent,
    AssetRipperLogEvent,
    AssetRipperPhaseEvent,
    AssetRipperProgressEvent,
    AssetRipperScanProgressEvent,
    parse_assetripper_event,
)
from ba_downloader.infrastructure.extraction.assetripper.exporter import (
    ASSETRIPPER_EXPORTER_WRAPPER_VERSION,
    AssetRipperBatchExporter,
    AssetRipperDependencyScanner,
    AssetRipperExportError,
    AssetRipperExportInput,
    AssetRipperRuntimeMetadataInspector,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    ASSETRIPPER_COMMIT,
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from support.fixtures import build_execution_context


def _context(tmp_path: Path, *, region: str = "jp") -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region=region,
        platform="android",
        version="1",
        max_retries=0,
    )


class FakeProcessRunner:
    def __init__(
        self,
        *,
        export_succeeds: bool = True,
        exported_files: bool = True,
    ) -> None:
        self.commands: list[ProcessCommand] = []
        self.requests: list[dict[str, object]] = []
        self.export_succeeds = export_succeeds
        self.exported_files = exported_files

    def run(
        self,
        command: ProcessCommand,
        *,
        output_observer: ProcessOutputObserverPort | None = None,
    ) -> ProcessResult:
        self.commands.append(command)
        if command.argv[1] == "build":
            output = Path(command.argv[command.argv.index("--output") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "AssetRipperExporter.dll").write_bytes(b"dll")
            return ProcessResult(command, 0, "", "")

        result_path = Path(command.argv[-1])
        request = json.loads(Path(command.argv[-2]).read_text(encoding="utf8"))
        self.requests.append(request)
        input_sort_keys = [
            item["path"] if isinstance(item, dict) else item
            for item in request["inputs"]
        ]
        assert input_sort_keys == sorted(input_sort_keys, key=str.casefold)
        if request["operation"] == "inspect_jp_runtime":
            result_path.write_text(
                json.dumps(
                    {
                        "succeeded": True,
                        "error": None,
                        "game_main_config_base64": base64.b64encode(
                            b"encrypted-config"
                        ).decode("ascii"),
                        "bundle_version": "1.2.3",
                    }
                ),
                encoding="utf8",
            )
            return ProcessResult(command, 0, "", "")
        if request["operation"] == "scan_bundle_dependencies":
            if output_observer is not None:
                output_observer.on_output(
                    ProcessOutputLine(
                        "stdout",
                        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},'
                        '"kind":"scan_progress","current":1,"total":1,'
                        '"archive_id":"archive.zip"}',
                    )
                )
            result_path.write_text(
                json.dumps(
                    {
                        "succeeded": True,
                        "error": None,
                        "scans": [
                            {
                                "archive_id": request["archive_ids"][0],
                                "sha256": "a" * 64,
                                "entries": [
                                    {
                                        "entry_path": "asset.bundle",
                                        "sha256": "b" * 64,
                                        "size": 123,
                                        "serialized_files": [
                                            {
                                                "logical_name": "cab-a",
                                                "dependencies": ["cab-b"],
                                            }
                                        ],
                                        "resource_files": ["a.resS"],
                                        "streamed_resources": [
                                            {
                                                "source_serialized_file": "cab-a",
                                                "resource_path": "a.resS",
                                                "asset_type": "Texture2D",
                                            }
                                        ],
                                        "error": None,
                                    }
                                ],
                                "error": None,
                            }
                        ],
                    }
                ),
                encoding="utf8",
            )
            return ProcessResult(command, 0, "", "")
        assert request["operation"] == "export_primary_content"
        requested_target_ids = [
            item["node_id"]
            for item in request["inputs"]
            if isinstance(item, dict) and item["target"]
        ]
        if output_observer is not None:
            output_observer.on_output(
                ProcessOutputLine(
                    "stderr",
                    f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"log",'
                    '"level":"error","category":"Export","message":"ignored"}',
                )
            )
            output_observer.on_output(ProcessOutputLine("stdout", "ordinary output"))
            output_observer.on_output(
                ProcessOutputLine(
                    "stdout",
                    f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"phase",'
                    '"phase":"loading"}',
                )
            )
            output_observer.on_output(
                ProcessOutputLine(
                    "stdout",
                    f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"progress",'
                    '"phase":"loading","stage":"loading_files",'
                    '"current":2,"total":5}',
                )
            )
        result_path.write_text(
            json.dumps(
                {
                    "succeeded": self.export_succeeds,
                    "error": None if self.export_succeeds else "Invalid bundle",
                    "files": (
                        [{"path": "asset.bin", "size": 3}]
                        if self.export_succeeds and self.exported_files
                        else []
                    ),
                    "requested_target_ids": requested_target_ids,
                    "resolved_target_ids": requested_target_ids,
                    "exported_target_ids": requested_target_ids,
                }
            ),
            encoding="utf8",
        )
        return ProcessResult(command, 0 if self.export_succeeds else 1, "", "")


class FakeHttpClient:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.downloads = 0

    def download_to_file(
        self, url: str, destination: str, **_: object
    ) -> DownloadResult:
        self.downloads += 1
        Path(destination).write_bytes(self.payload)
        return DownloadResult(destination, len(self.payload), 200, {}, url)


def _write_source_archive(path: Path) -> bytes:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "source/Source/AssetRipper.Export.PrimaryContent/"
            "AssetRipper.Export.PrimaryContent.csproj",
            "<Project />",
        )
        archive.writestr(
            "source/Source/AssetRipper.Export.UnityProjects/"
            "AssetRipper.Export.UnityProjects.csproj",
            "<Project />",
        )
    return path.read_bytes()


def _export_input(path: Path, *, target: bool = True) -> AssetRipperExportInput:
    return AssetRipperExportInput(path, path.name, target)


def test_source_resolver_prefers_valid_submodule(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    source = repository / "third_party" / "AssetRipper"
    for relative_project in (
        "Source/AssetRipper.Export.PrimaryContent/"
        "AssetRipper.Export.PrimaryContent.csproj",
        "Source/AssetRipper.Export.UnityProjects/"
        "AssetRipper.Export.UnityProjects.csproj",
    ):
        project = source / relative_project
        project.parent.mkdir(parents=True, exist_ok=True)
        project.write_text("<Project />", encoding="utf8")

    client = FakeHttpClient(b"")
    resolver = AssetRipperSourceResolver(
        client,
        NullLogger(),
        repository_root=repository,
    )

    assert resolver.resolve(_context(tmp_path)) == source
    assert client.downloads == 0


def test_source_resolver_downloads_verified_fallback(tmp_path: Path) -> None:
    archive = _write_source_archive(tmp_path / "source.zip")
    client = FakeHttpClient(archive)
    resolver = AssetRipperSourceResolver(
        client,
        NullLogger(),
        repository_root=tmp_path / "repository",
        archive_url="https://example.invalid/source.zip",
        archive_sha256=hashlib.sha256(archive).hexdigest(),
        commit="test-commit",
    )

    first = resolver.resolve(_context(tmp_path))
    second = resolver.resolve(_context(tmp_path))

    assert first == second
    assert client.downloads == 1


def test_source_resolver_applies_shared_versioned_overlay(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    resolver = AssetRipperSourceResolver(
        FakeHttpClient(b""),
        NullLogger(),
        repository_root=repository,
    )

    jp_context = _context(tmp_path)
    cn_context = _context(tmp_path, region="cn")
    patched = resolver.resolve_patched(jp_context)
    reused = resolver.resolve_patched(cn_context)

    assert patched == reused
    assert jp_context.workspace.tools_cache == cn_context.workspace.tools_cache
    assert patched != repository / "third_party" / "AssetRipper"
    assert (
        patched / "Source" / "AssetRipper.Assets" / "Bundles" / "GameLoadProgress.cs"
    ).is_file()
    assert (patched / "overlay.json").is_file()
    guid_table = (
        patched
        / "Source"
        / "AssetRipper.Processing"
        / "AudioMixers"
        / "GuidIndexTable.cs"
    ).read_text(encoding="utf8")
    processor = (
        patched
        / "Source"
        / "AssetRipper.Processing"
        / "AudioMixers"
        / "AudioMixerProcessor.cs"
    ).read_text(encoding="utf8")

    assert "UnityGuid.NewGuid()" not in guid_table
    assert "UnityGuid.NewGuid()" not in processor
    assert "UnityGuid.Md5Hash" in guid_table
    assert "mixer.Collection.Name" in processor
    assert "mixer.PathID" in processor
    collection = (
        patched
        / "Source"
        / "AssetRipper.Export.PrimaryContent"
        / "Models"
        / "GlbPrefabModelExportCollection.cs"
    ).read_text(encoding="utf8")

    assert "asset.Root.Collection.Name" in collection
    assert "asset.Root.PathID" in collection
    assert "GetStableDirectoryName" in collection
    assert "asset.PathID" not in collection
    registry = (
        patched
        / "Source"
        / "AssetRipper.Assets"
        / "Bundles"
        / "AssetProvenanceRegistry.cs"
    ).read_text(encoding="utf8")
    exporter = (
        patched
        / "Source"
        / "AssetRipper.Export.PrimaryContent"
        / "PrimaryContentExporter.cs"
    ).read_text(encoding="utf8")

    assert "RegisterInput" in registry
    assert "RegisterCollection" in registry
    assert "RegisterDerived" in registry
    assert "ResolveProvenance" in registry
    assert "ExportSelective" in exporter
    assert "handledEmptyTargetIds" in exporter
    assert "collection is EmptyExportCollection" in exporter


def test_batch_exporter_builds_once_and_reads_typed_result(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "Source" / "AssetRipper.Export.PrimaryContent").mkdir(parents=True)
    (source / "Source" / "AssetRipper.Export.UnityProjects").mkdir(parents=True)
    for project in (
        source
        / "Source"
        / "AssetRipper.Export.PrimaryContent"
        / "AssetRipper.Export.PrimaryContent.csproj",
        source
        / "Source"
        / "AssetRipper.Export.UnityProjects"
        / "AssetRipper.Export.UnityProjects.csproj",
    ):
        project.write_text("<Project />", encoding="utf8")
    resolver = type("Resolver", (), {"resolve_patched": lambda self, context: source})()
    runner = FakeProcessRunner()
    exporter = AssetRipperBatchExporter(
        resolver,  # type: ignore[arg-type]
        runner,
        repository_root=tmp_path,
    )
    input_b = tmp_path / "b.bundle"
    input_a = tmp_path / "a.bundle"
    input_b.write_bytes(b"b")
    input_a.write_bytes(b"a")

    context = _context(tmp_path)
    result = exporter.export(
        context,
        [_export_input(input_b), _export_input(input_a)],
        tmp_path / "out",
    )
    other_context = _context(tmp_path, region="cn")
    exporter.export(
        other_context,
        [_export_input(input_a)],
        tmp_path / "out-again",
    )

    assert result.files[0].path == "asset.bin"
    assert context.workspace.tools_cache == other_context.workspace.tools_cache
    assert [command.argv[1] for command in runner.commands] == [
        "build",
        str(runner.commands[1].argv[1]),
        str(runner.commands[2].argv[1]),
    ]
    assert "--disable-build-servers" in runner.commands[0].argv
    assert Path(runner.commands[0].argv[3]) == (
        Path(exporter_module.__file__).with_name("tool") / "AssetRipperExporter.csproj"
    )


def test_batch_exporter_sends_targeted_inputs_and_reads_coverage(
    tmp_path: Path,
) -> None:
    source = type("Resolver", (), {"resolve_patched": lambda self, context: tmp_path})()
    runner = FakeProcessRunner()
    exporter = AssetRipperBatchExporter(
        source,  # type: ignore[arg-type]
        runner,
        repository_root=tmp_path,
    )
    dependency = tmp_path / "dependency.bundle"
    target = tmp_path / "target.bundle"
    dependency.write_bytes(b"dependency")
    target.write_bytes(b"target")

    result = exporter.export(
        _context(tmp_path),
        [
            AssetRipperExportInput(dependency, "archive::dependency", False),
            AssetRipperExportInput(target, "archive::target", True),
        ],
        tmp_path / "out",
    )

    request = runner.requests[-1]
    assert request["inputs"] == [
        {
            "node_id": "archive::dependency",
            "path": str(dependency.resolve()),
            "target": False,
        },
        {
            "node_id": "archive::target",
            "path": str(target.resolve()),
            "target": True,
        },
    ]
    assert result.requested_target_ids == ("archive::target",)
    assert result.resolved_target_ids == ("archive::target",)
    assert result.exported_target_ids == ("archive::target",)


def test_batch_exporter_forwards_structured_process_events(tmp_path: Path) -> None:
    source = type("Resolver", (), {"resolve_patched": lambda self, context: tmp_path})()
    runner = FakeProcessRunner()
    exporter = AssetRipperBatchExporter(
        source,  # type: ignore[arg-type]
        runner,
        repository_root=tmp_path,
    )
    bundle = tmp_path / "bundle"
    bundle.write_bytes(b"bundle")
    events: list[
        AssetRipperPhaseEvent | AssetRipperProgressEvent | AssetRipperLogEvent
    ] = []

    exporter.export(
        _context(tmp_path),
        [_export_input(bundle)],
        tmp_path / "out",
        events.append,
    )

    assert events == [
        AssetRipperPhaseEvent("loading"),
        AssetRipperProgressEvent("loading", 2, 5, "loading_files"),
    ]


@pytest.mark.parametrize(
    "line",
    [
        "ordinary AssetRipper output",
        "BAAD_ASSETRIPPER_EVENT not-json",
        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"phase","phase":"unknown"}}',
        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"progress",'
        '"phase":"exporting","current":6,"total":5}',
        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"log",'
        '"level":"info","category":"Import","message":"ignored"}',
    ],
)
def test_assetripper_event_parser_ignores_unsupported_lines(line: str) -> None:
    assert parse_assetripper_event(line) is None


def test_assetripper_event_parser_reads_warning_and_error_events() -> None:
    warning = parse_assetripper_event(
        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"log",'
        '"level":"warning","category":"Import","message":"bad asset"}'
    )
    error = parse_assetripper_event(
        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"log",'
        '"level":"error","category":"Export","message":"failed asset"}'
    )

    assert warning == AssetRipperLogEvent("warning", "Import", "bad asset")
    assert error == AssetRipperLogEvent("error", "Export", "failed asset")


def test_assetripper_event_parser_reads_processing_heartbeat() -> None:
    heartbeat = parse_assetripper_event(
        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"heartbeat",'
        '"phase":"processing","elapsed_seconds":12.5}'
    )

    assert heartbeat == AssetRipperHeartbeatEvent("processing", 12.5)


def test_assetripper_event_parser_reads_dependency_scan_progress() -> None:
    event = parse_assetripper_event(
        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},'
        '"kind":"scan_progress","current":2,"total":5,'
        '"archive_id":"FullPatch_001.zip"}'
    )

    assert event == AssetRipperScanProgressEvent(2, 5, "FullPatch_001.zip")


def test_assetripper_event_parser_ignores_invalid_processing_heartbeat() -> None:
    heartbeat = parse_assetripper_event(
        f'BAAD_ASSETRIPPER_EVENT {{"version":{EVENT_VERSION},"kind":"heartbeat",'
        '"phase":"loading","elapsed_seconds":-1}'
    )

    assert heartbeat is None


def test_packaged_exporter_preserves_runtime_contracts() -> None:
    program = (
        Path(__file__).parents[1]
        / "src"
        / "ba_downloader"
        / "infrastructure"
        / "extraction"
        / "assetripper"
        / "tool"
        / "Program.cs"
    ).read_text(encoding="utf8")

    assert "Logger.Add(eventLogger);" in program
    assert 'EventWriter.WritePhase("loading");' in program
    assert 'EventWriter.WritePhase("processing");' in program
    assert 'EventWriter.WritePhase("exporting");' in program
    assert "WriteHeartbeat" in program
    assert "ProcessWithHeartbeat" in program
    assert "handler.Load(" in program
    assert "handler.Process(gameData);" in program
    assert "LoadAndProcess" not in program
    assert '"scan_bundle_dependencies"' in program
    assert "SchemeReader.ReadFile(buffer" in program
    assert "serializedFile.Dependencies" in program
    assert "FetchResourceFiles" in program
    assert "ScanStreamedResources" in program
    assert "DisposeFileTree(file);" in program
    assert "EventWriter.WriteScanProgress" in program
    assert "ExportInput" in program
    assert "AssetProvenanceRegistry.Configure" in program
    assert "ExportSelective" in program
    assert "RequestedTargetIds" in program
    assert "ResolvedTargetIds" in program
    assert "ExportedTargetIds" in program


def test_legacy_exporter_cache_marker_forces_wrapper_rebuild(tmp_path: Path) -> None:
    source = type("Resolver", (), {"resolve_patched": lambda self, context: tmp_path})()
    runner = FakeProcessRunner()
    exporter = AssetRipperBatchExporter(
        source,  # type: ignore[arg-type]
        runner,
        repository_root=tmp_path,
    )
    bundle = tmp_path / "bundle"
    bundle.write_bytes(b"bundle")
    context = _context(tmp_path)

    exporter.export(context, [_export_input(bundle)], tmp_path / "first")
    cache_root = context.workspace.tools_cache / "assetripper" / "exporter"
    marker = cache_root / "source-commit.txt"
    marker.write_text(f"{ASSETRIPPER_COMMIT}\n", encoding="ascii")
    exporter.export(context, [_export_input(bundle)], tmp_path / "second")

    assert ASSETRIPPER_EXPORTER_WRAPPER_VERSION != "1"
    assert [command.argv[1] for command in runner.commands].count("build") == 2


def test_batch_exporter_reports_structured_failure(tmp_path: Path) -> None:
    source = type("Resolver", (), {"resolve_patched": lambda self, context: tmp_path})()
    runner = FakeProcessRunner(export_succeeds=False)
    exporter = AssetRipperBatchExporter(
        source,  # type: ignore[arg-type]
        runner,
        repository_root=tmp_path,
    )
    bundle = tmp_path / "bad.bundle"
    bundle.write_bytes(b"bad")

    with pytest.raises(AssetRipperExportError):
        exporter.export(_context(tmp_path), [_export_input(bundle)], tmp_path / "out")


def test_batch_exporter_rejects_success_without_output(tmp_path: Path) -> None:
    source = type("Resolver", (), {"resolve_patched": lambda self, context: tmp_path})()
    runner = FakeProcessRunner(exported_files=False)
    exporter = AssetRipperBatchExporter(
        source,  # type: ignore[arg-type]
        runner,
        repository_root=tmp_path,
    )
    bundle = tmp_path / "empty.bundle"
    bundle.write_bytes(b"empty")

    with pytest.raises(AssetRipperExportError):
        exporter.export(_context(tmp_path), [_export_input(bundle)], tmp_path / "out")


def test_runtime_metadata_inspector_reads_typed_result(tmp_path: Path) -> None:
    source = type("Resolver", (), {"resolve_patched": lambda self, context: tmp_path})()
    runner = FakeProcessRunner()
    inspector = AssetRipperRuntimeMetadataInspector(
        source,  # type: ignore[arg-type]
        runner,
        repository_root=tmp_path,
    )
    data_root = tmp_path / "Data"
    data_root.mkdir()

    metadata = inspector.inspect(_context(tmp_path), data_root)

    assert metadata.game_main_config == b"encrypted-config"
    assert metadata.bundle_version == "1.2.3"
    assert runner.requests[-1] == {
        "inputs": [str(data_root.resolve())],
        "operation": "inspect_jp_runtime",
    }


def test_dependency_scanner_reads_strict_archive_results(tmp_path: Path) -> None:
    source = type("Resolver", (), {"resolve_patched": lambda self, context: tmp_path})()
    runner = FakeProcessRunner()
    scanner = AssetRipperDependencyScanner(
        source,  # type: ignore[arg-type]
        runner,
        repository_root=tmp_path,
    )
    path = tmp_path / "archive.zip"
    path.write_bytes(b"archive")
    archive = BundleArchiveInput.from_path(path, archive_id="archive.zip")
    events: list[object] = []

    scans = scanner.scan(_context(tmp_path), [archive], events.append)

    assert scans[0].archive_id == "archive.zip"
    assert scans[0].entries[0].serialized_files[0].dependencies == ("cab-b",)
    assert scans[0].entries[0].resource_files == ("a.resS",)
    assert scans[0].entries[0].streamed_resources[0].asset_type == "Texture2D"
    assert events == [AssetRipperScanProgressEvent(1, 1, "archive.zip")]
    assert runner.requests[-1]["archive_ids"] == ["archive.zip"]
