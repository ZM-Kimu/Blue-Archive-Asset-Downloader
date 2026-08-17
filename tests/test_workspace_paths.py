from pathlib import Path
from typing import Literal

from ba_downloader.domain.models.asset import AssetRecord, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.storage.workspace_paths import (
    extracted_dumps_root,
    extracted_schema_root,
    extracted_type_root,
    raw_resource_path,
    raw_type_root,
    uses_v3_workspace,
)


def _context(
    tmp_path: Path,
    *,
    workspace_mode: Literal["legacy", "v3"] = "legacy",
) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        platform="android",
        threads=1,
        version="1",
        raw_dir=str(tmp_path / "raw"),
        extract_dir=str(tmp_path / "extract"),
        temp_dir=str(tmp_path / "temp"),
        resource_type=("table",),
        proxy_url="",
        max_retries=0,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
        workspace_mode=workspace_mode,
    )


def test_legacy_context_does_not_depend_on_raw_directory_name(tmp_path: Path) -> None:
    context = _context(tmp_path)

    assert not uses_v3_workspace(context)
    assert raw_type_root(context, AssetType.table) == tmp_path / "raw" / "Table"


def test_v3_context_uses_lowercase_resource_roots(tmp_path: Path) -> None:
    context = _context(tmp_path, workspace_mode="v3")
    resource = AssetRecord(
        path="Table/example.bytes",
        asset_type=AssetType.table,
        size=1,
        checksum="",
        url="https://example.invalid/example.bytes",
    )

    assert uses_v3_workspace(context)
    assert raw_type_root(context, AssetType.table) == tmp_path / "raw" / "tables"
    assert raw_resource_path(context, resource) == (
        tmp_path / "raw" / "tables" / "example.bytes"
    )
    assert extracted_type_root(context, AssetType.table) == (
        tmp_path / "extract" / "tables" / "semantic"
    )
    assert extracted_type_root(context, AssetType.media) == (
        tmp_path / "extract" / "media"
    )
    assert extracted_schema_root(context, "flatbuffer") == (
        tmp_path / "extract" / "schemas" / "flatbuffers"
    )
    assert extracted_dumps_root(context) == tmp_path / "extract" / "dumps"
