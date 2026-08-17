from __future__ import annotations

from enum import StrEnum
from urllib.parse import urljoin

from ba_downloader.domain.models.asset import BootstrapSession, CatalogSource
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.regions.jp.platform import build_jp_platform_profile


class CatalogSelection(StrEnum):
    FULL = "full"
    TABLE_ONLY = "table_only"


class JPCatalogSourceProvider:
    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def fetch(
        self,
        session: BootstrapSession,
        context: RuntimeContext,
        selection: CatalogSelection = CatalogSelection.FULL,
    ) -> list[CatalogSource]:
        base_url = session.catalog_root.rstrip("/") + "/"
        sources: list[CatalogSource] = []
        bundle_patch_dir = build_jp_platform_profile(context).bundle_patch_dir

        targets = [("table", urljoin(base_url, "TableBundles/TableCatalog.bytes"))]
        if selection is CatalogSelection.FULL:
            targets.extend(
                (
                    (
                        "media",
                        urljoin(
                            base_url,
                            "MediaResources/Catalog/MediaCatalog.bytes",
                        ),
                    ),
                    (
                        "bundle",
                        urljoin(
                            base_url,
                            f"{bundle_patch_dir}/BundlePackingInfo.json",
                        ),
                    ),
                )
            )

        for name, url in targets:
            response = self.http_client.request("GET", url)
            if not 200 <= response.status_code < 300:
                raise FileNotFoundError(
                    f"JP {name} catalog request returned HTTP {response.status_code} "
                    f"for {url}."
                )
            if not response.content:
                raise FileNotFoundError(
                    f"JP {name} catalog response was empty for {url}."
                )
            sources.append(
                CatalogSource(
                    name=name,
                    url=url,
                    content=response.content,
                    content_type=str(response.headers.get("content-type", "")),
                )
            )

        if len(sources) != len(targets):
            raise FileNotFoundError("Cannot pull the requested JP catalogs.")
        return sources
