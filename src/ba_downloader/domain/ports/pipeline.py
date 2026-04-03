from typing import Generic, Protocol, TypeVar

from ba_downloader.domain.models.asset import (
    AssetCollection,
    BootstrapSession,
    CatalogSource,
    ResolvedRelease,
)
from ba_downloader.domain.models.runtime import RuntimeContext

TDecodedCo = TypeVar("TDecodedCo", covariant=True)
TDecodedContra = TypeVar("TDecodedContra", contravariant=True)


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


class CatalogDecoder(Protocol, Generic[TDecodedCo]):
    def decode(
        self,
        session: BootstrapSession,
        sources: list[CatalogSource],
        context: RuntimeContext,
    ) -> TDecodedCo:
        ...


class AssetNormalizer(Protocol, Generic[TDecodedContra]):
    def normalize(
        self,
        payload: TDecodedContra,
        session: BootstrapSession,
    ) -> AssetCollection:
        ...
