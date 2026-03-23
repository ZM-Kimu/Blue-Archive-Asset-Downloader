from ba_downloader.infrastructure.services.downloader_engine import DownloaderEngine
from ba_downloader.shared.resources.resource_filters import ResourceUtils
from ba_downloader.utils.config import Config


class DownloadService:
    def __init__(self) -> None:
        self.downloader = DownloaderEngine()

    def run(self) -> None:
        resources = self.downloader.main()
        filtered = ResourceUtils.filter_type(resources, Config.resource_type)
        self.downloader.verify_and_download(filtered)
