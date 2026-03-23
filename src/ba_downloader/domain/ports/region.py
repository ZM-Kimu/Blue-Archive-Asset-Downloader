from typing import Literal, Protocol

from ba_downloader.lib.structure import Resource

Region = Literal["cn", "gl", "jp"]


class RegionProvider(Protocol):
    def main(self) -> Resource:
        ...
