from __future__ import annotations

from typing import Optional

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from ba_downloader.domain.ports.progress import ProgressReporterPort


class RichProgressReporter(ProgressReporterPort):
    def __init__(
        self,
        total: int,
        description: str,
        *,
        download_mode: bool = False,
    ) -> None:
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ]
        if download_mode:
            columns.extend(
                [
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                ]
            )
        else:
            columns.extend([TimeElapsedColumn(), TimeRemainingColumn()])

        self._progress = Progress(*columns, transient=False)
        self._task_id: Optional[int] = None
        self._total = total
        self._description = description

    def __enter__(self) -> "RichProgressReporter":
        self._progress.start()
        self._task_id = self._progress.add_task(self._description, total=self._total)
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

    def set_completed(self, completed: int) -> None:
        if self._task_id is not None:
            self._progress.update(self._task_id, completed=completed)

    def stop(self) -> None:
        self._progress.stop()


class NullProgressReporter(ProgressReporterPort):
    def __enter__(self) -> "NullProgressReporter":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def advance(self, amount: int = 1) -> None:
        _ = amount

    def set_total(self, total: int) -> None:
        _ = total

    def set_description(self, description: str) -> None:
        _ = description

    def set_completed(self, completed: int) -> None:
        _ = completed

    def stop(self) -> None:
        return None
