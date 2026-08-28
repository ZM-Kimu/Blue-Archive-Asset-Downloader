from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ba_downloader.infrastructure.extraction.errors import BundleExtractionError
from ba_downloader.infrastructure.extraction.unitypy.bundles import (
    UnityPyBundleWorkflow,
    _load_unitypy_environment,
)
from support.fixtures import build_execution_context


class RecordingLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def info(self, _message: str) -> None:
        pass

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, _message: str) -> None:
        pass


class FakeImage:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def save(self, path: str) -> None:
        Path(path).write_bytes(self.content)


class FakeObject:
    def __init__(
        self,
        asset_type: str,
        class_id: int,
        path_id: int,
        data: Any,
        *,
        serialized_file: str = "sharedassets0.assets",
    ) -> None:
        self.type = SimpleNamespace(name=asset_type, value=class_id)
        self.path_id = path_id
        self.assets_file = SimpleNamespace(name=serialized_file)
        self._data = data

    def read(self) -> Any:
        return self._data


def _context(tmp_path: Path) -> Any:
    return build_execution_context(
        tmp_path,
        region="jp",
        version="1.0.0",
        max_retries=1,
    )


def _bundle(context: Any, name: str = "sample.bundle") -> Path:
    path = context.workspace.raw_bundles / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"bundle")
    return path


def _objects(prefix: str = "sample") -> list[FakeObject]:
    return [
        FakeObject(
            "Texture2D",
            28,
            1,
            SimpleNamespace(m_Name=f"{prefix}_texture", image=FakeImage(b"png")),
        ),
        FakeObject(
            "Sprite",
            213,
            2,
            SimpleNamespace(m_Name=f"{prefix}_sprite", image=FakeImage(b"sprite")),
        ),
        FakeObject(
            "AudioClip",
            83,
            3,
            SimpleNamespace(
                m_Name=f"{prefix}_audio",
                samples={f"{prefix}.wav": b"wave"},
            ),
        ),
        FakeObject(
            "Font",
            128,
            4,
            SimpleNamespace(m_Name=f"{prefix}_font", m_FontData=b"font"),
        ),
        FakeObject(
            "TextAsset",
            49,
            5,
            SimpleNamespace(m_Name=f"{prefix}.txt", m_Script="text"),
        ),
        FakeObject(
            "Mesh",
            43,
            6,
            SimpleNamespace(m_Name=f"{prefix}_mesh", export=lambda: "o mesh\n"),
        ),
        FakeObject(
            "MonoBehaviour",
            114,
            7,
            SimpleNamespace(m_Name="ignored"),
        ),
    ]


def test_unitypy_missing_optional_dependency_is_user_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setitem(sys.modules, "UnityPy", None)

    with pytest.raises(BundleExtractionError, match="optional dependency"):
        _load_unitypy_environment(tmp_path / "sample.bundle")


def test_unitypy_exports_only_reduced_primary_types(tmp_path: Path) -> None:
    context = _context(tmp_path)
    bundle = _bundle(context)
    environment = SimpleNamespace(objects=_objects())

    report = UnityPyBundleWorkflow(
        RecordingLogger(),
        environment_loader=lambda _path: environment,
    ).run(context, [bundle], concurrency=30)

    output = context.workspace.extracted_bundles
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf8"))
    assert report.failed_batches == 0
    assert manifest["schema_version"] == 0
    assert manifest["layout"] == "unitypy-readable"
    assert {record["type"] for record in manifest["assets"].values()} == {
        "Texture2D",
        "Sprite",
        "AudioClip",
        "Font",
        "TextAsset",
        "Mesh",
    }
    assert (output / "Assets/Texture2D/sample_texture.png").read_bytes() == b"png"
    assert (output / "Assets/Sprite/sample_sprite.png").read_bytes() == b"sprite"
    assert (output / "Assets/AudioClip/sample.wav").read_bytes() == b"wave"
    assert (output / "Assets/Font/sample_font.ttf").read_bytes() == b"font"
    assert (output / "Assets/TextAsset/sample.txt").read_text() == "text"
    assert (output / "Assets/Mesh/sample_mesh.obj").read_text() == "o mesh\n"
    assert not (output / "Assets/MonoBehaviour").exists()


def test_unitypy_filtered_runs_accumulate_for_same_handler(tmp_path: Path) -> None:
    context = _context(tmp_path)
    first = _bundle(context, "first.bundle")
    second = _bundle(context, "second.bundle")
    environments = {
        first: SimpleNamespace(objects=_objects("first")[:1]),
        second: SimpleNamespace(objects=_objects("second")[:1]),
    }
    workflow = UnityPyBundleWorkflow(
        RecordingLogger(),
        environment_loader=lambda path: environments[path],
    )

    workflow.run(context, [first], concurrency=1, filtered=True)
    workflow.run(context, [second], concurrency=1, filtered=True)

    output = context.workspace.extracted_bundles
    assert (output / "Assets/Texture2D/first_texture.png").is_file()
    assert (output / "Assets/Texture2D/second_texture.png").is_file()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf8"))
    assert len(manifest["assets"]) == 2


def test_unitypy_allocates_deterministic_numeric_suffixes(tmp_path: Path) -> None:
    context = _context(tmp_path)
    bundle = _bundle(context)
    objects = [
        FakeObject(
            "Texture2D",
            28,
            path_id,
            SimpleNamespace(m_Name="duplicate", image=FakeImage(content)),
        )
        for path_id, content in ((2, b"second"), (1, b"first"))
    ]

    UnityPyBundleWorkflow(
        RecordingLogger(),
        environment_loader=lambda _path: SimpleNamespace(objects=objects),
    ).run(context, [bundle], concurrency=1)

    assets = context.workspace.extracted_bundles / "Assets/Texture2D"
    assert (assets / "duplicate.png").read_bytes() == b"first"
    assert (assets / "duplicate_0.png").read_bytes() == b"second"


def test_unitypy_skips_empty_font_without_reporting_failure(tmp_path: Path) -> None:
    context = _context(tmp_path)
    bundle = _bundle(context)
    objects = [
        FakeObject(
            "Font",
            128,
            1,
            SimpleNamespace(m_Name="empty", m_FontData=b""),
        ),
        _objects()[0],
    ]

    report = UnityPyBundleWorkflow(
        RecordingLogger(),
        environment_loader=lambda _path: SimpleNamespace(objects=objects),
    ).run(context, [bundle], concurrency=1)

    manifest = json.loads(
        (context.workspace.extracted_bundles / "manifest.json").read_text()
    )
    assert report.warnings == ()
    assert manifest["failures"] == []
    assert {record["type"] for record in manifest["assets"].values()} == {"Texture2D"}


def test_unitypy_retries_incomplete_run_and_warm_hits_complete_run(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    bundle = _bundle(context)
    calls = 0

    def load(_path: Path) -> Any:
        nonlocal calls
        calls += 1
        return SimpleNamespace(objects=_objects()[:1])

    workflow = UnityPyBundleWorkflow(RecordingLogger(), environment_loader=load)

    workflow.run(context, [bundle], concurrency=1)
    workflow.run(context, [bundle], concurrency=1)

    assert calls == 1


def test_unitypy_replaces_incompatible_handler_output(tmp_path: Path) -> None:
    context = _context(tmp_path)
    bundle = _bundle(context)
    output = context.workspace.extracted_bundles
    old_asset = output / "Assets/old.glb"
    old_asset.parent.mkdir(parents=True)
    old_asset.write_bytes(b"old")
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 0,
                "layout": "assetripper-readable",
                "assets": {},
                "failures": [],
            }
        ),
        encoding="utf8",
    )

    UnityPyBundleWorkflow(
        RecordingLogger(),
        environment_loader=lambda _path: SimpleNamespace(objects=_objects()[:1]),
    ).run(context, [bundle], concurrency=1, filtered=True)

    assert not old_asset.exists()
    assert (output / "Assets/Texture2D/sample_texture.png").is_file()


def test_unitypy_failure_preserves_published_output(tmp_path: Path) -> None:
    context = _context(tmp_path)
    bundle = _bundle(context)
    output = context.workspace.extracted_bundles
    marker = output / "Assets/keep.bin"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"keep")
    (output / "manifest.json").write_text(
        json.dumps({"schema_version": 9}),
        encoding="utf8",
    )

    def fail(_path: Path) -> Any:
        raise ValueError("bad archive")

    with pytest.raises(BundleExtractionError):
        UnityPyBundleWorkflow(
            RecordingLogger(),
            environment_loader=fail,
        ).run(context, [bundle], concurrency=1)

    assert marker.read_bytes() == b"keep"
    assert json.loads((output / "manifest.json").read_text())["schema_version"] == 9
