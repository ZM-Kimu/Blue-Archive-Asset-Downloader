from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.region import RegionProvider
from ba_downloader.domain.services.resource_query import ResourceQueryService


class DownloadService:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
    ) -> None:
        self.provider = provider
        self.downloader = downloader

    def run(self, context: RuntimeContext) -> RuntimeContext:
        catalog = self.provider.load_catalog(context)
        resources = catalog.resources
        if catalog.context.search:
            resources = ResourceQueryService.search_name(resources, catalog.context.search)
        filtered = ResourceQueryService.filter_type(resources, catalog.context.resource_type)
        self.downloader.verify_and_download(filtered, catalog.context)
        return catalog.context
