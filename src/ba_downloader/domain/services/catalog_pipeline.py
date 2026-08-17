from __future__ import annotations

from dataclasses import replace
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
        raw_candidates = session.metadata.get("catalog_root_candidates", ())
        candidates = (
            [str(item) for item in raw_candidates if isinstance(item, str) and item]
            if isinstance(raw_candidates, (list, tuple))
            else []
        )
        if not candidates:
            sources = self.source_provider.fetch(session, resolved_context)
            decoded = self.decoder.decode(session, sources, resolved_context)
            assets = self.normalizer.normalize(decoded, session)
            return assets, resolved_context

        failures: list[str] = []
        for catalog_root in candidates:
            candidate_session = replace(session, catalog_root=catalog_root)
            try:
                sources = self.source_provider.fetch(
                    candidate_session,
                    resolved_context,
                )
                decoded = self.decoder.decode(
                    candidate_session,
                    sources,
                    resolved_context,
                )
                assets = self.normalizer.normalize(decoded, candidate_session)
                if not assets:
                    raise ValueError("decoded catalog did not contain any assets")
                return assets, resolved_context
            except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
                failures.append(f"{catalog_root}: {exc}")

        details = "; ".join(failures)
        raise LookupError(f"No catalog root produced a valid catalog. {details}")
