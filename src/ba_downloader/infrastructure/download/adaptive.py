from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(slots=True)
class AdaptiveDownloadState:
    upper_bound: int
    target_concurrency: int
    success_since_adjustment: int = 0


def classify_download_failure(exc: Exception) -> str:
    message = str(exc).lower()
    if "timed out" in message:
        return "timeout"
    if "429" in message or "403" in message:
        return "throttled"
    if any(
        marker in message
        for marker in ("connection", "reset", "aborted", "broken pipe")
    ):
        return "connection"
    if any(
        marker in message
        for marker in ("incomplete response body", "partial", "size mismatch")
    ):
        return "connection"
    return "other"


def decrease_target_concurrency(state: AdaptiveDownloadState) -> bool:
    state.success_since_adjustment = 0
    next_target = max(1, ceil(state.target_concurrency / 2))
    if next_target == state.target_concurrency:
        return False
    state.target_concurrency = next_target
    return True


def record_download_success(state: AdaptiveDownloadState) -> bool:
    state.success_since_adjustment += 1
    if state.success_since_adjustment < 2:
        return False

    state.success_since_adjustment = 0
    if state.target_concurrency >= state.upper_bound:
        return False

    state.target_concurrency += 1
    return True
