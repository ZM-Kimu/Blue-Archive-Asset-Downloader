from __future__ import annotations

import struct
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
        "from .CharacterExcelTable import CharacterExcelTable\n",
        encoding="utf8",
    )
    (flat_data_dir / "CharacterExcelTable.py").write_text(
        "class CharacterExcelTable:\n    pass\n",
        encoding="utf8",
    )
    (flat_data_dir / "dump_wrapper.py").write_text(
        "def dump_table(table_instance):\n    return []\n",
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
