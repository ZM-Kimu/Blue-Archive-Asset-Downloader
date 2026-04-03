from __future__ import annotations


from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Column

from ba_downloader.domain.ports.progress import ProgressReporterPort
from ba_downloader.infrastructure.logging.runtime import get_console


class RichProgressReporter(ProgressReporterPort):
    DESCRIPTION_COLUMN_WIDTH = 48
    DOWNLOAD_DESCRIPTION_COLUMN_WIDTH = 18
    DOWNLOAD_BAR_WIDTH = 24
    FILE_STATUS_COLUMN_WIDTH = 14
    CONCURRENCY_STATUS_COLUMN_WIDTH = 11
    FAILURE_STATUS_COLUMN_WIDTH = 10

    def __init__(
        self,
        total: int,
        description: str,
        *,
        download_mode: bool = False,
    ) -> None:
        description_width = (
            self.DOWNLOAD_DESCRIPTION_COLUMN_WIDTH
            if download_mode
            else self.DESCRIPTION_COLUMN_WIDTH
        )
        columns = [
            SpinnerColumn(),
            TextColumn(
                "[progress.description]{task.description}",
                table_column=Column(
                    width=description_width,
                    min_width=description_width,
                    max_width=description_width,
                    no_wrap=True,
                    overflow="ellipsis",
                ),
            ),
        ]
        if download_mode:
            columns.extend(
                [
                    BarColumn(bar_width=self.DOWNLOAD_BAR_WIDTH),
                    TaskProgressColumn(),
                    TextColumn(
                        "{task.fields[status]}",
                        table_column=Column(
                            width=self.FILE_STATUS_COLUMN_WIDTH,
                            min_width=self.FILE_STATUS_COLUMN_WIDTH,
                            max_width=self.FILE_STATUS_COLUMN_WIDTH,
                            justify="right",
                            no_wrap=True,
                            overflow="ellipsis",
                        ),
                    ),
                    TextColumn(
                        "{task.fields[secondary_status]}",
                        table_column=Column(
                            width=self.CONCURRENCY_STATUS_COLUMN_WIDTH,
                            min_width=self.CONCURRENCY_STATUS_COLUMN_WIDTH,
                            max_width=self.CONCURRENCY_STATUS_COLUMN_WIDTH,
                            justify="right",
                            no_wrap=True,
                            overflow="ellipsis",
                        ),
                    ),
                    TextColumn(
                        "{task.fields[failed_status]}",
                        table_column=Column(
                            width=self.FAILURE_STATUS_COLUMN_WIDTH,
                            min_width=self.FAILURE_STATUS_COLUMN_WIDTH,
                            max_width=self.FAILURE_STATUS_COLUMN_WIDTH,
                            justify="right",
                            no_wrap=True,
                            overflow="ellipsis",
                        ),
                    ),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                ]
            )
        else:
            columns.extend(
                [BarColumn(), TaskProgressColumn(), TimeElapsedColumn(), TimeRemainingColumn()]
            )

        self._progress = Progress(*columns, console=get_console(), transient=False)
        self._task_id: TaskID | None = None
        self._total = total
        self._description = description
        self._status = ""
        self._secondary_status = ""
        self._failed_status = ""

    def __enter__(self) -> RichProgressReporter:
        self._progress.start()
        self._task_id = self._progress.add_task(
            self._description,
            total=self._total,
            status=self._status,
            secondary_status=self._secondary_status,
            failed_status=self._failed_status,
        )
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def advance(self, amount: int = 1) -> None:
        if self._task_id is not None:
            self._progress.update(self._task_id, advance=amount)

    def set_total(self, total: int) -> None:
        self._total = total
        if self._task_id is not None:
            self._progress.update(self._task_id, total=total)

    def set_description(self, description: str) -> None:
        self._description = description
        if self._task_id is not None:
            self._progress.update(self._task_id, description=description)

    def set_status(self, status: str) -> None:
        self._status = status
        if self._task_id is not None:
            self._progress.update(self._task_id, status=status)

    def set_secondary_status(self, status: str) -> None:
        self._secondary_status = status
        if self._task_id is not None:
            self._progress.update(self._task_id, secondary_status=status)

    def set_failed_status(self, status: str) -> None:
        self._failed_status = status
        if self._task_id is not None:
            self._progress.update(self._task_id, failed_status=status)

    def set_completed(self, completed: int) -> None:
        if self._task_id is not None:
            self._progress.update(self._task_id, completed=completed)

    def stop(self) -> None:
        self._progress.stop()


class NullProgressReporter(ProgressReporterPort):
    def __enter__(self) -> NullProgressReporter:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def advance(self, amount: int = 1) -> None:
        _ = amount

    def set_total(self, total: int) -> None:
        _ = total

    def set_description(self, description: str) -> None:
        _ = description

    def set_status(self, status: str) -> None:
        _ = status

    def set_secondary_status(self, status: str) -> None:
        _ = status

    def set_failed_status(self, status: str) -> None:
        _ = status

    def set_completed(self, completed: int) -> None:
        _ = completed

    def stop(self) -> None:
        return None
