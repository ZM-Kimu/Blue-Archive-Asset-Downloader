from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.extraction import ExtractionReport
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.models.schema import PreparedSchemaSnapshot, SchemaPurpose


class Il2CppDumpBackendPort(Protocol):
    def dump(
        self,
        context: RuntimeContext,
        output_dir: str,
        runtime_assets: PreparedRuntimeAssets,
    ) -> None: ...


class AssetExtractionPort(Protocol):
    def extract_bundles(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> ExtractionReport: ...

    def extract_media(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> ExtractionReport: ...

    def extract_tables(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> ExtractionReport: ...


class SchemaWorkflowPort(Protocol):
    def dump(
        self,
        context: RuntimeContext,
        runtime_assets: PreparedRuntimeAssets,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> None: ...

    def compile(
        self,
        context: RuntimeContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> PreparedSchemaSnapshot | None: ...


class SchemaPreparationPort(Protocol):
    def prepare(
        self,
        context: RuntimeContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> PreparedSchemaSnapshot | None: ...

    def compile(self, context: RuntimeContext) -> None: ...


class ExtractionPrerequisitePort(Protocol):
    def ensure(
        self,
        context: RuntimeContext,
        resources: AssetCollection | None = None,
    ) -> None: ...
