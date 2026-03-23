from typing import Generic, Protocol, TypeVar

from ba_downloader.domain.models.asset import (
    AssetCollection,
    BootstrapSession,
    CatalogSource,
    ResolvedRelease,
)
from ba_downloader.domain.models.runtime import RuntimeContext

TDecoded = TypeVar("TDecoded")


class ReleaseResolver(Protocol):
    def resolve(self, context: RuntimeContext) -> ResolvedRelease:
        ...


class SessionBootstrapper(Protocol):
    def bootstrap(
        self,
        release: ResolvedRelease,
        context: RuntimeContext,
    ) -> BootstrapSession:
        ...


class CatalogSourceProvider(Protocol):
    def fetch(
        self,
        session: BootstrapSession,
        context: RuntimeContext,
    ) -> list[CatalogSource]:
        ...


class CatalogDecoder(Protocol, Generic[TDecoded]):
    def decode(
        self,
        session: BootstrapSession,
        sources: list[CatalogSource],
        context: RuntimeContext,
    ) -> TDecoded:
        ...


class AssetNormalizer(Protocol, Generic[TDecoded]):
    def normalize(
        self,
        payload: TDecoded,
        session: BootstrapSession,
    ) -> AssetCollection:
        ...
