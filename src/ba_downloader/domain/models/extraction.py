from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractionReport:
    warnings: tuple[str, ...] = ()

    @classmethod
    def combine(cls, *reports: ExtractionReport) -> ExtractionReport:
        return cls(tuple(warning for report in reports for warning in report.warnings))
