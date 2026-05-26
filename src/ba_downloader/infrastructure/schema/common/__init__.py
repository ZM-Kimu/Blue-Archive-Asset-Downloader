"""Shared helpers for generated schema packages."""

from ba_downloader.infrastructure.schema.common.generated_registry import (
    GeneratedSchemaRegistry,
)
from ba_downloader.infrastructure.schema.common.identifiers import make_valid_identifier

__all__ = [
    "GeneratedSchemaRegistry",
    "make_valid_identifier",
]
