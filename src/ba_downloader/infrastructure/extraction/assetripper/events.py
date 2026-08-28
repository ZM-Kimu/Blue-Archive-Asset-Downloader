from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, TypeAlias

EVENT_PREFIX = "BAAD_ASSETRIPPER_EVENT "
EVENT_VERSION = 0
SERIALIZE_REFERENCE_UNSUPPORTED_MESSAGE = (
    "MonoBehaviour has a field with the [SerializeReference] attribute, "
    "which is not currently supported."
)

AssetRipperPhase = Literal["loading", "processing", "exporting"]
AssetRipperLoadingStage = Literal[
    "extracting_inputs",
    "loading_files",
    "creating_collections",
    "resolving_dependencies",
]
AssetRipperProgressStage = AssetRipperLoadingStage | Literal["exporting_assets"]


@dataclass(frozen=True, slots=True)
class AssetRipperGroupContext:
    group_id: str
    index: int
    total: int


@dataclass(frozen=True, slots=True)
class AssetRipperGroupStartedEvent:
    group: AssetRipperGroupContext


@dataclass(frozen=True, slots=True)
class AssetRipperGroupCompletedEvent:
    group: AssetRipperGroupContext


@dataclass(frozen=True, slots=True)
class AssetRipperPhaseEvent:
    phase: AssetRipperPhase
    group: AssetRipperGroupContext | None = None


@dataclass(frozen=True, slots=True)
class AssetRipperProgressEvent:
    phase: Literal["loading", "exporting"]
    current: int
    total: int
    stage: AssetRipperProgressStage = "exporting_assets"
    group: AssetRipperGroupContext | None = None


@dataclass(frozen=True, slots=True)
class AssetRipperAssetLifecycleEvent:
    lifecycle: Literal["started", "completed"]
    stable_id: str
    item: str
    current: int
    total: int
    group: AssetRipperGroupContext


@dataclass(frozen=True, slots=True)
class AssetRipperLogEvent:
    level: Literal["warning", "error"]
    category: str
    message: str


@dataclass(frozen=True, slots=True)
class AssetRipperHeartbeatEvent:
    phase: Literal["processing"]
    group: AssetRipperGroupContext | None = None


@dataclass(frozen=True, slots=True)
class AssetRipperProcessorProgressEvent:
    current: int
    total: int
    processor: str
    group: AssetRipperGroupContext | None = None


@dataclass(frozen=True, slots=True)
class AssetRipperScanProgressEvent:
    current: int
    total: int
    archive_id: str


@dataclass(frozen=True, slots=True)
class AssetRipperEntryCacheProgressEvent:
    current: int
    total: int
    node_id: str


AssetRipperProcessEvent: TypeAlias = (
    AssetRipperGroupStartedEvent
    | AssetRipperGroupCompletedEvent
    | AssetRipperPhaseEvent
    | AssetRipperProgressEvent
    | AssetRipperAssetLifecycleEvent
    | AssetRipperLogEvent
    | AssetRipperHeartbeatEvent
    | AssetRipperProcessorProgressEvent
    | AssetRipperScanProgressEvent
    | AssetRipperEntryCacheProgressEvent
)


def _count(
    payload: dict[str, object], key: str, *, positive: bool = False
) -> int | None:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if value < (1 if positive else 0):
        return None
    return value


def _group(payload: dict[str, object]) -> AssetRipperGroupContext | None:
    group_id = payload.get("group_id")
    index = _count(payload, "group_index", positive=True)
    total = _count(payload, "group_total", positive=True)
    if (
        not isinstance(group_id, str)
        or not group_id
        or index is None
        or total is None
        or index > total
    ):
        return None
    return AssetRipperGroupContext(group_id, index, total)


def parse_assetripper_event(line: str) -> AssetRipperProcessEvent | None:
    if not line.startswith(EVENT_PREFIX):
        return None
    try:
        payload = json.loads(line.removeprefix(EVENT_PREFIX))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != EVENT_VERSION:
        return None

    kind = payload.get("kind")
    group = _group(payload)
    if kind in ("group_started", "group_completed"):
        if group is None:
            return None
        return (
            AssetRipperGroupStartedEvent(group)
            if kind == "group_started"
            else AssetRipperGroupCompletedEvent(group)
        )
    if kind == "phase":
        phase = payload.get("phase")
        if phase in ("loading", "processing", "exporting"):
            return AssetRipperPhaseEvent(phase, group)
        return None
    if kind == "progress":
        phase = payload.get("phase")
        stage = payload.get("stage")
        current = _count(payload, "current")
        total = _count(payload, "total", positive=True)
        valid_stages = (
            "extracting_inputs",
            "loading_files",
            "creating_collections",
            "resolving_dependencies",
            "exporting_assets",
        )
        if (
            phase in ("loading", "exporting")
            and stage in valid_stages
            and current is not None
            and total is not None
            and current <= total
            and ((phase == "loading") == (stage != "exporting_assets"))
        ):
            return AssetRipperProgressEvent(phase, current, total, stage, group)
        return None
    if kind in ("asset_started", "asset_completed"):
        stable_id = payload.get("stable_id")
        item = payload.get("item")
        current = _count(payload, "current")
        total = _count(payload, "total", positive=True)
        if (
            group is not None
            and isinstance(stable_id, str)
            and stable_id
            and isinstance(item, str)
            and item
            and current is not None
            and total is not None
            and current <= total
        ):
            return AssetRipperAssetLifecycleEvent(
                "started" if kind == "asset_started" else "completed",
                stable_id,
                item,
                current,
                total,
                group,
            )
        return None
    if kind == "log":
        level = payload.get("level")
        category = payload.get("category")
        message = payload.get("message")
        if (
            level in ("warning", "error")
            and isinstance(category, str)
            and isinstance(message, str)
        ):
            return AssetRipperLogEvent(level, category, message)
    if kind == "heartbeat" and payload.get("phase") == "processing":
        return AssetRipperHeartbeatEvent("processing", group)
    if kind == "processor_progress":
        current = _count(payload, "current", positive=True)
        total = _count(payload, "total", positive=True)
        processor = payload.get("processor")
        if (
            current is not None
            and total is not None
            and current <= total
            and isinstance(processor, str)
            and processor
        ):
            return AssetRipperProcessorProgressEvent(current, total, processor, group)
    if kind == "scan_progress":
        current = _count(payload, "current")
        total = _count(payload, "total", positive=True)
        archive_id = payload.get("archive_id")
        if (
            current is not None
            and total is not None
            and current <= total
            and isinstance(archive_id, str)
            and archive_id
        ):
            return AssetRipperScanProgressEvent(current, total, archive_id)
    if kind == "cache_progress":
        current = _count(payload, "current")
        total = _count(payload, "total", positive=True)
        node_id = payload.get("node_id")
        if (
            current is not None
            and total is not None
            and current <= total
            and isinstance(node_id, str)
            and node_id
        ):
            return AssetRipperEntryCacheProgressEvent(current, total, node_id)
    return None
