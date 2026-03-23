from ba_downloader.infrastructure.services.extractor_engine import BundlesExtractor, MediasExtractor, TablesExtractor
from ba_downloader.utils.config import Config


class ExtractService:
    def run(self) -> None:
        if Config.region == "cn":
            BundlesExtractor().extract()
            return

        if "table" in Config.resource_type:
            TablesExtractor().extract_tables()
        if "bundle" in Config.resource_type:
            BundlesExtractor.extract()
        if "media" in Config.resource_type:
            MediasExtractor().extract_zips()

    def run_post_download(self) -> None:
        if Config.downloading_extract:
            return
        self.run()
