from __future__ import annotations

import signal
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, wait
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Event, current_thread, main_thread
from time import monotonic
from typing import Any

from ba_downloader.domain.ports.logging import LoggerPort


@dataclass(slots=True)
class CancellationFeedbackState:
    cancellation_logged: bool = False
    force_hint_logged: bool = False
    grace_deadline: float | None = None


@dataclass(frozen=True, slots=True)
class FutureWaitPolicy:
    logger: LoggerPort
    poll_interval: float
    grace_seconds: float
    subject_label: str


def build_future_wait_policy(
    logger: LoggerPort,
    poll_interval: float,
    grace_seconds: float,
    subject_label: str,
) -> FutureWaitPolicy:
    return FutureWaitPolicy(
        logger=logger,
        poll_interval=poll_interval,
        grace_seconds=grace_seconds,
        subject_label=subject_label,
    )


@contextmanager
def install_interrupt_handler(
    stop_event: Event,
    logger: LoggerPort,
    *,
    force_exit: Callable[[int], None],
    on_interrupt: Callable[[], None] | None = None,
) -> Iterator[None]:
    if current_thread() is not main_thread():
        yield
        return

    previous_handler = signal.getsignal(signal.SIGINT)
    interrupt_count = 0

    def handle_interrupt(signum: int, frame: Any | None) -> None:
        nonlocal interrupt_count
        _ = (signum, frame)
        interrupt_count += 1
        stop_event.set()
        if on_interrupt is not None:
            on_interrupt()
        if interrupt_count >= 2:
            logger.error("Force exiting immediately.")
            force_exit(130)

    try:
        signal.signal(signal.SIGINT, handle_interrupt)
        yield
    finally:
        signal.signal(signal.SIGINT, previous_handler)


def emit_cancellation_feedback(
    logger: LoggerPort,
    state: CancellationFeedbackState,
    *,
    grace_seconds: float,
    cancellation_message: str,
    still_stopping_message: str,
    has_pending_work: bool,
) -> None:
    if not state.cancellation_logged:
        logger.warn(cancellation_message)
        state.cancellation_logged = True
        state.grace_deadline = monotonic() + grace_seconds
        return

    if (
        has_pending_work
        and state.grace_deadline is not None
        and monotonic() >= state.grace_deadline
        and not state.force_hint_logged
    ):
        logger.warn(still_stopping_message)
        state.force_hint_logged = True


def cancel_pending_futures(pending_futures: Iterable[Future[Any]]) -> None:
    for pending_future in pending_futures:
        pending_future.cancel()


def wait_for_futures_with_cancellation(
    pending_futures: set[Future[Any]],
    *,
    stop_event: Event,
    logger: LoggerPort,
    cancellation_state: CancellationFeedbackState,
    poll_interval: float,
    grace_seconds: float,
    cancellation_message: str,
    still_stopping_message: str,
) -> tuple[set[Future[Any]], set[Future[Any]]]:
    done_futures, remaining_futures = wait(
        pending_futures,
        timeout=poll_interval,
        return_when=FIRST_COMPLETED,
    )

    if stop_event.is_set():
        cancel_pending_futures(remaining_futures)
        emit_cancellation_feedback(
            logger,
            cancellation_state,
            grace_seconds=grace_seconds,
            cancellation_message=cancellation_message,
            still_stopping_message=still_stopping_message,
            has_pending_work=bool(remaining_futures),
        )

    return done_futures, remaining_futures


def wait_for_operation_futures(
    pending_futures: set[Future[Any]],
    stop_event: Event,
    policy: FutureWaitPolicy,
    cancellation_state: CancellationFeedbackState,
    operation_name: str,
) -> tuple[set[Future[Any]], set[Future[Any]]]:
    return wait_for_futures_with_cancellation(
        pending_futures,
        stop_event=stop_event,
        logger=policy.logger,
        cancellation_state=cancellation_state,
        poll_interval=policy.poll_interval,
        grace_seconds=policy.grace_seconds,
        cancellation_message=f"Cancelling {operation_name}...",
        still_stopping_message=(
            f"{policy.subject_label} are still stopping. Press Ctrl+C again to force exit."
        ),
    )
