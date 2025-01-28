from os import path

from downloader import Downloader
from extractor import FlatbufferExtractor
from lib.console import notice
from utils.config import Config
from xtractor.table import TableExtractor

downloader = Downloader()
downloader.main()

if Config.region == "jp":
    fb_extractor = FlatbufferExtractor()
    fb_extractor.dump()
    fb_extractor.compile()

    table_extractor = TableExtractor(
        path.join(Config.raw_dir, "Table"),
        path.join(Config.extract_dir, "Table"),
        f"{Config.extract_dir}.FlatData",
    )
    table_extractor.extract_tables()
    notice("Extract completed.")
