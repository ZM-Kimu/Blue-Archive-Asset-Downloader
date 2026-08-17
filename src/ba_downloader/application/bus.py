from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

from ba_downloader.application.middleware import (
    MessageHandler,
    MessageMiddlewarePort,
)
from ba_downloader.domain.exceptions import (
    DuplicateMessageRegistrationError,
    UnhandledMessageError,
)
from ba_downloader.domain.models.execution import ExecutionContext

MessageT = TypeVar("MessageT")
ResultT = TypeVar("ResultT")


@dataclass(frozen=True, slots=True)
class MessageRegistration(Generic[MessageT, ResultT]):
    message_type: type[MessageT]
    handler: Callable[[ExecutionContext, MessageT], ResultT]


class _MessageBus:
    def __init__(
        self,
        registrations: Iterable[MessageRegistration[Any, Any]] = (),
        *,
        middleware: Iterable[MessageMiddlewarePort] = (),
    ) -> None:
        self._handlers: dict[type[object], MessageHandler] = {}
        self._middleware = tuple(middleware)
        for registration in registrations:
            self.register(registration)

    def register(self, registration: MessageRegistration[Any, Any]) -> None:
        message_type = cast(type[object], registration.message_type)
        if message_type in self._handlers:
            raise DuplicateMessageRegistrationError(
                f"Handler for '{message_type.__name__}' is already registered."
            )
        self._handlers[message_type] = cast(MessageHandler, registration.handler)

    def dispatch(self, context: ExecutionContext, message: object) -> Any:
        try:
            handler = self._handlers[type(message)]
        except KeyError as exc:
            raise UnhandledMessageError(
                f"No handler is registered for '{type(message).__name__}'."
            ) from exc

        call_next = handler
        for middleware in reversed(self._middleware):
            call_next = _wrap_middleware(middleware, call_next)
        return call_next(context, message)


class CommandBus(_MessageBus):
    pass


class QueryBus(_MessageBus):
    pass


def _wrap_middleware(
    middleware: MessageMiddlewarePort,
    call_next: MessageHandler,
) -> MessageHandler:
    def wrapped(context: ExecutionContext, message: object) -> object:
        return middleware(context, message, call_next)

    return wrapped
