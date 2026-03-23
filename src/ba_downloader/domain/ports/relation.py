from typing import Protocol

from ba_downloader.domain.models.resource import Resource
from ba_downloader.domain.models.runtime import RuntimeContext


class RelationBuilderPort(Protocol):
    def build(self, context: RuntimeContext) -> None:
        ...

    def get_excel_resources(self, resources: Resource) -> Resource:
        ...

    def search(self, context: RuntimeContext, search_terms: list[str]) -> list[str]:
        ...

    def verify_relation_file(self, context: RuntimeContext) -> bool:
        ...
