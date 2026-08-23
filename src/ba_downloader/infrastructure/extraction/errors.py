from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ba_downloader.domain.exceptions import ExtractError


@dataclass(frozen=True, slots=True)
class ExtractionFailure:
    file_path: str
    error: Exception


class ExtractionFailureError(ExtractError):
    def __init__(self, operation_name: str, failures: list[ExtractionFailure]) -> None:
        self.operation_name = operation_name
        self.failures = failures
        file_word = "file" if len(failures) == 1 else "files"
        examples = ", ".join(Path(failure.file_path).name for failure in failures[:5])
        suffix = f": {examples}" if examples else ""
        first_error = next(
            (failure.error for failure in failures if str(failure.error)),
            None,
        )
        detail = (
            f"; first error: {first_error.__class__.__name__}: {first_error}"
            if first_error is not None
            else ""
        )
        super().__init__(
            f"{operation_name} failed for {len(failures)} {file_word}{suffix}{detail}"
        )


class BundleExtractionError(ExtractError):
    """Expected bundle extraction failure safe to expose to CLI and API clients."""
