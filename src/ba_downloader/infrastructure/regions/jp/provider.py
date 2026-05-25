from __future__ import annotations

from ba_downloader.domain.models.asset import (
    AssetCollection,
    BootstrapSession,
    RegionCapabilities,
    ResolvedRelease,
)
from ba_downloader.domain.models.region_catalog import (
    DecodedJPCatalog,
    RegionCatalogResult,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.pipeline import CatalogDecoder
from ba_downloader.domain.services.catalog_pipeline import CatalogPipeline
from ba_downloader.infrastructure.regions.common import (
    SYNC_AND_RELATION_CAPABILITIES,
)
from ba_downloader.infrastructure.regions.jp.asset_normalizer import JPAssetNormalizer
from ba_downloader.infrastructure.regions.jp.bootstrapper import JPBootstrapper
from ba_downloader.infrastructure.regions.jp.catalog_source import (
    JPCatalogSourceProvider,
)
from ba_downloader.infrastructure.regions.jp.models import APKPackageInfo
from ba_downloader.infrastructure.regions.jp.release_resolver import JPReleaseResolver


class JPRegionProvider:
    CAPABILITIES = SYNC_AND_RELATION_CAPABILITIES

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        catalog_decoder: CatalogDecoder[DecodedJPCatalog],
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.release_resolver = JPReleaseResolver(http_client)
        self.bootstrapper = JPBootstrapper(http_client, logger)
        self.catalog_source_provider = JPCatalogSourceProvider(http_client, logger)
        self.catalog_decoder = catalog_decoder
        self.asset_normalizer = JPAssetNormalizer()
        self.pipeline = CatalogPipeline(
            self.release_resolver,
            self.bootstrapper,
            self.catalog_source_provider,
            self.catalog_decoder,
            self.asset_normalizer,
        )

    def get_capabilities(self) -> RegionCapabilities:
        return self.CAPABILITIES

    def apk_extract_folder(self, context: RuntimeContext) -> str:
        return self.bootstrapper.apk_extract_folder(context)

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        if context.version:
            self.logger.warn("Specifying a version is not allowed with JPRegionProvider.")

        self.logger.info("Automatically fetching latest package info...")
        assets, resolved_context = self.pipeline.load(context)
        self.logger.info(f"Current resource version: {resolved_context.version}")
        self.logger.info(f"Catalog: {assets}.")
        return RegionCatalogResult(
            resources=assets,
            context=resolved_context,
            capabilities=self.get_capabilities(),
        )

    def download_apk_file(self, apk_url: str, context: RuntimeContext) -> str:
        return self.bootstrapper.download_apk_file(apk_url, context)

    def extract_apk_file(self, apk_path: str, context: RuntimeContext) -> None:
        self.bootstrapper.extract_apk_file(apk_path, context)

    @classmethod
    def parse_package_info(cls, payload: bytes) -> APKPackageInfo:
        return JPReleaseResolver.parse_package_info(payload)

    def get_latest_package_info(self) -> APKPackageInfo:
        return self.release_resolver.get_latest_package_info()

    def get_latest_version(self) -> str:
        return self.get_latest_package_info().version

    def get_resource_manifest(self, server_url: str) -> AssetCollection:
        session = BootstrapSession(
            release=ResolvedRelease(region="jp", version=""),
            server_url=server_url,
            catalog_root=self.bootstrapper._resolve_catalog_root(
                self.http_client.request("GET", server_url).json()
            ),
        )
        return self._load_asset_collection(
            session,
            RuntimeContext(
                region="jp",
                threads=1,
                version="",
                raw_dir="",
                extract_dir="",
                temp_dir="",
                extract_while_download=False,
                resource_type=("table", "media", "bundle"),
                proxy_url="",
                max_retries=0,
                search=(),
                advanced_search=(),
                work_dir="",
            ),
        )

    def get_server_url(self, context: RuntimeContext) -> str:
        return self.bootstrapper.get_server_url(context)

    def _load_asset_collection(
        self,
        session: BootstrapSession,
        context: RuntimeContext,
    ) -> AssetCollection:
        try:
            sources = self.catalog_source_provider.fetch(session, context)
            decoded = self.catalog_decoder.decode(session, sources, context)
            assets = self.asset_normalizer.normalize(decoded, session)
            if not assets:
                raise FileNotFoundError("Cannot pull the JP manifest.")
            return assets
        except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {exc}."
            ) from exc


__all__ = [
    "APKPackageInfo",
    "JPAssetNormalizer",
    "JPBootstrapper",
    "JPCatalogSourceProvider",
    "JPRegionProvider",
    "JPReleaseResolver",
]
