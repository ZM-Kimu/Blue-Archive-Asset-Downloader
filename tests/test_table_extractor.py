from __future__ import annotations

import json
import struct
import zlib
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extractors.table import (
    GeneratedDumpWrapperError,
    MalformedTablePayloadError,
    TableDecryptError,
    TableExtractor,
    UnsupportedSchemaError,
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


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=4,
        version="1.0.0",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _create_flat_data_package(flat_data_dir: Path) -> None:
    flat_data_dir.mkdir(parents=True, exist_ok=True)
    (flat_data_dir / "__init__.py").write_text(
        "from .CharacterExcelTable import CharacterExcelTable\n"
        "from .GroundGridFlat import GroundGridFlat\n",
        encoding="utf8",
    )
    (flat_data_dir / "CharacterExcelTable.py").write_text(
        "class CharacterExcelTable:\n"
        "    @classmethod\n"
        "    def GetRootAs(cls, data):\n"
        "        return cls()\n",
        encoding="utf8",
    )
    (flat_data_dir / "GroundGridFlat.py").write_text(
        "class GroundGridFlat:\n"
        "    @classmethod\n"
        "    def GetRootAs(cls, data):\n"
        "        return cls()\n",
        encoding="utf8",
    )
    (flat_data_dir / "dump_wrapper.py").write_text(
        "def dump_table(table_instance):\n"
        "    return [{\"kind\": \"excel\"}]\n\n"
        "def dump_GroundGridFlat(excel_instance, password: bytes = b\"\"):\n"
        "    return {\"kind\": \"ground_grid\"}\n",
        encoding="utf8",
    )


def test_table_extractor_loads_generated_flat_data_from_directory(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)

    extractor = TableExtractor.from_context(context)

    assert "characterexceltable" in extractor.lower_fb_name_modules
    assert extractor.dump_wrapper_lib.__name__.endswith(".dump_wrapper")


def test_table_extractor_raises_when_flat_data_directory_is_missing(tmp_path: Path) -> None:
    context = _build_context(tmp_path)

    with pytest.raises(FileNotFoundError, match="FlatData directory does not exist"):
        TableExtractor.from_context(context)


@pytest.mark.parametrize(
    ("error_type", "expected_fragment"),
    [
        (UnsupportedSchemaError, "unsupported schema"),
        (TableDecryptError, "decrypt failed"),
        (GeneratedDumpWrapperError, "dump wrapper failed"),
    ],
)
def test_extract_zip_file_warns_with_explicit_processing_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error_type: type[Exception],
    expected_fragment: str,
) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    zip_path = table_dir / "Excel.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("CharacterExcelTable.bytes", b"payload")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flat_data_dir),
        logger=logger,
    )

    def fail_processing(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        raise error_type(expected_fragment)

    monkeypatch.setattr(extractor, "_process_zip_file", fail_processing)

    extractor.extract_zip_file("Excel.zip")

    assert any(expected_fragment in message for message in logger.warn_messages)
    assert logger.warn_messages[-1] == "Skipped 1 entries while extracting Excel.zip."
    assert not (Path(context.extract_dir) / "Excel").exists()


def test_dump_encrypted_table_raises_generated_wrapper_error_on_stop_iteration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)
    extractor = TableExtractor(
        str(Path(context.raw_dir) / "Table"),
        str(Path(context.extract_dir)),
        str(flat_data_dir),
    )

    FakeFlatbufferClass = type(
        "CharacterExcelTable",
        (),
        {
            "GetRootAs": staticmethod(lambda data: data),
        },
    )

    monkeypatch.setattr(
        extractor,
        "dump_wrapper_lib",
        type(
            "WrapperModule",
            (),
            {
                "dump_table": staticmethod(lambda flat_buffer: (_ for _ in ()).throw(StopIteration())),
            },
        )(),
    )

    with pytest.raises(
        GeneratedDumpWrapperError,
        match="could not resolve a table dump",
    ):
        extractor._dump_encrypted_table(FakeFlatbufferClass, b"payload")


def test_dump_flatbuffer_payload_raises_malformed_error_on_struct_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)
    extractor = TableExtractor(
        str(Path(context.raw_dir) / "Table"),
        str(Path(context.extract_dir)),
        str(flat_data_dir),
    )

    FakeFlatbufferClass = type(
        "CharacterExcelTable",
        (),
        {
            "GetRootAs": staticmethod(lambda data: data),
        },
    )

    monkeypatch.setattr(
        extractor,
        "dump_wrapper_lib",
        type(
            "WrapperModule",
            (),
            {
                "dump_CharacterExcelTable": staticmethod(
                    lambda flat_buffer: (_ for _ in ()).throw(struct.error("bad offset"))
                ),
            },
        )(),
    )

    with pytest.raises(
        MalformedTablePayloadError,
        match="Malformed flatbuffer payload",
    ):
        extractor._dump_flatbuffer_payload(FakeFlatbufferClass, b"payload")


def test_extract_zip_file_writes_excel_artifact(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "Excel.zip", "w") as archive:
        archive.writestr("CharacterExcelTable.bytes", b"payload")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flat_data_dir),
        logger=logger,
    )

    extractor.extract_zip_file("Excel.zip")

    output_path = Path(context.extract_dir) / "Excel" / "CharacterExcelTable.json"
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf8")) == [{"kind": "excel"}]
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_ground_grid_patch_artifact(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr("sb_02_trainroof_p01_d.bytes", b"\xff\x00grid")

    with ZipFile(table_dir / "TablePatchPack_GroundGrid_11.zip", "w") as outer_archive:
        outer_archive.writestr(
            "sb_02_trainroof_p01_d.zip",
            inner_zip_buffer.getvalue(),
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flat_data_dir),
        logger=logger,
    )

    extractor.extract_zip_file("TablePatchPack_GroundGrid_11.zip")

    output_path = (
        Path(context.extract_dir)
        / "TablePatchPack_GroundGrid_11"
        / "sb_02_trainroof_p01_d"
        / "GroundGridFlat.json"
    )
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf8")) == {
        "kind": "ground_grid"
    }
    assert logger.warn_messages == []
    assert logger.error_messages == []


def test_extract_zip_file_writes_ground_stage_raw_payloads(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr("1052103_02_s3_02_excavation_p02_n.bytes", b"\xff\x00stage")

    with ZipFile(table_dir / "TablePatchPack_GroundStage_1.zip", "w") as outer_archive:
        outer_archive.writestr(
            "1052103_02_s3_02_excavation_p02_n.zip",
            inner_zip_buffer.getvalue(),
        )

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flat_data_dir),
        logger=logger,
    )

    extractor.extract_zip_file("TablePatchPack_GroundStage_1.zip")

    output_path = (
        Path(context.extract_dir)
        / "TablePatchPack_GroundStage_1"
        / "1052103_02_s3_02_excavation_p02_n"
        / "1052103_02_s3_02_excavation_p02_n.bytes"
    )
    assert output_path.is_file()
    assert output_path.read_bytes() == b"\xff\x00stage"
    assert logger.warn_messages == []
    assert logger.error_messages == []
    assert logger.info_messages == [
        "Extracted raw GroundStage payloads from TablePatchPack_GroundStage_1.zip; semantic parser is not implemented yet."
    ]


def test_extract_zip_file_skips_ground_stage_entries_with_zlib_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)

    inner_zip_buffer = BytesIO()
    with ZipFile(inner_zip_buffer, "w") as inner_archive:
        inner_archive.writestr("broken_stage.bytes", b"\xff\x00stage")

    with ZipFile(table_dir / "TablePatchPack_GroundStage_1.zip", "w") as outer_archive:
        outer_archive.writestr("broken_stage.zip", inner_zip_buffer.getvalue())

    original_read = ZipFile.read

    def flaky_read(self, name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "broken_stage.bytes":
            raise zlib.error("invalid stored block lengths")
        return original_read(self, name, *args, **kwargs)

    monkeypatch.setattr(ZipFile, "read", flaky_read)

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flat_data_dir),
        logger=logger,
    )

    extractor.extract_zip_file("TablePatchPack_GroundStage_1.zip")

    assert logger.error_messages == []
    assert any("invalid stored block lengths" in message for message in logger.warn_messages)
    assert logger.warn_messages[-1] == (
        "Skipped 1 entries while extracting TablePatchPack_GroundStage_1.zip."
    )
    assert not (Path(context.extract_dir) / "TablePatchPack_GroundStage_1").exists()


def test_extract_zip_file_warns_for_rhythm_beatmap_without_output_dir(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    _create_flat_data_package(flat_data_dir)
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(table_dir / "RhythmBeatmapData.zip", "w") as archive:
        archive.writestr("8040101_example.bytes", b"\xff\x00beatmap")

    logger = RecordingLogger()
    extractor = TableExtractor(
        str(table_dir),
        str(Path(context.extract_dir)),
        str(flat_data_dir),
        logger=logger,
    )

    extractor.extract_zip_file("RhythmBeatmapData.zip")

    assert logger.warn_messages == [
        "Skipping RhythmBeatmapData.zip: beatmap semantic parser is not implemented yet."
    ]
    assert logger.error_messages == []
    assert not (Path(context.extract_dir) / "RhythmBeatmapData").exists()
