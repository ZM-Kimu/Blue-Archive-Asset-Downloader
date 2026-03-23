from __future__ import annotations

from rich.highlighter import RegexHighlighter


class LogMessageHighlighter(RegexHighlighter):
    base_style = "log."
    highlights = [
        r"(?P<url>https?://[^\s]+)",
        (
            r"(?P<path>"
            r"(?:[A-Za-z]:[\\/]|(?:\.\.?[\\/])|[/\\])"
            r"(?:[^\\/\s]+[\\/])*"
            r"[^\\/\s:]+"
            r")"
        ),
        r"(?P<exception>\b[A-Z][A-Za-z0-9_]*(?:Error|Exception)\b)",
    ]
