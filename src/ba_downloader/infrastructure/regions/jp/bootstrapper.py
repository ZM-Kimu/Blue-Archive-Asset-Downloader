from __future__ import annotations

from collections.abc import Mapping
from os import path
from typing import Any

from ba_downloader.domain.models.asset import BootstrapSession, ResolvedRelease
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.packages import (
    PackageArchiveError,
    download_package_file,
    extract_xapk_file,
)
from ba_downloader.infrastructure.packages.jp_server_info import JPServerInfoExtractor
from ba_downloader.infrastructure.regions.jp.models import resolve_jp_patch_pack_dir


class JPBootstrapper:
    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        server_info_extractor: JPServerInfoExtractor | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.server_info_extractor = server_info_extractor or JPServerInfoExtractor()

    @staticmethod
    def apk_extract_folder(context: RuntimeContext) -> str:
        return path.join(context.temp_dir, "Data")

    def bootstrap(
        self,
        release: ResolvedRelease,
        context: RuntimeContext,
    ) -> BootstrapSession:
        if not release.package_url:
            raise LookupError("JP release does not contain a package URL.")

        try:
            apk_path = self.download_apk_file(release.package_url, context)
            self.extract_apk_file(apk_path, context)
        except PackageArchiveError as exc:
            raise LookupError(
                "Downloaded JP package is invalid or incomplete. "
                "Retry may solve the issue, and proxy or network instability may have "
                f"caused the package to be corrupted. Details: {exc}"
            ) from exc
        server_url = self.get_server_url(context)
        catalog_root = self._resolve_catalog_root(
            self.http_client.request("GET", server_url).json()
        )
        return BootstrapSession(
            release=release,
            server_url=server_url,
            catalog_root=catalog_root,
            metadata={
                "apk_path": apk_path,
                "bundle_patch_dir": resolve_jp_patch_pack_dir(context.platform),
            },
        )

    def download_apk_file(self, apk_url: str, context: RuntimeContext) -> str:
        self.logger.info("Downloading APK to retrieve server URL...")
        return download_package_file(
            self.http_client,
            self.logger,
            apk_url,
            context.temp_dir,
        )

    def extract_apk_file(self, apk_path: str, context: RuntimeContext) -> None:
        extract_xapk_file(
            apk_path,
            self.apk_extract_folder(context),
            context.temp_dir,
        )

    @staticmethod
    def _resolve_catalog_root(addressable_payload: Mapping[str, Any]) -> str:
        connection_groups = addressable_payload.get("ConnectionGroups", [])
        if not connection_groups:
            raise LookupError("ConnectionGroups not found in JP addressables response.")

        override_groups = connection_groups[0].get("OverrideConnectionGroups", [])
        roots = [
            str(group.get("AddressablesCatalogUrlRoot", "")).rstrip("/")
            for group in override_groups
            if group.get("AddressablesCatalogUrlRoot")
        ]

        if len(roots) >= 2:
            return roots[1] + "/"
        if roots:
            return roots[-1] + "/"

        raise LookupError(
            "AddressablesCatalogUrlRoot not found in JP addressables response."
        )

    def get_server_url(self, context: RuntimeContext) -> str:
        self.logger.info("Retrieving game info...")
        data_root = path.join(self.apk_extract_folder(context), "assets", "bin", "Data")
        url, version = self.server_info_extractor.find_server_info(data_root)
        if url:
            self.logger.info(f"Resolved server URL: {url}")
        if version:
            self.logger.info(f"The apk version is {version}.")

        if not url:
            raise LookupError("Cannot find server url from apk.")
        if version and version != context.version:
            self.logger.warn("Server version is different with apk version.")
        elif not version:
            self.logger.warn("Cannot retrieve apk version data.")
        return url
