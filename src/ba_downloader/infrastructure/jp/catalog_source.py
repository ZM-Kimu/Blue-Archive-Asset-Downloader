from __future__ import annotations

from urllib.parse import urljoin

from ba_downloader.domain.models.asset import BootstrapSession, CatalogSource
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.jp.models import resolve_jp_patch_pack_dir


class JPCatalogSourceProvider:
    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def fetch(
        self,
        session: BootstrapSession,
        context: RuntimeContext,
    ) -> list[CatalogSource]:
        base_url = session.catalog_root.rstrip("/") + "/"
        sources: list[CatalogSource] = []
        bundle_patch_dir = resolve_jp_patch_pack_dir(context.platform)

        targets = (
            ("table", urljoin(base_url, "TableBundles/TableCatalog.bytes")),
            ("media", urljoin(base_url, "MediaResources/Catalog/MediaCatalog.bytes")),
            ("bundle", urljoin(base_url, f"{bundle_patch_dir}/BundlePackingInfo.json")),
        )

        for name, url in targets:
            response = self.http_client.request("GET", url)
            if not response.content:
                self.logger.error(f"Failed to fetch JP {name} catalog from {url}.")
                continue
            sources.append(
                CatalogSource(
                    name=name,
                    url=url,
                    content=response.content,
                    content_type=str(response.headers.get("content-type", "")),
                )
            )

        if len(sources) < 3:
            raise FileNotFoundError("Cannot pull the JP manifest.")
        return sources
