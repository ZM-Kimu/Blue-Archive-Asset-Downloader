from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import AssetExtractionPort


class ExtractService:
    def __init__(self, extraction_workflow: AssetExtractionPort) -> None:
        self.extraction_workflow = extraction_workflow

    def run(self, context: RuntimeContext) -> None:
        if context.region == "cn":
            self.extraction_workflow.extract_bundles(context)
            return

        if "table" in context.resource_type:
            self.extraction_workflow.extract_tables(context)
        if "bundle" in context.resource_type:
            self.extraction_workflow.extract_bundles(context)
        if "media" in context.resource_type:
            self.extraction_workflow.extract_media(context)

    def run_post_download(self, context: RuntimeContext) -> None:
        if context.extract_while_download:
            return
        self.run(context)
