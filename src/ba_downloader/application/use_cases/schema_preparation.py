from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.schema import PreparedSchemaSnapshot, SchemaPurpose
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.extract import SchemaWorkflowPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort


class SchemaPreparationService:
    def __init__(
        self,
        schema_workflow: SchemaWorkflowPort,
        runtime_asset_preparer: RuntimeAssetPreparerPort,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.schema_workflow = schema_workflow
        self.runtime_asset_preparer = runtime_asset_preparer
        self.cancellation = cancellation or NeverCancelled()

    def prepare(
        self,
        context: ExecutionContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> PreparedSchemaSnapshot | None:
        self.cancellation.raise_if_cancelled()
        runtime_assets = self.runtime_asset_preparer.prepare(context)
        self.cancellation.raise_if_cancelled()
        if purpose is SchemaPurpose.FULL:
            self.schema_workflow.dump(context, runtime_assets)
        else:
            self.schema_workflow.dump(context, runtime_assets, purpose)
        self.cancellation.raise_if_cancelled()
        snapshot = (
            self.schema_workflow.compile(context)
            if purpose is SchemaPurpose.FULL
            else self.schema_workflow.compile(context, purpose)
        )
        self.cancellation.raise_if_cancelled()
        return snapshot

    def compile(self, context: ExecutionContext) -> None:
        self.cancellation.raise_if_cancelled()
        self.schema_workflow.compile(context)
        self.cancellation.raise_if_cancelled()
