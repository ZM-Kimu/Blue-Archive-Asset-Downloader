from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import SchemaWorkflowPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort


class SchemaPreparationService:
    def __init__(
        self,
        schema_workflow: SchemaWorkflowPort,
        runtime_asset_preparer: RuntimeAssetPreparerPort,
    ) -> None:
        self.schema_workflow = schema_workflow
        self.runtime_asset_preparer = runtime_asset_preparer

    def prepare(self, context: RuntimeContext) -> None:
        runtime_assets = self.runtime_asset_preparer.prepare(context)
        self.schema_workflow.dump(context, runtime_assets)
        self.schema_workflow.compile(context)

    def compile(self, context: RuntimeContext) -> None:
        self.schema_workflow.compile(context)
