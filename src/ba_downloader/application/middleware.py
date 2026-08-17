from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort

MessageHandler: TypeAlias = Callable[[ExecutionContext, object], object]


class MessageMiddlewarePort(Protocol):
    def __call__(
        self,
        context: ExecutionContext,
        message: object,
        call_next: MessageHandler,
    ) -> object: ...


class CancellationMiddleware:
    def __init__(self, cancellation: CancellationPort) -> None:
        self._cancellation = cancellation

    def __call__(
        self,
        context: ExecutionContext,
        message: object,
        call_next: MessageHandler,
    ) -> object:
        self._cancellation.raise_if_cancelled()
        result = call_next(context, message)
        self._cancellation.raise_if_cancelled()
        return result
