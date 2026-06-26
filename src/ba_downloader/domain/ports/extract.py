from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext


class Il2CppDumpBackendPort(Protocol):
    def dump(self, context: RuntimeContext, output_dir: str) -> None: ...


class AssetExtractionPort(Protocol):
    def extract_bundles(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None: ...

    def extract_media(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None: ...

    def extract_tables(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None: ...


class SchemaWorkflowPort(Protocol):
    def dump(self, context: RuntimeContext) -> None: ...

    def compile(self, context: RuntimeContext) -> None: ...


class ExtractionPrerequisitePort(Protocol):
    def ensure(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None: ...
