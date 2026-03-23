from typing import Callable

from ba_downloader.domain.models.asset import RegionCapabilities
from ba_downloader.domain.ports.region import Region, RegionProvider
from ba_downloader.infrastructure.regions.providers import (
    CNServer,
    GLServer,
    JPServer,
    LegacyRegionPipelineAdapter,
)


class RegionRegistry:
    def __init__(self) -> None:
        self._providers: dict[Region, Callable[..., RegionProvider]] = {}

    def register(
        self,
        region: Region,
        provider_factory: Callable[..., RegionProvider],
    ) -> None:
        self._providers[region] = provider_factory

    def resolve(self, region: Region) -> Callable[..., RegionProvider]:
        if region not in self._providers:
            raise KeyError(f"Region '{region}' is not registered.")
        return self._providers[region]


def build_cn_provider(**kwargs) -> RegionProvider:
    return LegacyRegionPipelineAdapter(
        CNServer,
        capabilities=RegionCapabilities(
            supports_sync=True,
            supports_advanced_search=False,
            supports_relation_build=False,
        ),
        **kwargs,
    )


def build_gl_provider(**kwargs) -> RegionProvider:
    return LegacyRegionPipelineAdapter(
        GLServer,
        capabilities=RegionCapabilities(
            supports_sync=True,
            supports_advanced_search=True,
            supports_relation_build=True,
        ),
        **kwargs,
    )


build_cn_provider.__name__ = "CNServer"
build_gl_provider.__name__ = "GLServer"


DEFAULT_REGION_REGISTRY = RegionRegistry()
DEFAULT_REGION_REGISTRY.register("cn", build_cn_provider)
DEFAULT_REGION_REGISTRY.register("gl", build_gl_provider)
DEFAULT_REGION_REGISTRY.register("jp", JPServer)
