import logging

from rich.style import Style
from rich.text import Text

from ba_downloader.infrastructure.logging import runtime
from ba_downloader.infrastructure.logging.highlighter import LogMessageHighlighter


def test_configure_logging_uses_shared_console_and_custom_highlighter() -> None:
    logger = logging.getLogger(runtime.LOGGER_NAME)
    logger.handlers.clear()
    runtime._configured = False
    runtime._console = None

    runtime.configure_logging()

    handler = logger.handlers[0]
    assert handler.console is runtime.get_console()
    assert isinstance(handler.highlighter, LogMessageHighlighter)
    assert runtime.get_console().get_style("log.url") == Style.parse("underline cyan")
    assert runtime.get_console().get_style("log.path") == Style.parse("cyan")
    assert runtime.get_console().get_style("log.exception") == Style.parse("bold red")


def test_log_highlighter_avoids_version_number_highlighting() -> None:
    message = Text("Downloading package ブルーアーカイブ_v1.67.412528_apkpure.com.xapk...")

    LogMessageHighlighter().highlight(message)

    assert not message.spans


def test_log_highlighter_marks_urls_paths_and_exception_names() -> None:
    message = Text(
        "Failed to download Bundle/FullPatch_044.zip from "
        "https://example.com/archive.zip with NetworkError"
    )

    LogMessageHighlighter().highlight(message)

    styles = {span.style for span in message.spans}
    assert "log.url" in styles
    assert "log.path" in styles
    assert "log.exception" in styles


def test_log_highlighter_does_not_mark_url_as_path() -> None:
    message = Text(
        "Resolved server URL: "
        "https://yostar-serverinfo.bluearchiveyostar.com/r90_67_0hkp7rg02pe8a888qd2y.json"
    )

    LogMessageHighlighter().highlight(message)

    styles = {span.style for span in message.spans}
    assert "log.url" in styles
    assert "log.path" not in styles
