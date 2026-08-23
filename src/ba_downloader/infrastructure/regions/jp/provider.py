from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse

from ba_downloader.domain.models.asset import (
    AssetCollection,
    BootstrapSession,
    RegionCapabilities,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.region_catalog import (
    DecodedJPCatalog,
    RegionCatalogResult,
)
from ba_downloader.domain.ports.execution import CancellationPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.pipeline import CatalogDecoder
from ba_downloader.domain.ports.progress import ProgressReporterFactoryPort
from ba_downloader.domain.services.catalog_pipeline import CatalogPipeline
from ba_downloader.infrastructure.extraction.assetripper import (
    AssetRipperRuntimeMetadataInspector,
    AssetRipperSourceResolver,
)
from ba_downloader.infrastructure.packages.apkpure import ApkPurePackageRelease
from ba_downloader.infrastructure.regions.jp.asset_normalizer import JPAssetNormalizer
from ba_downloader.infrastructure.regions.jp.bootstrapper import JPBootstrapper
from ba_downloader.infrastructure.regions.jp.catalog_source import (
    CatalogSelection,
    JPCatalogSourceProvider,
)
from ba_downloader.infrastructure.regions.jp.release_resolver import JPReleaseResolver
from ba_downloader.infrastructure.runtime.process import CancellableProcessRunner


class JPRegionProvider:
    CAPABILITIES = RegionCapabilities(
        supports_sync=True,
        supports_advanced_search=True,
        supports_character_index_build=True,
    )

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        catalog_decoder: CatalogDecoder[DecodedJPCatalog],
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.release_resolver = JPReleaseResolver(http_client)
        self.bootstrapper = JPBootstrapper(
            http_client,
            logger,
            AssetRipperRuntimeMetadataInspector(
                AssetRipperSourceResolver(
                    http_client,
                    logger,
                    cancellation=cancellation,
                ),
                CancellableProcessRunner(cancellation),
                logger=logger,
            ),
            progress_factory=progress_factory,
            cancellation=cancellation,
        )
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

    def apk_extract_folder(self, context: ExecutionContext) -> str:
        return self.bootstrapper.apk_extract_folder(context)

    def load_catalog(self, context: ExecutionContext) -> RegionCatalogResult:
        if context.resource_version:
            self.logger.warn(
                "Specifying a version is not allowed with JPRegionProvider."
            )

        self.logger.info("Automatically fetching latest package info...")
        assets, resolved_context = self.pipeline.load(context)
        self.logger.info(
            f"Current resource version: {resolved_context.resource_version}"
        )
        self.logger.info(f"Catalog: {assets}.")
        return RegionCatalogResult(
            resources=assets,
            context=resolved_context,
        )

    def load_character_index_catalog(
        self,
        context: ExecutionContext,
    ) -> RegionCatalogResult:
        if context.resource_version:
            self.logger.warn(
                "Specifying a version is not allowed with JPRegionProvider."
            )
        self.logger.info("Automatically fetching latest package info...")
        release = self.release_resolver.resolve(context)
        resolved_context = context.resolve_resource_version(release.version)
        session = self.bootstrapper.bootstrap(release, resolved_context)
        assets = self._load_selected_catalog(
            session,
            resolved_context,
            CatalogSelection.TABLE_ONLY,
        )
        self.logger.info(
            f"Current resource version: {resolved_context.resource_version}"
        )
        self.logger.info(f"Catalog: {assets}.")
        return RegionCatalogResult(resources=assets, context=resolved_context)

    @classmethod
    def parse_package_info(cls, payload: bytes) -> ApkPurePackageRelease:
        return JPReleaseResolver.parse_package_info(payload)

    def get_latest_package_info(self) -> ApkPurePackageRelease:
        return self.release_resolver.get_latest_package_info()

    def get_latest_version(self) -> str:
        return self.get_latest_package_info().version

    def get_server_url(self, context: ExecutionContext) -> str:
        return self.bootstrapper.get_server_url(context)

    def _load_asset_collection(
        self,
        session: BootstrapSession,
        context: ExecutionContext,
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

    def _load_selected_catalog(
        self,
        session: BootstrapSession,
        context: ExecutionContext,
        selection: CatalogSelection,
    ) -> AssetCollection:
        raw_candidates = session.metadata.get("catalog_root_candidates", ())
        candidates = (
            [str(item) for item in raw_candidates if isinstance(item, str) and item]
            if isinstance(raw_candidates, (list, tuple))
            else []
        )
        if not candidates:
            candidates = [session.catalog_root]

        failures: list[str] = []
        for catalog_root in candidates:
            candidate_session = replace(session, catalog_root=catalog_root)
            try:
                sources = self.catalog_source_provider.fetch(
                    candidate_session,
                    context,
                    selection,
                )
                decoded = self.catalog_decoder.decode(
                    candidate_session,
                    sources,
                    context,
                )
                if selection is CatalogSelection.TABLE_ONLY:
                    self._validate_character_index_tables(
                        decoded,
                        candidate_session,
                    )
                assets = self.asset_normalizer.normalize(decoded, candidate_session)
                if not assets:
                    raise ValueError("decoded catalog did not contain any assets")
                return assets
            except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
                failures.append(f"{catalog_root}: {exc}")

        details = "; ".join(failures)
        raise LookupError(
            f"No JP catalog root produced a valid {selection.value} catalog. {details}"
        )

    @staticmethod
    def _validate_character_index_tables(
        catalog: DecodedJPCatalog,
        session: BootstrapSession,
    ) -> None:
        seen_paths: set[str] = set()
        excel_resources = 0
        for table in catalog.tables:
            name = table.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("JP table catalog entry has an invalid path.")
            normalized_name = name.replace("\\", "/").lstrip("/")
            if normalized_name in seen_paths:
                raise ValueError(
                    f"JP table catalog path is not unique: {normalized_name}."
                )
            seen_paths.add(normalized_name)

            size = table.get("size")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ValueError(
                    f"JP table catalog size is invalid for {normalized_name}."
                )
            crc = table.get("crc")
            try:
                int(str(crc), 10)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"JP table catalog CRC is invalid for {normalized_name}."
                ) from exc
            includes = table.get("includes")
            if not isinstance(includes, list) or not all(
                isinstance(item, str) for item in includes
            ):
                raise ValueError(
                    f"JP table catalog includes are invalid for {normalized_name}."
                )
            resource_url = urljoin(
                session.catalog_root.rstrip("/") + "/",
                f"TableBundles/{normalized_name}",
            )
            parsed_url = urlparse(resource_url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ValueError(
                    f"JP table catalog URL is invalid for {normalized_name}."
                )
            identifiers = [PurePosixPath(normalized_name).name, *includes]
            if any("exceldb" in item.casefold() for item in identifiers):
                excel_resources += 1

        if excel_resources != 1:
            raise ValueError(
                "JP table catalog must resolve exactly one ExcelDB resource; "
                f"resolved {excel_resources}."
            )


__all__ = [
    "JPAssetNormalizer",
    "JPBootstrapper",
    "JPCatalogSourceProvider",
    "JPRegionProvider",
    "JPReleaseResolver",
]
