from __future__ import annotations

from urllib.parse import urljoin

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetType,
    BootstrapSession,
)
from ba_downloader.domain.models.region_catalog import DecodedJPCatalog
from ba_downloader.infrastructure.regions.common import (
    coerce_int,
    coerce_string_list,
)


class JPAssetNormalizer:
    @staticmethod
    def normalize(
        payload: DecodedJPCatalog, session: BootstrapSession
    ) -> AssetCollection:
        assets = AssetCollection()
        base_url = session.catalog_root.rstrip("/") + "/"
        bundle_patch_dir = str(
            session.metadata.get("bundle_patch_dir", "Android_PatchPack")
        )

        for table in payload.tables:
            includes = coerce_string_list(table.get("includes", []))
            assets.add(
                urljoin(base_url, f"TableBundles/{table['name']}"),
                urljoin("Table/", str(table["name"])),
                coerce_int(table.get("size")),
                str(table["crc"]),
                "crc",
                AssetType.table,
                {"includes": includes},
            )

        for media in payload.media:
            assets.add(
                urljoin(base_url, f"MediaResources/{media['path']}"),
                urljoin("Media/", str(media["path"])),
                coerce_int(media.get("bytes")),
                str(media["crc"]),
                "crc",
                AssetType.media,
                {"media_type": media["type"]},
            )

        for bundle in payload.bundles:
            bundle_files = coerce_string_list(bundle.get("bundle_files", []))
            assets.add(
                urljoin(base_url, f"{bundle_patch_dir}/{bundle['name']}"),
                urljoin("Bundle/", str(bundle["name"])),
                coerce_int(bundle.get("size")),
                str(bundle["crc"]),
                "crc",
                AssetType.bundle,
                {"bundle_files": bundle_files},
            )

        return assets
