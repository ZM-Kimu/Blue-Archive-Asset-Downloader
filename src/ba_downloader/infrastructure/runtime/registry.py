from __future__ import annotations

from typing import Callable

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.region import Region
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort
from ba_downloader.infrastructure.regions.providers.gl import GLRuntimeAssetPreparer


class NoOpRuntimeAssetPreparer(RuntimeAssetPreparerPort):
    def prepare(self, context: RuntimeContext) -> None:
        _ = context


class RuntimeAssetPreparerRegistry:
    def __init__(self) -> None:
        self._preparers: dict[Region, Callable[..., RuntimeAssetPreparerPort]] = {}

    def register(
        self,
        region: Region,
        preparer_factory: Callable[..., RuntimeAssetPreparerPort],
    ) -> None:
        self._preparers[region] = preparer_factory

    def resolve(self, region: Region) -> Callable[..., RuntimeAssetPreparerPort]:
        if region not in self._preparers:
            raise KeyError(f"Region '{region}' is not registered.")
        return self._preparers[region]


def build_noop_runtime_preparer(**_: object) -> RuntimeAssetPreparerPort:
    return NoOpRuntimeAssetPreparer()


DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY = RuntimeAssetPreparerRegistry()
DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.register("cn", build_noop_runtime_preparer)
DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.register("gl", GLRuntimeAssetPreparer)
DEFAULT_RUNTIME_ASSET_PREPARER_REGISTRY.register("jp", build_noop_runtime_preparer)
