from __future__ import annotations

from typing import ClassVar

from rich.highlighter import RegexHighlighter


class LogMessageHighlighter(RegexHighlighter):
    base_style = "log."
    highlights: ClassVar[list[str]] = [
        r"(?P<url>https?://[^\s]+)",
        (
            r"(?:(?<=\s)|^)(?P<path>"
            r"(?!https?://)"
            r"(?:[A-Za-z]:[\\/]|(?:\.\.?[\\/])|[/\\]|[^\\/\s:]+[\\/])"
            r"(?:[^\\/\s]+[\\/])*"
            r"[^\\/\s:]+"
            r")"
        ),
        r"(?P<exception>\b[A-Z][A-Za-z0-9_]*(?:Error|Exception)\b)",
    ]
