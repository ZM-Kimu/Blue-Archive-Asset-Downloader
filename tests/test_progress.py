from rich.progress import BarColumn, TextColumn

from ba_downloader.infrastructure.progress.rich_progress import (
    NullProgressReporter,
    RichProgressReporter,
)


def test_null_progress_reporter_is_noop() -> None:
    reporter = NullProgressReporter()

    with reporter:
        reporter.set_description("Testing")
        reporter.set_status("1/2 files")
        reporter.set_secondary_status("conc. 2/4")
        reporter.set_failed_status("failed 0")
        reporter.set_total(10)
        reporter.set_completed(3)
        reporter.advance(2)

    reporter.stop()


def test_rich_progress_reporter_uses_fixed_width_description_column() -> None:
    reporter = RichProgressReporter(10, "Verifying Main_11005_005.ogg")

    description_column = next(
        column
        for column in reporter._progress.columns
        if isinstance(column, TextColumn)
    )
    table_column = description_column.get_table_column()

    assert table_column.width == RichProgressReporter.DESCRIPTION_COLUMN_WIDTH
    assert table_column.min_width == RichProgressReporter.DESCRIPTION_COLUMN_WIDTH
    assert table_column.max_width == RichProgressReporter.DESCRIPTION_COLUMN_WIDTH
    assert table_column.overflow == "ellipsis"
    assert table_column.no_wrap is True


def test_rich_progress_reporter_uses_compact_description_column_in_download_mode() -> (
    None
):
    reporter = RichProgressReporter(10, "FullPatch_089.zip", download_mode=True)

    description_column = next(
        column
        for column in reporter._progress.columns
        if isinstance(column, TextColumn)
        and column.text_format == "[progress.description]{task.description}"
    )
    table_column = description_column.get_table_column()

    assert table_column.width == RichProgressReporter.DOWNLOAD_DESCRIPTION_COLUMN_WIDTH
    assert (
        table_column.min_width == RichProgressReporter.DOWNLOAD_DESCRIPTION_COLUMN_WIDTH
    )
    assert (
        table_column.max_width == RichProgressReporter.DOWNLOAD_DESCRIPTION_COLUMN_WIDTH
    )
    assert table_column.overflow == "ellipsis"
    assert table_column.no_wrap is True

    bar_column = next(
        column for column in reporter._progress.columns if isinstance(column, BarColumn)
    )
    assert bar_column.bar_width == RichProgressReporter.DOWNLOAD_BAR_WIDTH


def test_rich_progress_reporter_uses_fixed_width_status_column_in_download_mode() -> (
    None
):
    reporter = RichProgressReporter(10, "FullPatch_043.zip", download_mode=True)

    file_status_column = next(
        column
        for column in reporter._progress.columns
        if isinstance(column, TextColumn)
        and column.text_format == "{task.fields[status]}"
    )
    table_column = file_status_column.get_table_column()

    assert table_column.width == RichProgressReporter.FILE_STATUS_COLUMN_WIDTH
    assert table_column.min_width == RichProgressReporter.FILE_STATUS_COLUMN_WIDTH
    assert table_column.max_width == RichProgressReporter.FILE_STATUS_COLUMN_WIDTH
    assert table_column.overflow == "ellipsis"
    assert table_column.no_wrap is True

    concurrency_column = next(
        column
        for column in reporter._progress.columns
        if isinstance(column, TextColumn)
        and column.text_format == "{task.fields[secondary_status]}"
    )
    concurrency_table_column = concurrency_column.get_table_column()

    assert (
        concurrency_table_column.width
        == RichProgressReporter.CONCURRENCY_STATUS_COLUMN_WIDTH
    )
    assert (
        concurrency_table_column.min_width
        == RichProgressReporter.CONCURRENCY_STATUS_COLUMN_WIDTH
    )
    assert (
        concurrency_table_column.max_width
        == RichProgressReporter.CONCURRENCY_STATUS_COLUMN_WIDTH
    )
    assert concurrency_table_column.overflow == "ellipsis"
    assert concurrency_table_column.no_wrap is True

    failed_column = next(
        column
        for column in reporter._progress.columns
        if isinstance(column, TextColumn)
        and column.text_format == "{task.fields[failed_status]}"
    )
    failed_table_column = failed_column.get_table_column()

    assert failed_table_column.width == RichProgressReporter.FAILURE_STATUS_COLUMN_WIDTH
    assert (
        failed_table_column.min_width
        == RichProgressReporter.FAILURE_STATUS_COLUMN_WIDTH
    )
    assert (
        failed_table_column.max_width
        == RichProgressReporter.FAILURE_STATUS_COLUMN_WIDTH
    )
    assert failed_table_column.overflow == "ellipsis"
    assert failed_table_column.no_wrap is True
