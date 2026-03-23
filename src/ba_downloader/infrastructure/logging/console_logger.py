from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.logging.runtime import get_stdlib_logger


class ConsoleLogger(LoggerPort):
    def __init__(self) -> None:
        self._logger = get_stdlib_logger()

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warn(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)


class NullLogger(LoggerPort):
    def info(self, message: str) -> None:
        _ = message

    def warn(self, message: str) -> None:
        _ = message

    def error(self, message: str) -> None:
        _ = message
