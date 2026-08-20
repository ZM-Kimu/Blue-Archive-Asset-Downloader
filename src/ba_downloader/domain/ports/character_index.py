from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.character import CharacterIndex
from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.schema import PreparedSchemaSnapshot


class CharacterIndexBuilderPort(Protocol):
    def build(
        self,
        context: ExecutionContext,
        *,
        schema_snapshot: PreparedSchemaSnapshot | None = None,
        database_source_identity: DatabaseSourceIdentity | None = None,
    ) -> None: ...

    def get_excel_resources(self, resources: AssetCollection) -> AssetCollection: ...

    def verify_index_file(self, context: ExecutionContext) -> bool: ...

    def load(self, context: ExecutionContext) -> CharacterIndex: ...
