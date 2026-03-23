from typing import Protocol

from ba_downloader.domain.models.runtime import RuntimeContext


class AssetExtractionPort(Protocol):
    def extract_bundles(self, context: RuntimeContext) -> None:
        ...

    def extract_media(self, context: RuntimeContext) -> None:
        ...

    def extract_tables(self, context: RuntimeContext) -> None:
        ...


class FlatbufferWorkflowPort(Protocol):
    def dump(self, context: RuntimeContext) -> None:
        ...

    def compile(self, context: RuntimeContext) -> None:
        ...
