from ba_downloader.extractors.character import CharacterNameRelation
from ba_downloader.infrastructure.services.downloader_engine import DownloaderEngine
from ba_downloader.infrastructure.services.extractor_engine import FlatbufferExtractor


class RelationService:
    def __init__(self) -> None:
        self.downloader = DownloaderEngine()
        self.flatbuffer = FlatbufferExtractor()

    def build(self) -> None:
        self.flatbuffer.dump()
        self.flatbuffer.compile()

        resources = self.downloader.main()
        relation_builder = CharacterNameRelation()
        excel_resources = relation_builder.get_excel_res(resources)
        self.downloader.verify_and_download(excel_resources)
        relation_builder.main()
