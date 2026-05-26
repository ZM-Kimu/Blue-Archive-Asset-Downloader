from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ProgressCallback = Callable[[str], None]

CANCELLED_EXTRACTION_MESSAGE = "Extraction cancelled by user."


class TableProcessingError(RuntimeError):
    """Raised when a table payload cannot be processed."""


class UnsupportedSchemaError(TableProcessingError):
    """Raised when no generated FlatBufferData schema matches a payload."""


class FlatBufferExportError(TableProcessingError):
    """Raised when generated FlatBufferData schemas cannot export a payload."""


class TableDecryptError(TableProcessingError):
    """Raised when xor-protected table payloads cannot be decoded."""


class MalformedTablePayloadError(TableProcessingError):
    """Raised when bytes or JSON payload content is malformed."""


@dataclass(frozen=True, slots=True)
class ProcessedTableArtifact:
    data: bytes
    file_name: str
