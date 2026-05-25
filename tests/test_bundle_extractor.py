from __future__ import annotations

from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any

import UnityPy

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extractors import bundle as bundle_module
from ba_downloader.infrastructure.extractors.bundle import BundleExtractor


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


class FakeMesh:
    def __init__(self, name: str, export_result: Any) -> None:
        self.m_Name = name
        self._export_result = export_result

    def export(self) -> Any:
        if isinstance(self._export_result, Exception):
            raise self._export_result
        return self._export_result


class FakeImage:
    def __init__(self) -> None:
        self.saved_path: str | None = None

    def save(self, path: str) -> None:
        self.saved_path = path


class FakeTexture:
    def __init__(self, name: str, image: Any) -> None:
        self.m_Name = name
        self._image = image

    @property
    def image(self) -> Any:
        if isinstance(self._image, Exception):
            raise self._image
        return self._image


class FakeFont:
    def __init__(self, name: str, font_data: Any) -> None:
        self.m_Name = name
        self.m_FontData = font_data


class FakeObject:
    def __init__(self, obj_type: str, data: Any) -> None:
        self.type = SimpleNamespace(name=obj_type)
        self._data = data

    def read(self) -> Any:
        return self._data


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="cn",
        threads=1,
        version="1.0.0",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _patch_unitypy_load(
    monkeypatch: Any,
    objects: list[FakeObject],
) -> None:
    monkeypatch.setattr(
        UnityPy,
        "load",
        lambda _bundle_path: SimpleNamespace(objects=objects),
    )


def test_extract_bundle_writes_mesh_obj_when_export_returns_string(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    logger = RecordingLogger()
    _patch_unitypy_load(
        monkeypatch,
        [FakeObject("Mesh", FakeMesh("mesh_ok", "g mesh_ok\n"))],
    )

    BundleExtractor(context, logger).extract_bundle("sample.bundle", ["Mesh"])

    output_path = Path(context.extract_dir) / "Bundle" / "Mesh" / "mesh_ok.obj"
    assert output_path.read_text(encoding="utf8") == "g mesh_ok\n"
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_bundle_summarizes_non_obj_mesh_exports_without_errors(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    logger = RecordingLogger()
    _patch_unitypy_load(
        monkeypatch,
        [
            FakeObject("Mesh", FakeMesh("mesh_a", False)),
            FakeObject("Mesh", FakeMesh("mesh_b", None)),
        ],
    )

    BundleExtractor(context, logger).extract_bundle("sample.bundle", ["Mesh"])

    mesh_output_dir = Path(context.extract_dir) / "Bundle" / "Mesh"
    assert not list(mesh_output_dir.glob("*.obj"))
    assert logger.warn_messages == [
        "Exported 0 meshes and skipped 2 meshes while extracting sample.bundle: "
        "UnityPy returned non-OBJ mesh data. Examples: mesh_a, mesh_b"
    ]
    assert logger.error_messages == []


def test_extract_bundle_keeps_real_mesh_export_exceptions_as_errors(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    logger = RecordingLogger()
    _patch_unitypy_load(
        monkeypatch,
        [FakeObject("Mesh", FakeMesh("mesh_bad", ValueError("broken mesh")))],
    )

    BundleExtractor(context, logger).extract_bundle("sample.bundle", ["Mesh"])

    assert logger.warn_messages == []
    assert logger.error_messages == [
        "Error while extracting bundle sample.bundle: "
        "RuntimeError: Cannot export mesh mesh_bad: broken mesh"
    ]


def test_extract_bundle_summarizes_unsupported_mesh_topology_without_errors(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    logger = RecordingLogger()
    _patch_unitypy_load(
        monkeypatch,
        [
            FakeObject(
                "Mesh",
                FakeMesh(
                    "BallEffector",
                    ValueError(
                        "Failed getting triangles. Submesh topology is lines or points."
                    ),
                ),
            )
        ],
    )

    BundleExtractor(context, logger).extract_bundle("sample.bundle", ["Mesh"])

    assert logger.warn_messages == [
        "Exported 0 meshes and skipped 1 meshes while extracting sample.bundle: "
        "UnityPy returned non-OBJ mesh data. Examples: BallEffector"
    ]
    assert logger.error_messages == []


def test_extract_bundle_summarizes_undecodable_images_without_errors(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    logger = RecordingLogger()
    _patch_unitypy_load(
        monkeypatch,
        [
            FakeObject(
                "Texture2D",
                FakeTexture("Font Texture", PermissionError("dependency missing")),
            )
        ],
    )

    BundleExtractor(context, logger).extract_bundle("sample.bundle", ["Texture2D"])

    assert logger.warn_messages == [
        "Skipped 1 images while extracting sample.bundle: "
        "UnityPy could not decode image data. Examples: "
        "Font Texture (PermissionError: dependency missing)"
    ]
    assert logger.error_messages == []


def test_extract_bundle_writes_font_when_font_data_is_int_list(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    logger = RecordingLogger()
    font_data = [79, 84, 84, 79, 0, 1]
    _patch_unitypy_load(
        monkeypatch,
        [FakeObject("Font", FakeFont("UIFont", font_data))],
    )

    BundleExtractor(context, logger).extract_bundle("sample.bundle", ["Font"])

    output_path = Path(context.extract_dir) / "Bundle" / "Font" / "UIFont.otf"
    assert output_path.read_bytes() == b"OTTO\x00\x01"
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_worker_does_not_count_skipped_mesh_as_bundle_error(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _patch_unitypy_load(
        monkeypatch,
        [FakeObject("Mesh", FakeMesh("mesh_a", False))],
    )
    tasks: Queue[str] = Queue()
    tasks.put("sample.bundle")
    error_count = SimpleNamespace(value=0)

    BundleExtractor.multiprocess_extract_worker(
        tasks,
        context,
        ["Mesh"],
        error_count,
    )

    assert error_count.value == 0


def test_worker_uses_log_event_queue_without_configuring_console_logging(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _patch_unitypy_load(
        monkeypatch,
        [FakeObject("Mesh", FakeMesh("mesh_a", False))],
    )
    tasks: Queue[str] = Queue()
    tasks.put("sample.bundle")
    log_events: Queue[Any] = Queue()
    error_count = SimpleNamespace(value=0)
    configure_calls: list[None] = []
    monkeypatch.setattr(
        bundle_module,
        "configure_logging",
        lambda: configure_calls.append(None),
    )

    BundleExtractor.multiprocess_extract_worker(
        tasks,
        context,
        ["Mesh"],
        error_count,
        log_events,
    )

    assert configure_calls == []
    assert error_count.value == 0
    event = log_events.get_nowait()
    assert event.level == "warn"
    assert event.message == (
        "Exported 0 meshes and skipped 1 meshes while extracting sample.bundle: "
        "UnityPy returned non-OBJ mesh data. Examples: mesh_a"
    )


def test_worker_sends_bundle_errors_to_log_event_queue(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    monkeypatch.setattr(
        UnityPy,
        "load",
        lambda _bundle_path: (_ for _ in ()).throw(ValueError("broken bundle")),
    )
    tasks: Queue[str] = Queue()
    tasks.put("bad.bundle")
    log_events: Queue[Any] = Queue()
    error_count = SimpleNamespace(value=0)

    BundleExtractor.multiprocess_extract_worker(
        tasks,
        context,
        ["Mesh"],
        error_count,
        log_events,
    )

    assert error_count.value == 1
    event = log_events.get_nowait()
    assert event.level == "error"
    assert event.message == (
        "Failed to extract bundle bad.bundle: ValueError: broken bundle"
    )
