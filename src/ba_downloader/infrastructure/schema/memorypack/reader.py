from __future__ import annotations

from typing import Any

from ba_downloader.infrastructure.schema.memorypack.cn_partial import (
    CnPartialDaoFallbackReader,
)
from ba_downloader.infrastructure.schema.memorypack.cursor import (
    NULL_COLLECTION_HEADER,
    NULL_OBJECT_HEADER,
    MemoryPackCursor,
)
from ba_downloader.infrastructure.schema.memorypack.formatter_reader import (
    FormatterDrivenReader,
)
from ba_downloader.infrastructure.schema.memorypack.formatters import (
    MemoryPackFormatterRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.registry import (
    MemoryPackSchemaRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.schema_reader import (
    SchemaObjectReader,
    memorypack_schema,
)


class MemoryPackReader(MemoryPackCursor):
    schema = staticmethod(memorypack_schema)

    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self._schema_reader = SchemaObjectReader(self)
        self._formatter_reader = FormatterDrivenReader(self, self._schema_reader)
        self._cn_partial_reader = CnPartialDaoFallbackReader(self)

    def read_object(self, schema_type: type[Any]) -> Any | None:
        return self._schema_reader.read_object(schema_type)

    def read_formatter_object(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry,
        formatter_registry: MemoryPackFormatterRegistry,
        *,
        ensure_consumed: bool = True,
    ) -> dict[str, Any]:
        return self._formatter_reader.read_object(
            root_type,
            schema_registry,
            formatter_registry,
            ensure_consumed=ensure_consumed,
        )

    def read_cn_table_dao_partial(
        self,
        root_type: str,
        schema_registry: MemoryPackSchemaRegistry | None = None,
    ) -> dict[str, Any]:
        return self._cn_partial_reader.read_partial(root_type, schema_registry)


__all__ = [
    "NULL_COLLECTION_HEADER",
    "NULL_OBJECT_HEADER",
    "MemoryPackReader",
    "MemoryPackSchemaRegistry",
]
