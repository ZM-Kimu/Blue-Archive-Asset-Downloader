from downloader import Downloader
from extractor import (
    BundlesExtractor,
    FlatbufferExtractor,
    MediasExtractor,
    TablesExtractor,
)
from lib.console import notice
from lib.structure import Resource
from utils.config import Config
from utils.util import ResourceUtils
from xtractor.character import CharacterNameRelation

downloader = Downloader()
fb_extractor = FlatbufferExtractor()


class Branches:
    @staticmethod
    def dump() -> None:
        fb_extractor.dump()
        fb_extractor.compile()

    @staticmethod
    def search(res: Resource, dumped: bool) -> Resource:
        keywords = []
        if Config.advance_search:
            notice("Preparing for advance srearch...")

            if not CharacterNameRelation.verify_relation_file(
                Config.version, Config.region
            ):
                if not dumped:
                    Branches.dump()
                char_extractor = CharacterNameRelation()
                excel_zip = char_extractor.get_excel_res(res)
                downloader.verify_and_download(excel_zip)
                char_extractor.main()

            keywords = CharacterNameRelation.search(
                Config.version, Config.region, Config.advance_search
            )

        if Config.search:
            keywords = Config.search

        if keywords:
            res = ResourceUtils.search_name(res, keywords)

        return res

    @staticmethod
    def extract() -> None:
        if not Config.downloading_extract:
            if "table" in Config.resource_type:
                TablesExtractor().extract_tables()
            if "bundle" in Config.resource_type:
                BundlesExtractor.extract()
            if "media" in Config.resource_type:
                MediasExtractor().extract_zips()

            notice("Extract task done.")

    @staticmethod
    def filter_and_download(res: Resource) -> None:
        resource = ResourceUtils.filter_type(res, Config.resource_type)
        downloader.verify_and_download(resource)


if __name__ == "__main__":

    res = downloader.main()

    if Config.region == "jp":

        dumped = False
        if "table" in Config.resource_type:
            Branches.dump()
            dumped = True

        if Config.search or Config.advance_search:
            res = Branches.search(res, dumped)

        Branches.filter_and_download(res)

        if not Config.downloading_extract:
            Branches.extract()

    else:
        Branches.filter_and_download(res)
