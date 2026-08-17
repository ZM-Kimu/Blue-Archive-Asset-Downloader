from __future__ import annotations

from pathlib import Path

from ba_downloader.domain.models.asset import AssetRecord, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext

_NEW_RESOURCE_ROOTS = {
    AssetType.table: "tables",
    AssetType.media: "media",
    AssetType.bundle: "bundles",
}
_OLD_RESOURCE_ROOTS = {
    AssetType.table: "Table",
    AssetType.media: "Media",
    AssetType.bundle: "Bundle",
}
_NEW_EXTRACTED_ROOTS = {
    AssetType.table: Path("tables") / "semantic",
    AssetType.media: Path("media"),
    AssetType.bundle: Path("bundles"),
}
_OLD_EXTRACTED_ROOTS = {
    AssetType.table: Path("Table"),
    AssetType.media: Path("Media"),
    AssetType.bundle: Path("Bundle"),
}


def uses_v3_workspace(context: RuntimeContext) -> bool:
    return context.workspace_mode == "v3"


def raw_resource_path(context: RuntimeContext, resource: AssetRecord) -> Path:
    raw_root = Path(context.raw_dir)
    if not uses_v3_workspace(context):
        return raw_root / resource.path
    relative = Path(resource.path)
    if relative.parts and relative.parts[0].casefold() in {
        "table",
        "media",
        "bundle",
    }:
        relative = Path(*relative.parts[1:])
    return raw_root / _NEW_RESOURCE_ROOTS[resource.asset_type] / relative


def raw_type_root(context: RuntimeContext, asset_type: AssetType) -> Path:
    root_name = (
        _NEW_RESOURCE_ROOTS[asset_type]
        if uses_v3_workspace(context)
        else _OLD_RESOURCE_ROOTS[asset_type]
    )
    return Path(context.raw_dir) / root_name


def extracted_type_root(context: RuntimeContext, asset_type: AssetType) -> Path:
    relative = (
        _NEW_EXTRACTED_ROOTS[asset_type]
        if uses_v3_workspace(context)
        else _OLD_EXTRACTED_ROOTS[asset_type]
    )
    return Path(context.extract_dir) / relative


def extracted_schema_root(context: RuntimeContext, schema: str) -> Path:
    if context.schema_snapshot_root:
        return (
            Path(context.schema_snapshot_root)
            / "schemas"
            / schema.replace("flatbuffer", "flatbuffers")
        )
    if uses_v3_workspace(context):
        names = {"flatbuffer": "flatbuffers", "memorypack": "memorypack"}
        return Path(context.extract_dir) / "schemas" / names[schema]
    names = {"flatbuffer": "FlatBufferData", "memorypack": "MemoryPackData"}
    return Path(context.extract_dir) / names[schema]


def extracted_dumps_root(context: RuntimeContext) -> Path:
    if context.schema_snapshot_root:
        return Path(context.schema_snapshot_root) / "dumps"
    name = "dumps" if uses_v3_workspace(context) else "Dumps"
    return Path(context.extract_dir) / name
