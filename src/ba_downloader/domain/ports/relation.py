from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext


class RelationBuilderPort(Protocol):
    def build(self, context: RuntimeContext) -> None: ...

    def get_excel_resources(self, resources: AssetCollection) -> AssetCollection: ...

    def search(self, context: RuntimeContext, search_terms: list[str]) -> list[str]: ...

    def verify_relation_file(self, context: RuntimeContext) -> bool: ...
