from __future__ import annotations

from io import StringIO

import pytest
from rich.cells import cell_len
from rich.console import Console

from ba_downloader.domain.ports.progress import (
    ProgressGroup,
    ProgressMeasure,
    ProgressState,
    ProgressWorkers,
)
from ba_downloader.domain.services.progress_timing import ProgressTimingEstimator
from ba_downloader.infrastructure.progress import rich_progress


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _reporter(
    monkeypatch: pytest.MonkeyPatch,
    state: ProgressState,
    *,
    width: int,
    clock: FakeClock,
) -> rich_progress.RichProgressReporter:
    console = Console(
        file=StringIO(),
        width=width,
        force_terminal=False,
        color_system="standard",
    )
    monkeypatch.setattr(rich_progress, "get_console", lambda: console)
    return rich_progress.RichProgressReporter(state, clock=clock)


def test_rich_bundle_progress_keeps_one_task_and_explicit_group_eta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    reporter = _reporter(
        monkeypatch,
        ProgressState(
            "Bundles",
            "loading",
            overall=ProgressMeasure(0, 52, "groups"),
        ),
        width=220,
        clock=clock,
    )

    with reporter:
        task = reporter._progress.tasks[0]
        started_at = task.start_time
        clock.advance(10)
        reporter.update(
            ProgressState(
                "Bundles",
                "exporting",
                overall=ProgressMeasure(1, 52, "groups"),
                current=ProgressMeasure(312, 647, "assets"),
                group=ProgressGroup("group-02", 2, 52),
                item="Cafe_CH0347",
                eta_seconds=20,
            )
        )
        title = reporter._render_title()
        status = reporter._render_status()

        assert len(reporter._progress.tasks) == 1
        assert reporter._progress.tasks[0].start_time == started_at
        assert title.plain.rstrip() == "[Bundles] Exporting"
        assert "1/52 groups  312/647 assets  Cafe_CH0347" in status.plain
        assert "Group 2/52" not in status.plain
        assert "elapsed 0:00:10  ETA 0:00:20" in status.plain
        assert "│" not in status.plain
        assert any(span.style == "bright_blue" for span in status.spans)


@pytest.mark.parametrize("width", [80, 120, 160, 220])
def test_rich_progress_is_responsive_without_vertical_separators(
    monkeypatch: pytest.MonkeyPatch,
    width: int,
) -> None:
    clock = FakeClock()
    state = ProgressState(
        "Assets",
        "verifying",
        overall=ProgressMeasure(4288, 26283, "files"),
        item=(
            "assets-_mx-characters-shun_original-_mxdependency-"
            "2024-11-18_005_assets_all_1372137408.bundle"
        ),
        workers=ProgressWorkers(30, 30),
        pending=137,
        failures=0,
        eta_seconds=4230,
    )
    reporter = _reporter(monkeypatch, state, width=width, clock=clock)

    with reporter:
        reporter._render_title()
        status = reporter._render_status()
        occupied = (
            8
            + reporter._title_table_column.width
            + reporter._bar_column.bar_width
            + cell_len(status.plain)
        )

        assert occupied <= width
        assert "│" not in status.plain
        assert "  " in status.plain
        assert "ETA 1:10:30" in status.plain
        if width == 80:
            assert "assets-_mx" not in status.plain


def test_timing_uses_overall_samples_and_expires_a_stalled_rate() -> None:
    clock = FakeClock()
    initial = ProgressState(
        "Assets",
        "downloading",
        overall=ProgressMeasure(0, 10, "bytes"),
    )
    estimator = ProgressTimingEstimator(clock=clock)
    estimator.start(initial)

    clock.advance(2)
    advanced = ProgressState(
        "Assets",
        "downloading",
        overall=ProgressMeasure(2, 10, "bytes"),
        current=ProgressMeasure(1, 5, "files"),
    )
    estimator.observe(advanced)
    timing = estimator.snapshot(advanced)
    assert timing.elapsed_seconds == 2
    assert timing.rate_per_second == 1
    assert timing.eta_seconds == 8

    clock.advance(31)
    stalled = estimator.snapshot(advanced)
    assert stalled.elapsed_seconds == 33
    assert stalled.rate_per_second is None
    assert stalled.eta_seconds is None


def test_timing_resets_rate_when_the_primary_measure_changes() -> None:
    clock = FakeClock()
    estimator = ProgressTimingEstimator(clock=clock)
    scanning = ProgressState(
        "Bundles",
        "scanning",
        overall=ProgressMeasure(0, 3, "archives"),
    )
    estimator.start(scanning)
    clock.advance(1)
    scanning = ProgressState(
        "Bundles",
        "scanning",
        overall=ProgressMeasure(1, 3, "archives"),
    )
    estimator.observe(scanning)
    assert estimator.snapshot(scanning).rate_per_second == 1

    exporting = ProgressState(
        "Bundles",
        "exporting",
        overall=ProgressMeasure(0, 52, "groups"),
    )
    estimator.observe(exporting)
    timing = estimator.snapshot(exporting)
    assert timing.elapsed_seconds == 1
    assert timing.rate_per_second is None
    assert timing.eta_seconds is None
