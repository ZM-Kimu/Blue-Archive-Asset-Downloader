from ba_downloader.application.services.extract import ExtractService
from ba_downloader.extractors.character import CharacterNameRelation
from ba_downloader.infrastructure.services.downloader_engine import DownloaderEngine
from ba_downloader.infrastructure.services.extractor_engine import FlatbufferExtractor
from ba_downloader.lib.console import notice
from ba_downloader.shared.resources.resource_filters import ResourceUtils
from ba_downloader.utils.config import Config


class SyncService:
    def __init__(self) -> None:
        self.downloader = DownloaderEngine()
        self.flatbuffer = FlatbufferExtractor()
        self.extract_service = ExtractService()

    def _dump_and_compile(self) -> None:
        self.flatbuffer.dump()
        self.flatbuffer.compile()

    def _search_resource(self, resources, dumped: bool):
        keywords: list[str] = []
        if Config.advance_search:
            notice("Preparing for advanced search...")
            if not CharacterNameRelation.verify_relation_file(Config.version, Config.region):
                if not dumped:
                    self._dump_and_compile()
                    dumped = True
                relation_builder = CharacterNameRelation()
                excel_resource = relation_builder.get_excel_res(resources)
                self.downloader.verify_and_download(excel_resource)
                relation_builder.main()

            keywords = CharacterNameRelation.search(
                Config.version,
                Config.region,
                Config.advance_search,
            )

        if Config.search:
            keywords = Config.search

        if keywords:
            resources = ResourceUtils.search_name(resources, keywords)

        return resources

    def _filter_and_download(self, resources) -> None:
        filtered = ResourceUtils.filter_type(resources, Config.resource_type)
        self.downloader.verify_and_download(filtered)

    def run(self) -> None:
        resources = self.downloader.main()

        if Config.region == "jp":
            dumped = False
            if "table" in Config.resource_type:
                self._dump_and_compile()
                dumped = True
            if Config.search or Config.advance_search:
                resources = self._search_resource(resources, dumped)
            self._filter_and_download(resources)
            self.extract_service.run_post_download()
            return

        if Config.region == "gl":
            self._dump_and_compile()
            if Config.search or Config.advance_search:
                resources = self._search_resource(resources, True)
            self._filter_and_download(resources)
            self.extract_service.run()
            return

        self._filter_and_download(resources)
