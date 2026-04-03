import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from ba_downloader.infrastructure.logging.highlighter import LogMessageHighlighter


LOGGER_NAME = "ba_downloader"
LOG_THEME = Theme(
    {
        "log.url": "underline cyan",
        "log.path": "cyan",
        "log.exception": "bold red",
    }
)
_configured = False
_console: Console | None = None


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(stderr=True, theme=LOG_THEME)
    return _console


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    logger.addHandler(
        RichHandler(
            console=get_console(),
            rich_tracebacks=True,
            show_path=False,
            highlighter=LogMessageHighlighter(),
            markup=False,
            keywords=[],
        )
    )
    _configured = True


def get_stdlib_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger
