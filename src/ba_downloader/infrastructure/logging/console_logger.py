from typing import Literal

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.lib.console import notice, print


class ConsoleLogger(LoggerPort):
    def info(self, message: str) -> None:
        print(message)

    def warn(self, message: str) -> None:
        notice(message, "warn")

    def error(self, message: str) -> None:
        notice(message, "error")


class NullLogger(LoggerPort):
    def info(self, message: str) -> None:
        _ = message

    def warn(self, message: str) -> None:
        _ = message

    def error(self, message: str) -> None:
        _ = message
