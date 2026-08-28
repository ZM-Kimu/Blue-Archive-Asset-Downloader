from __future__ import annotations

import signal
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Timer
from time import sleep

sys.path.insert(0, str(Path(__file__).parents[1]))

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.extraction.process_table_runner import (
    ProcessTableExtractionRunner,
)
from ba_downloader.infrastructure.extraction.table.profiles import (
    TableExtractionProfile,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from support import build_execution_context


def blocking_table_profile(
    _context: ExecutionContext,
    _database_source_identity: object | None = None,
) -> TableExtractionProfile:
    while True:
        sleep(1.0)


def main() -> int:
    with TemporaryDirectory() as temporary_directory:
        runner = ProcessTableExtractionRunner(
            NullLogger(),
            poll_interval_seconds=0.02,
            interrupt_grace_seconds=0.1,
            table_profile_factory=blocking_table_profile,
        )
        interrupt = Timer(0.5, signal.raise_signal, args=(signal.SIGINT,))
        interrupt.start()
        try:
            runner.run(
                ["ExcelDB.db", "GroundStage.bytes"],
                build_execution_context(Path(temporary_directory), region="jp"),
                concurrency=2,
            )
        except OperationCancelledError:
            return 0
        finally:
            interrupt.cancel()
            interrupt.join(timeout=1.0)
    return 1


if __name__ == "__main__":
    sys.exit(main())
