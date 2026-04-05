from __future__ import annotations

from typing import Generic, TypeVar

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.pipeline import (
    AssetNormalizer,
    CatalogDecoder,
    CatalogSourceProvider,
    ReleaseResolver,
    SessionBootstrapper,
)

TDecoded = TypeVar("TDecoded")


class CatalogPipeline(Generic[TDecoded]):
    def __init__(
        self,
        release_resolver: ReleaseResolver,
        bootstrapper: SessionBootstrapper,
        source_provider: CatalogSourceProvider,
        decoder: CatalogDecoder[TDecoded],
        normalizer: AssetNormalizer[TDecoded],
    ) -> None:
        self.release_resolver = release_resolver
        self.bootstrapper = bootstrapper
        self.source_provider = source_provider
        self.decoder = decoder
        self.normalizer = normalizer

    def load(self, context: RuntimeContext) -> tuple[AssetCollection, RuntimeContext]:
        release = self.release_resolver.resolve(context)
        resolved_context = context.with_updates(version=release.version)
        session = self.bootstrapper.bootstrap(release, resolved_context)
        sources = self.source_provider.fetch(session, resolved_context)
        decoded = self.decoder.decode(session, sources, resolved_context)
        assets = self.normalizer.normalize(decoded, session)
        return assets, resolved_context
