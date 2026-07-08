from ba_downloader.application.profiles import RegionProfile
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.resource_query import ResourceQueryService


class DownloadAssetsUseCase:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        *,
        workflow_profile: RegionProfile,
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.workflow_profile = workflow_profile

    def run(self, context: RuntimeContext) -> RuntimeContext:
        catalog = self.provider.load_catalog(context)
        resources = catalog.resources
        self.workflow_profile.catalog_metadata.on_catalog_loaded(
            catalog.context,
            resources,
        )
        if catalog.context.search:
            resources = ResourceQueryService.search_name(
                resources, catalog.context.search
            )
        filtered = ResourceQueryService.filter_type(
            resources, catalog.context.resource_type
        )
        self.downloader.verify_and_download(filtered, catalog.context)
        return catalog.context
