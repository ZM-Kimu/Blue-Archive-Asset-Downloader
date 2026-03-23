from typing import Callable

from ba_downloader.domain.ports.region import Region, RegionProvider
from ba_downloader.regions.cn import CNServer
from ba_downloader.regions.gl import GLServer
from ba_downloader.regions.jp import JPServer


class RegionRegistry:
    def __init__(self) -> None:
        self._providers: dict[Region, Callable[[], RegionProvider]] = {}

    def register(self, region: Region, provider_factory: Callable[[], RegionProvider]) -> None:
        self._providers[region] = provider_factory

    def resolve(self, region: Region) -> RegionProvider:
        if region not in self._providers:
            raise KeyError(f"Region '{region}' is not registered.")
        return self._providers[region]()


DEFAULT_REGION_REGISTRY = RegionRegistry()
DEFAULT_REGION_REGISTRY.register("cn", CNServer)
DEFAULT_REGION_REGISTRY.register("gl", GLServer)
DEFAULT_REGION_REGISTRY.register("jp", JPServer)
