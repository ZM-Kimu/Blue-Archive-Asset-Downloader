from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, TypeAlias

EVENT_PREFIX = "BAAD_ASSETRIPPER_EVENT "
EVENT_VERSION = 5
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
class AssetRipperPhaseEvent:
    phase: AssetRipperPhase


@dataclass(frozen=True, slots=True)
class AssetRipperProgressEvent:
    phase: Literal["loading", "exporting"]
    current: int
    total: int
    stage: AssetRipperProgressStage = "exporting_assets"


@dataclass(frozen=True, slots=True)
class AssetRipperLogEvent:
    level: Literal["warning", "error"]
    category: str
    message: str


@dataclass(frozen=True, slots=True)
class AssetRipperHeartbeatEvent:
    phase: Literal["processing"]


@dataclass(frozen=True, slots=True)
class AssetRipperProcessorProgressEvent:
    current: int
    total: int
    processor: str


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
    AssetRipperPhaseEvent
    | AssetRipperProgressEvent
    | AssetRipperLogEvent
    | AssetRipperHeartbeatEvent
    | AssetRipperProcessorProgressEvent
    | AssetRipperScanProgressEvent
    | AssetRipperEntryCacheProgressEvent
)


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
    if kind == "phase":
        phase = payload.get("phase")
        if phase in ("loading", "processing", "exporting"):
            return AssetRipperPhaseEvent(phase)
        return None
    if kind == "progress":
        phase = payload.get("phase")
        stage = payload.get("stage")
        current = payload.get("current")
        total = payload.get("total")
        if (
            phase in ("loading", "exporting")
            and (
                stage
                in (
                    "extracting_inputs",
                    "loading_files",
                    "creating_collections",
                    "resolving_dependencies",
                    "exporting_assets",
                )
            )
            and isinstance(current, int)
            and not isinstance(current, bool)
            and isinstance(total, int)
            and not isinstance(total, bool)
            and 0 <= current <= total
            and total > 0
            and (
                (phase == "loading" and stage != "exporting_assets")
                or (phase == "exporting" and stage == "exporting_assets")
            )
        ):
            return AssetRipperProgressEvent(phase, current, total, stage)
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
    if kind == "heartbeat":
        phase = payload.get("phase")
        if phase == "processing":
            return AssetRipperHeartbeatEvent(phase)
    if kind == "processor_progress":
        current = payload.get("current")
        total = payload.get("total")
        processor = payload.get("processor")
        if (
            isinstance(current, int)
            and not isinstance(current, bool)
            and isinstance(total, int)
            and not isinstance(total, bool)
            and 0 < current <= total
            and isinstance(processor, str)
            and bool(processor)
        ):
            return AssetRipperProcessorProgressEvent(current, total, processor)
    if kind == "scan_progress":
        current = payload.get("current")
        total = payload.get("total")
        archive_id = payload.get("archive_id")
        if (
            isinstance(current, int)
            and not isinstance(current, bool)
            and isinstance(total, int)
            and not isinstance(total, bool)
            and 0 <= current <= total
            and total > 0
            and isinstance(archive_id, str)
            and bool(archive_id)
        ):
            return AssetRipperScanProgressEvent(current, total, archive_id)
    if kind == "cache_progress":
        current = payload.get("current")
        total = payload.get("total")
        node_id = payload.get("node_id")
        if (
            isinstance(current, int)
            and not isinstance(current, bool)
            and isinstance(total, int)
            and not isinstance(total, bool)
            and 0 <= current <= total
            and total > 0
            and isinstance(node_id, str)
            and bool(node_id)
        ):
            return AssetRipperEntryCacheProgressEvent(current, total, node_id)
    return None
