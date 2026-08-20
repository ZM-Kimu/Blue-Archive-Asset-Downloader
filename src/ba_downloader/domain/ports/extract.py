from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.extraction import ExtractionReport
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.models.schema import PreparedSchemaSnapshot, SchemaPurpose


class Il2CppDumpBackendPort(Protocol):
    def dump(
        self,
        context: ExecutionContext,
        output_dir: str,
        runtime_assets: PreparedRuntimeAssets,
    ) -> None: ...


class AssetExtractionPort(Protocol):
    def extract_bundles(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
    ) -> ExtractionReport: ...

    def extract_media(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
    ) -> ExtractionReport: ...

    def extract_tables(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
        *,
        concurrency: int,
    ) -> ExtractionReport: ...


class SchemaWorkflowPort(Protocol):
    def dump(
        self,
        context: ExecutionContext,
        runtime_assets: PreparedRuntimeAssets,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> None: ...

    def compile(
        self,
        context: ExecutionContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> PreparedSchemaSnapshot | None: ...


class SchemaPreparationPort(Protocol):
    def prepare(
        self,
        context: ExecutionContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> PreparedSchemaSnapshot | None: ...

    def compile(self, context: ExecutionContext) -> None: ...


class ExtractionPrerequisitePort(Protocol):
    def ensure(
        self,
        context: ExecutionContext,
        resources: AssetCollection | None = None,
    ) -> None: ...
