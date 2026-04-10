from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.application.services.extract import ExtractService
from ba_downloader.domain.models.runtime import RuntimeContext


class RecordingExtractionWorkflow:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def extract_tables(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("extract_tables")

    def extract_bundles(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("extract_bundles")

    def extract_media(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("extract_media")


class RecordingRuntimeAssetPreparer:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def prepare(self, context: RuntimeContext) -> None:
        _ = context
        self.calls.append("prepare")


class RecordingFlatbufferWorkflow:
    def __init__(
        self,
        calls: list[str],
        *,
        fail_on: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls = calls
        self.fail_on = fail_on
        self.error = error

    def dump(self, context: RuntimeContext) -> None:
        self.calls.append("dump")
        if self.fail_on == "dump" and self.error is not None:
            raise self.error
        dump_dir = Path(context.extract_dir) / "Dumps"
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / "dump.cs").write_text("// generated", encoding="utf8")

    def compile(self, context: RuntimeContext) -> None:
        self.calls.append("compile")
        if self.fail_on == "compile" and self.error is not None:
            raise self.error
        flat_data_dir = Path(context.extract_dir) / "FlatData"
        flat_data_dir.mkdir(parents=True, exist_ok=True)
        (flat_data_dir / "__init__.py").write_text("", encoding="utf8")
        (flat_data_dir / "dump_wrapper.py").write_text("", encoding="utf8")


class RecordingLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def warn(self, message: str) -> None:
        _ = message

    def error(self, message: str) -> None:
        _ = message


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=1,
        version="",
        raw_dir=str(tmp_path / "JP_Windows_RawData"),
        extract_dir=str(tmp_path / "JP_Windows_Extracted"),
        temp_dir=str(tmp_path / "JP_Windows_Temp"),
        extract_while_download=False,
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
        platform="windows",
    )


def _create_table_folder(context: RuntimeContext) -> None:
    table_dir = Path(context.raw_dir) / "Table"
    table_dir.mkdir(parents=True, exist_ok=True)
    (table_dir / "Excel.zip").write_bytes(b"placeholder")


def _create_flat_data(context: RuntimeContext) -> None:
    flat_data_dir = Path(context.extract_dir) / "FlatData"
    flat_data_dir.mkdir(parents=True, exist_ok=True)
    (flat_data_dir / "__init__.py").write_text("", encoding="utf8")
    (flat_data_dir / "dump_wrapper.py").write_text("", encoding="utf8")


def _create_dump_cs(context: RuntimeContext) -> None:
    dump_dir = Path(context.extract_dir) / "Dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    (dump_dir / "dump.cs").write_text("// generated", encoding="utf8")


def test_extract_service_skips_bootstrap_when_flatdata_exists(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    _create_flat_data(context)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractService(
        extraction_workflow,
        RecordingFlatbufferWorkflow(calls),
        RecordingRuntimeAssetPreparer(calls),
        RecordingLogger(),
    )

    service.run(context)

    assert calls == []
    assert extraction_workflow.calls == ["extract_tables"]


def test_extract_service_compiles_when_dump_cs_exists_but_flatdata_is_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    _create_dump_cs(context)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractService(
        extraction_workflow,
        RecordingFlatbufferWorkflow(calls),
        RecordingRuntimeAssetPreparer(calls),
        RecordingLogger(),
    )

    service.run(context)

    assert calls == ["compile"]
    assert extraction_workflow.calls == ["extract_tables"]
    assert (Path(context.extract_dir) / "FlatData" / "dump_wrapper.py").is_file()


def test_extract_service_bootstraps_when_dump_cs_and_flatdata_are_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractService(
        extraction_workflow,
        RecordingFlatbufferWorkflow(calls),
        RecordingRuntimeAssetPreparer(calls),
        RecordingLogger(),
    )

    service.run(context)

    assert calls == ["prepare", "dump", "compile"]
    assert extraction_workflow.calls == ["extract_tables"]
    assert (Path(context.extract_dir) / "Dumps" / "dump.cs").is_file()
    assert (Path(context.extract_dir) / "FlatData" / "__init__.py").is_file()


@pytest.mark.parametrize(
    ("fail_on", "error"),
    [
        (
            "dump",
            FileNotFoundError("Cannot find binary file or global-metadata file for Cpp2IL backend."),
        ),
        (
            "compile",
            LookupError("Failed to compile FlatData from dump.cs."),
        ),
    ],
)
def test_extract_service_translates_jp_bootstrap_failures_to_lookup_error(
    tmp_path: Path,
    fail_on: str,
    error: Exception,
) -> None:
    context = _build_context(tmp_path)
    _create_table_folder(context)
    if fail_on == "compile":
        _create_dump_cs(context)

    calls: list[str] = []
    service = ExtractService(
        RecordingExtractionWorkflow(),
        RecordingFlatbufferWorkflow(calls, fail_on=fail_on, error=error),
        RecordingRuntimeAssetPreparer(calls),
        RecordingLogger(),
    )

    with pytest.raises(LookupError, match="JP table extract prerequisites were missing") as exc_info:
        service.run(context)

    message = str(exc_info.value)
    assert context.temp_dir in message
    assert "global-metadata.dat" in message
    assert "GameAssembly.dll" in message


def test_extract_service_does_not_bootstrap_when_jp_table_folder_is_missing(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    calls: list[str] = []
    extraction_workflow = RecordingExtractionWorkflow()
    service = ExtractService(
        extraction_workflow,
        RecordingFlatbufferWorkflow(calls),
        RecordingRuntimeAssetPreparer(calls),
        RecordingLogger(),
    )

    service.run(context)

    assert calls == []
    assert extraction_workflow.calls == ["extract_tables"]
