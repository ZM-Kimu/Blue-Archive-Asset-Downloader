from downloader import Downloader
from extractor import (
    BundlesExtractor,
    FlatbufferExtractor,
    MediasExtractor,
    TablesExtractor,
)
from lib.console import notice
from lib.structure import Resource, ResourceItem
from utils.config import Config
from xtractor.character import CharacterNameRelation


def filter_resource_type(resource: Resource) -> Resource:
    """Filter the necessary item from the resource_type specified in the Config"""
    if len(Config.resource_type) == 3:
        return resource

    filtered_res = Resource()
    for res in resource:
        if res.resource_type.name in Config.resource_type:
            filtered_res.add_item(res)

    return filtered_res


def process_search(resource: Resource, keywords: list[str]) -> Resource:
    results = Resource()

    searched_list: list[ResourceItem] = []
    for keyword in keywords:
        searched_list += resource.search_resource("path", keyword)

    for searched in searched_list:
        results.add_item(searched)

    return results


if __name__ == "__main__":

    downloader = Downloader()
    res = downloader.main()

    if Config.region == "jp":
        fb_extractor = FlatbufferExtractor()
        if "table" in Config.resource_type or Config.advance_search:
            fb_extractor.dump()
            fb_extractor.compile()

        if Config.advance_search:
            notice("Preparing for advance srearch...")
            char_extractor = CharacterNameRelation()
            if not char_extractor.verify_relation_file(Config.version, Config.region):
                excel_zip = char_extractor.get_excel_res(res)
                downloader.verify_and_download(excel_zip)
                char_extractor.main()

            keywords = char_extractor.search(
                Config.version, Config.region, Config.advance_search
            )

            res = process_search(res, keywords)

        if Config.search:
            res = process_search(res, Config.search)

    resource = filter_resource_type(res)
    downloader.verify_and_download(resource)

    if Config.region == "jp":
        if "table" in Config.resource_type:
            TablesExtractor().extract_tables()
        if "bundle" in Config.resource_type:
            BundlesExtractor.extract()
        if "media" in Config.resource_type:
            MediasExtractor().extract_zips()

        notice("Extract task done.")
