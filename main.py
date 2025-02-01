from downloader import Downloader
from extractor import (
    BundlesExtractor,
    FlatbufferExtractor,
    MediasExtractor,
    TablesExtractor,
)
from lib.console import notice
from utils.config import Config

if __name__ == "__main__":

    downloader = Downloader()
    downloader.main()

    if Config.region == "jp":
        fb_extractor = FlatbufferExtractor()
        fb_extractor.dump()
        fb_extractor.compile()

        TablesExtractor().extract_tables()

        BundlesExtractor.extract()

        MediasExtractor().extract_zips()

        notice("Extract task done.")
