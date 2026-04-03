from __future__ import annotations

from pathlib import Path

import pytest

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extractors.table import TableExtractor


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
