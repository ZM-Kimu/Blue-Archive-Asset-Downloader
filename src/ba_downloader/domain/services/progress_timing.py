from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from ba_downloader.domain.ports.progress import ProgressMeasure, ProgressState

_ETA_UNAVAILABLE_STAGES = {
    "validating",
    "publishing",
    "failed",
    "cancelled",
}


@dataclass(frozen=True, slots=True)
class ProgressTiming:
    elapsed_seconds: float
    eta_seconds: float | None
    rate_per_second: float | None

    def to_wire(self) -> dict[str, float | None]:
        return {
            "elapsed_seconds": self.elapsed_seconds,
            "eta_seconds": self.eta_seconds,
            "rate_per_second": self.rate_per_second,
        }


class ProgressTimingEstimator:
    """Track elapsed time and a short-window rate for one progress task."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        window_seconds: float = 30.0,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("Progress timing window must be positive.")
        self._clock = clock
        self._window_seconds = window_seconds
        self._started_at: float | None = None
        self._measure_key: tuple[str, int] | None = None
        self._samples: deque[tuple[float, int]] = deque()

    def start(self, state: ProgressState) -> None:
        now = self._clock()
        self._started_at = now
        self._measure_key = None
        self._samples.clear()
        self.observe(state, now=now)

    def observe(self, state: ProgressState, *, now: float | None = None) -> None:
        timestamp = self._clock() if now is None else now
        if self._started_at is None:
            self._started_at = timestamp
        measure = state.overall
        if measure is None:
            return
        key = (measure.unit, measure.total)
        if key != self._measure_key or (
            self._samples and measure.completed < self._samples[-1][1]
        ):
            self._measure_key = key
            self._samples.clear()
        if not self._samples or measure.completed != self._samples[-1][1]:
            self._samples.append((timestamp, measure.completed))
        self._prune(timestamp)

    def snapshot(self, state: ProgressState) -> ProgressTiming:
        now = self._clock()
        if self._started_at is None:
            self.start(state)
            now = self._clock()
        self._prune(now)
        started_at = self._started_at if self._started_at is not None else now
        elapsed = max(now - started_at, 0.0)
        rate = self._rate(now)
        eta = self._eta(state, rate)
        return ProgressTiming(elapsed, eta, rate)

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while len(self._samples) > 1 and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def _rate(self, now: float) -> float | None:
        if len(self._samples) < 2:
            return None
        first_time, first_completed = self._samples[0]
        last_time, last_completed = self._samples[-1]
        duration = last_time - first_time
        advanced = last_completed - first_completed
        if duration <= 0 or advanced <= 0 or now - last_time > self._window_seconds:
            return None
        return advanced / duration

    @staticmethod
    def _eta(state: ProgressState, rate: float | None) -> float | None:
        if state.stage == "complete":
            return 0.0
        if state.stage in _ETA_UNAVAILABLE_STAGES:
            return None
        if state.eta_seconds is not None:
            return state.eta_seconds
        measure: ProgressMeasure | None = state.overall
        if (
            measure is None
            or measure.completed <= 0
            or measure.completed >= measure.total
            or rate is None
        ):
            return None
        return max((measure.total - measure.completed) / rate, 0.0)
