from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from time import monotonic

from rich.cells import cell_len, get_character_cell_size
from rich.filesize import decimal
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
)
from rich.table import Column
from rich.text import Text

from ba_downloader.domain.ports.progress import (
    ProgressMeasure,
    ProgressReporterFactoryPort,
    ProgressReporterPort,
    ProgressState,
    preserve_terminal_progress,
)
from ba_downloader.domain.services.progress_timing import (
    ProgressTiming,
    ProgressTimingEstimator,
)
from ba_downloader.infrastructure.logging.runtime import get_console

_STAGE_LABELS = {
    "verifying": "Verifying",
    "downloading": "Downloading",
    "scanning": "Scanning",
    "cache_fill": "Preparing cache",
    "loading": "Loading",
    "processing": "Processing",
    "exporting": "Exporting",
    "extracting": "Extracting",
    "validating": "Validating",
    "publishing": "Publishing",
    "complete": "Complete",
    "failed": "Failed",
    "cancelled": "Cancelled",
}

_TITLE_MAX_WIDTH = 26
_TITLE_MIN_WIDTH = 14
_BAR_MAX_WIDTH = 24
_BAR_MIN_WIDTH = 10
_FIXED_LAYOUT_WIDTH = 8


def _format_measure(measure: ProgressMeasure | None) -> str:
    if measure is None:
        return ""
    if measure.unit == "bytes":
        return _format_bytes_measure(measure.completed, measure.total)
    return f"{measure.completed}/{measure.total} {measure.unit}"


def _format_bytes_measure(completed: int, total: int) -> str:
    suffixes = ("bytes", "KB", "MB", "GB", "TB", "PB")
    scale = 1.0
    suffix = suffixes[0]
    for suffix in suffixes:
        if total < scale * 1000 or suffix == suffixes[-1]:
            break
        scale *= 1000
    if scale == 1:
        return f"{completed}/{total} {suffix}"
    return f"{completed / scale:.1f}/{total / scale:.1f} {suffix}"


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-:--:--"
    value = max(round(seconds), 0)
    hours, remainder = divmod(value, 3600)
    minutes, seconds_value = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds_value:02d}"


def _take_cells(value: str, maximum: int, *, from_end: bool = False) -> str:
    if maximum <= 0:
        return ""
    characters = reversed(value) if from_end else iter(value)
    selected: list[str] = []
    used = 0
    for character in characters:
        width = get_character_cell_size(character)
        if used + width > maximum:
            break
        selected.append(character)
        used += width
    if from_end:
        selected.reverse()
    return "".join(selected)


def _middle_elide(value: str, maximum: int) -> str:
    if cell_len(value) <= maximum:
        return value
    if maximum <= 1:
        return "…" if maximum == 1 else ""
    remaining = maximum - 1
    tail_width = max(remaining // 2, 1)
    head_width = remaining - tail_width
    return (
        _take_cells(value, head_width)
        + "…"
        + _take_cells(value, tail_width, from_end=True)
    )


def _right_elide(value: str, maximum: int) -> str:
    if cell_len(value) <= maximum:
        return value
    if maximum <= 1:
        return "…" if maximum == 1 else ""
    return _take_cells(value, maximum - 1) + "…"


def _join_parts(parts: list[Text], separator: str = "  ") -> Text:
    result = Text()
    for index, part in enumerate(parts):
        if index:
            result.append(separator)
        result.append(part)
    return result


class _DynamicColumn(ProgressColumn):
    def __init__(
        self,
        render_callback: Callable[[], Text],
        *,
        table_column: Column,
    ) -> None:
        super().__init__(table_column=table_column)
        self._render_callback = render_callback

    def render(self, task: Task) -> Text:
        _ = task
        return self._render_callback()


class RichProgressReporter(ProgressReporterPort):
    def __init__(
        self,
        initial_state: ProgressState,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._state = initial_state
        self._lock = Lock()
        self._timing = ProgressTimingEstimator(clock=clock)
        self._prepared_status = Text()
        self._prepared_title = Text()
        self._title_table_column = Column(
            width=_TITLE_MAX_WIDTH,
            min_width=_TITLE_MIN_WIDTH,
            no_wrap=True,
            overflow="ellipsis",
        )
        self._bar_column = BarColumn(bar_width=_BAR_MAX_WIDTH)
        self._progress = Progress(
            SpinnerColumn(),
            _DynamicColumn(
                self._render_title,
                table_column=self._title_table_column,
            ),
            self._bar_column,
            _DynamicColumn(
                self._render_status,
                table_column=Column(no_wrap=True, overflow="crop"),
            ),
            console=get_console(),
            transient=False,
        )
        self._task_id: TaskID | None = None

    def __enter__(self) -> RichProgressReporter:
        self._timing.start(self._state)
        self._progress.start()
        measure = self._display_measure()
        self._task_id = self._progress.add_task(
            self._state.label,
            total=measure.total,
            completed=measure.completed,
        )
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _display_measure(self) -> ProgressMeasure:
        return (
            self._state.overall or self._state.current or ProgressMeasure(0, 0, "items")
        )

    def update(self, state: ProgressState) -> None:
        with self._lock:
            self._state = preserve_terminal_progress(self._state, state)
            state = self._state
            self._timing.observe(state)
            measure = self._display_measure()
        if self._task_id is None:
            return
        self._progress.update(
            self._task_id,
            description=state.label,
            completed=measure.completed,
            total=measure.total,
        )

    def _render_title(self) -> Text:
        with self._lock:
            state = self._state
            self._prepare_layout(state, self._timing.snapshot(state))
            return self._prepared_title.copy()

    def _render_status(self) -> Text:
        with self._lock:
            state = self._state
            self._prepare_layout(state, self._timing.snapshot(state))
            return self._prepared_status.copy()

    def _prepare_layout(self, state: ProgressState, timing: ProgressTiming) -> None:
        title = f"[{state.label}] {_STAGE_LABELS[state.stage]}"
        natural_title_width = min(
            max(cell_len(title) + 1, _TITLE_MIN_WIDTH),
            _TITLE_MAX_WIDTH,
        )
        title_width = natural_title_width
        bar_width = _BAR_MAX_WIDTH
        console_width = max(self._progress.console.width, 1)

        variants = (
            (48, True, True, True, True, True),
            (32, True, True, True, True, True),
            (16, True, True, True, True, True),
            (0, True, True, True, True, True),
            (0, False, True, True, True, True),
            (0, False, False, True, True, True),
            (0, False, False, False, True, True),
            (0, False, False, False, False, True),
            (0, False, False, False, False, False),
        )
        selected = self._build_status(
            state,
            timing,
            item_width=0,
            include_workers=False,
            include_zero_failures=False,
            include_current=False,
            include_speed=False,
            include_pending=False,
        )
        for variant in variants:
            candidate = self._build_status(
                state,
                timing,
                item_width=variant[0],
                include_workers=variant[1],
                include_zero_failures=variant[2],
                include_current=variant[3],
                include_speed=variant[4],
                include_pending=variant[5],
            )
            available = self._status_width(console_width, title_width, bar_width)
            if cell_len(candidate.plain) <= available:
                selected = candidate
                break
        else:
            required = cell_len(selected.plain)
            available = self._status_width(console_width, title_width, bar_width)
            shrink = max(required - available, 0)
            bar_width = max(_BAR_MAX_WIDTH - shrink, _BAR_MIN_WIDTH)
            available = self._status_width(console_width, title_width, bar_width)
            shrink = max(required - available, 0)
            title_width = max(title_width - shrink, _TITLE_MIN_WIDTH)

        self._title_table_column.width = title_width
        self._bar_column.bar_width = bar_width
        title_style = {
            "complete": "green",
            "failed": "red",
            "cancelled": "yellow",
        }.get(state.stage, "progress.description")
        self._prepared_title = Text(
            _right_elide(title, max(title_width - 1, 1)) + " ",
            style=title_style,
        )
        self._prepared_status = selected

    @staticmethod
    def _status_width(console_width: int, title_width: int, bar_width: int) -> int:
        return max(
            console_width - title_width - bar_width - _FIXED_LAYOUT_WIDTH,
            1,
        )

    @staticmethod
    def _build_status(
        state: ProgressState,
        timing: ProgressTiming,
        *,
        item_width: int,
        include_workers: bool,
        include_zero_failures: bool,
        include_current: bool,
        include_speed: bool,
        include_pending: bool,
    ) -> Text:
        display_measure = state.overall or state.current
        parts = [Text(_format_measure(display_measure), style="progress.data.speed")]

        activity: list[Text] = []
        if include_current and state.overall is not None and state.current is not None:
            activity.append(Text(_format_measure(state.current)))
        if include_pending and state.pending is not None:
            style = "yellow" if state.pending else "dim"
            activity.append(Text(f"pending {state.pending}", style=style))
        if include_workers and state.workers is not None:
            activity.append(
                Text(
                    f"workers {state.workers.active}/{state.workers.limit}",
                    style="cyan",
                )
            )
        details = [value for value in (state.item, state.message) if value]
        if item_width and details:
            detail = "  ".join(dict.fromkeys(details))
            activity.append(Text(_middle_elide(detail, item_width)))
        if activity:
            parts.append(_join_parts(activity))

        if state.failures or include_zero_failures:
            failure_style = "red" if state.failures else "dim"
            parts.append(Text(f"failed {state.failures}", style=failure_style))

        if (
            include_speed
            and display_measure is not None
            and display_measure.unit == "bytes"
            and timing.rate_per_second is not None
        ):
            parts.append(
                Text(f"{decimal(round(timing.rate_per_second))}/s", style="cyan")
            )

        parts.append(
            Text(f"elapsed {_format_duration(timing.elapsed_seconds)}", style="dim")
        )
        parts.append(
            Text(f"ETA {_format_duration(timing.eta_seconds)}", style="bright_blue")
        )
        result = Text(" ")
        result.append(_join_parts(parts))
        return result

    def stop(self) -> None:
        self._progress.stop()


class NullProgressReporter(ProgressReporterPort):
    def __enter__(self) -> NullProgressReporter:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def update(self, state: ProgressState) -> None:
        _ = state

    def stop(self) -> None:
        return None


class RichProgressReporterFactory(ProgressReporterFactoryPort):
    def create(self, initial_state: ProgressState) -> RichProgressReporter:
        return RichProgressReporter(initial_state)


class NullProgressReporterFactory(ProgressReporterFactoryPort):
    def create(self, initial_state: ProgressState) -> NullProgressReporter:
        _ = initial_state
        return NullProgressReporter()
