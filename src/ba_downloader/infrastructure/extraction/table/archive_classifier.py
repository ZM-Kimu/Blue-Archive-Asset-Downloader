from __future__ import annotations

from dataclasses import dataclass
from os import path

TableArchiveRouteKey = str

ROUTE_RHYTHM_BEATMAP = "rhythm_beatmap"
ROUTE_GROUND_GRID_PATCH = "ground_grid_patch"
ROUTE_GROUND_NODE_LAYER_PATCH = "ground_node_layer_patch"
ROUTE_GROUND_STAGE_PATCH = "ground_stage_patch"
ROUTE_RAW = "raw"
ROUTE_UNSUPPORTED = "unsupported"
ROUTE_STANDARD = "standard"

SHARED_TABLE_ARCHIVE_ROUTE_KEYS = frozenset(
    {
        ROUTE_RHYTHM_BEATMAP,
        ROUTE_GROUND_GRID_PATCH,
        ROUTE_GROUND_NODE_LAYER_PATCH,
        ROUTE_GROUND_STAGE_PATCH,
        ROUTE_RAW,
        ROUTE_STANDARD,
    }
)


@dataclass(frozen=True, slots=True)
class TableArchiveRoute:
    kind: TableArchiveRouteKey
    schema_name: str = ""
    info_message: str | None = None


_RHYTHM_BEATMAP_ARCHIVE_NAME = "RhythmBeatmapData.zip"


def classify_table_archive(file_name: str) -> TableArchiveRoute:
    archive_name = path.basename(file_name)

    if archive_name == _RHYTHM_BEATMAP_ARCHIVE_NAME:
        return TableArchiveRoute(
            ROUTE_RHYTHM_BEATMAP,
            info_message=(
                f"Extracted raw rhythm beatmap payloads from {archive_name}; "
                "semantic parser is not implemented yet."
            ),
        )

    if archive_name.startswith("TablePatchPack_"):
        if "GroundGrid" in archive_name:
            return TableArchiveRoute(ROUTE_GROUND_GRID_PATCH)
        if "GroundNodeLayer" in archive_name:
            return TableArchiveRoute(ROUTE_GROUND_NODE_LAYER_PATCH)
        if "GroundStage" in archive_name:
            return TableArchiveRoute(ROUTE_GROUND_STAGE_PATCH)

    return TableArchiveRoute(ROUTE_STANDARD)
