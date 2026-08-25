from __future__ import annotations

import json
from pathlib import Path

from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.infrastructure.storage.table_metadata_manifest import (
    JpTableMetadataManifestStore,
)
from support import build_execution_context


def _build_resources() -> AssetCollection:
    resources = AssetCollection()
    resources.add(
        "https://example.invalid/Table/TablePatchPack_GroundStage_1.zip",
        "Table/TablePatchPack_GroundStage_1.zip",
        123,
        "456",
        "crc",
        AssetType.table,
        {"includes": ["EN0010_VeryHard.zip"]},
    )
    resources.add(
        "https://example.invalid/Bundle/ignored.bundle",
        "Bundle/ignored.bundle",
        1,
        "0",
        "crc",
        AssetType.bundle,
    )
    return resources


def test_jp_table_metadata_manifest_round_trips_table_includes(
    tmp_path: Path,
) -> None:
    context = build_execution_context(
        tmp_path,
        region="jp",
        platform="android",
        version="1.70.436321",
    )
    store = JpTableMetadataManifestStore()

    store.write(context, _build_resources())

    manifest_path = (
        context.workspace.temp_state
        / "catalog"
        / "jp"
        / "android"
        / "1.70.436321.table-metadata.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 0
    assert payload["region"] == "jp"
    assert payload["platform"] == "android"
    assert payload["version"] == "1.70.436321"
    assert payload["tables"] == [
        {
            "url": "https://example.invalid/Table/TablePatchPack_GroundStage_1.zip",
            "path": "Table/TablePatchPack_GroundStage_1.zip",
            "size": 123,
            "crc": "456",
            "includes": ["EN0010_VeryHard.zip"],
        }
    ]

    loaded = store.load(context)

    assert loaded is not None
    assert [item.path for item in loaded] == ["Table/TablePatchPack_GroundStage_1.zip"]
    assert loaded[0].metadata == {"includes": ["EN0010_VeryHard.zip"]}
    assert not (tmp_path / ".ba-downloader" / "catalog").exists()


def test_jp_table_metadata_manifest_rejects_stale_payload(tmp_path: Path) -> None:
    context = build_execution_context(
        tmp_path,
        region="jp",
        platform="android",
        version="1.70.436321",
    )
    store = JpTableMetadataManifestStore()
    store.write(context, _build_resources())
    manifest_path = store.manifest_path(context)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["version"] = "stale"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    assert store.load(context) is None
