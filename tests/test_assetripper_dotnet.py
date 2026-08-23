from __future__ import annotations

import hashlib
import os
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NoReturn
from zipfile import ZipFile

import pytest

from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
    BundleEntryInput,
)
from ba_downloader.infrastructure.extraction.assetripper.exporter import (
    AssetRipperBatchExporter,
    AssetRipperExportError,
    AssetRipperExportGroup,
    AssetRipperExportInput,
    AssetRipperRuntimeMetadataInspector,
)
from ba_downloader.infrastructure.extraction.assetripper.source import (
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from ba_downloader.infrastructure.runtime.process import CancellableProcessRunner
from support.fixtures import build_execution_context


class _OfflineHttpClient:
    def download_to_file(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError(
            "AssetRipper integration build must use the checked-out submodule"
        )


def _project_closure(project: Path, source_root: Path) -> set[str]:
    pending = [project.resolve()]
    resolved: set[Path] = set()
    while pending:
        current = pending.pop()
        if current in resolved:
            continue
        resolved.add(current)
        for element in ET.parse(current).iter():
            if not element.tag.endswith("ProjectReference"):
                continue
            include = element.get("Include")
            if include is None:
                continue
            normalized = include.replace(
                "$(AssetRipperSource)", str(source_root)
            ).replace("\\", "/")
            referenced = Path(normalized)
            if not referenced.is_absolute():
                referenced = current.parent / referenced
            pending.append(referenced.resolve())
    return {path.stem for path in resolved}


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


@pytest.mark.skipif(
    os.environ.get("BAAD_RUN_DOTNET_BUILD") != "1",
    reason="Set BAAD_RUN_DOTNET_BUILD=1 to run the AssetRipper .NET build.",
)
def test_assetripper_tools_build_against_validated_overlay(tmp_path: Path) -> None:
    assert shutil.which("dotnet") is not None, ".NET 10 SDK is required"
    repository = Path(__file__).parents[1]
    context = build_execution_context(tmp_path, region="jp", version="1")
    resolver = AssetRipperSourceResolver(
        _OfflineHttpClient(),  # type: ignore[arg-type]
        NullLogger(),
        repository_root=repository,
    )
    exporter = AssetRipperBatchExporter(
        resolver,
        CancellableProcessRunner(),
        repository_root=repository,
    )
    inspector = AssetRipperRuntimeMetadataInspector(
        resolver,
        CancellableProcessRunner(),
        repository_root=repository,
    )

    source_started = time.perf_counter()
    patched_source = resolver.resolve_patched(context)
    source_seconds = time.perf_counter() - source_started
    inspector_started = time.perf_counter()
    inspector.prepare(context)
    inspector_seconds = time.perf_counter() - inspector_started
    exporter_started = time.perf_counter()
    exporter.prepare(context)
    exporter_seconds = time.perf_counter() - exporter_started

    inspector_outputs = list(
        (context.workspace.tools_cache / "assetripper" / "runtime-inspector").glob(
            "*/AssetRipperRuntimeInspector.dll"
        )
    )
    exporter_outputs = list(
        (context.workspace.tools_cache / "assetripper" / "exporter").glob(
            "*/AssetRipperExporter.dll"
        )
    )
    assert len(inspector_outputs) == 1
    assert len(exporter_outputs) == 1
    inspector_output = inspector_outputs[0]
    exporter_output = exporter_outputs[0]
    assert (patched_source / "overlay.json").is_file()
    assert inspector_output.is_file()
    assert inspector_output.stat().st_size > 0
    assert exporter_output.is_file()
    assert exporter_output.stat().st_size > 0

    archive_path = tmp_path / "bundle.zip"
    payload = b"bundle-entry"
    with ZipFile(archive_path, "w") as archive_file:
        archive_file.writestr("nested/asset.bundle", payload)
    with ZipFile(archive_path) as archive_file:
        crc32 = archive_file.getinfo("nested/asset.bundle").CRC
    archive = BundleArchiveInput.from_path(
        archive_path,
        archive_id="bundle.zip",
    )
    entry = BundleEntryInput(
        archive,
        "nested/asset.bundle",
        hashlib.sha256(payload).hexdigest(),
        len(payload),
        crc32=crc32,
    )
    cache_root = context.workspace.cache_state / "assetripper" / "entries"
    destination = cache_root / entry.sha256[:2] / entry.sha256 / "asset.bundle"
    materialized = exporter.materialize_entries(
        context,
        [entry],
        {entry.node_id: destination},
        concurrency=4,
    )
    assert materialized == {entry.node_id: len(payload)}
    assert destination.read_bytes() == payload
    assert destination.with_suffix(".bundle.json").is_file()

    with pytest.raises(AssetRipperExportError):
        exporter.export_grouped(
            context,
            [
                AssetRipperExportGroup(
                    "invalid",
                    (
                        AssetRipperExportInput(
                            destination,
                            entry.node_id,
                            True,
                        ),
                    ),
                )
            ],
            tmp_path / "invalid-output",
            concurrency=4,
        )

    inspector_project = (
        repository
        / "src"
        / "ba_downloader"
        / "infrastructure"
        / "extraction"
        / "assetripper"
        / "tool"
        / "runtime_inspector"
        / "AssetRipperRuntimeInspector.csproj"
    )
    closure = _project_closure(inspector_project, patched_source)
    assert closure == {
        "AssetRipperRuntimeInspector",
        "AssetRipper.Assets",
        "AssetRipper.Configuration",
        "AssetRipper.IO.Files",
        "AssetRipper.Import",
        "AssetRipper.Numerics",
        "AssetRipper.SerializationLogic",
        "AssetRipper.SourceGenerated.Extensions",
        "AssetRipper.SourceGenerated.Extensions.SourceGenerator",
    }
    print(
        {
            "patched_source_seconds": round(source_seconds, 2),
            "inspector_build_seconds": round(inspector_seconds, 2),
            "cold_inspector_prepare_seconds": round(
                source_seconds + inspector_seconds, 2
            ),
            "deferred_exporter_build_seconds": round(exporter_seconds, 2),
            "inspector_project_count": len(closure) - 1,
            "inspector_output_bytes": _directory_size(inspector_output.parent),
            "exporter_output_bytes": _directory_size(exporter_output.parent),
        }
    )
