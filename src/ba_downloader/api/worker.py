from __future__ import annotations

import logging
import traceback
from typing import Any

from ba_downloader.api.events import (
    QueueLogger,
    QueueProgressReporterFactory,
    build_secret_redactions,
    redact_text,
    utc_now,
)
from ba_downloader.application.contracts import ApplicationCommand
from ba_downloader.bootstrap.container import ExecutionScope
from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import ArtifactCollector, EventCancellation

LOGGER = logging.getLogger(__name__)


def run_application_job(
    command: ApplicationCommand,
    context: ExecutionContext,
    event_queue: Any,
    terminal_sender: Any,
    cancel_event: Any,
) -> None:
    redactions = build_secret_redactions(
        sqlcipher_key_hex=context.sqlcipher_key,
        proxy_url=context.proxy_url,
    )
    logger = QueueLogger(event_queue, redactions=redactions)
    cancellation = EventCancellation(cancel_event)
    artifacts = ArtifactCollector()
    try:
        with ExecutionScope(
            context,
            logger=logger,
            progress_factory=QueueProgressReporterFactory(event_queue),
            cancellation=cancellation,
            artifacts=artifacts,
        ) as executor:
            result = executor.execute(command)
        result_payload = {
            "context": result.context,
            "artifacts": result.artifacts,
            "catalog": result.catalog,
            "statistics": result.statistics,
            "warnings": tuple(
                redact_text(warning, redactions) for warning in result.warnings
            ),
        }
        terminal_sender.send(
            {"type": "result", "timestamp": utc_now(), "payload": result_payload}
        )
    except OperationCancelledError:
        terminal_sender.send(
            {"type": "cancelled", "timestamp": utc_now(), "payload": {}}
        )
    except BaseException as exc:  # pylint: disable=broad-exception-caught
        LOGGER.error(
            "Application worker failed:\n%s",
            redact_text(traceback.format_exc(), redactions),
        )
        terminal_sender.send(
            {
                "type": "error",
                "timestamp": utc_now(),
                "payload": {
                    "code": "OPERATION_FAILED",
                    "message": redact_text(
                        str(exc) or exc.__class__.__name__, redactions
                    ),
                    "exception_type": exc.__class__.__name__,
                },
            }
        )
    finally:
        terminal_sender.close()
