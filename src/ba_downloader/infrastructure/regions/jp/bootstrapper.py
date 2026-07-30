from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
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
from ba_downloader.infrastructure.regions.jp.platform import build_jp_platform_profile
from ba_downloader.infrastructure.runtime import RuntimeSnapshotStore


class JPBootstrapper:
    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        server_info_extractor: JPServerInfoExtractor | None = None,
        snapshot_store: RuntimeSnapshotStore | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.server_info_extractor = server_info_extractor or JPServerInfoExtractor()
        self.snapshot_store = snapshot_store or RuntimeSnapshotStore()

    def package_dir(self, context: RuntimeContext) -> Path:
        return self.snapshot_store.version_root(context, context.version) / "Package"

    def apk_extract_folder(self, context: RuntimeContext) -> str:
        return str(self.package_dir(context) / "Extracted")

    def bootstrap(
        self,
        release: ResolvedRelease,
        context: RuntimeContext,
    ) -> BootstrapSession:
        if not release.package_url:
            raise LookupError("JP release does not contain a package URL.")
        if not context.version or context.version != release.version:
            raise ValueError(
                "JP bootstrap requires a context resolved to the package version."
            )

        try:
            apk_path = self._prepare_package(release, context)
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
                "bundle_patch_dir": build_jp_platform_profile(context).bundle_patch_dir,
            },
        )

    def _prepare_package(
        self,
        release: ResolvedRelease,
        context: RuntimeContext,
    ) -> str:
        package_dir = self.package_dir(context)
        if self._has_required_package_assets(package_dir):
            existing_archive = self._find_package_archive(package_dir)
            if existing_archive is not None:
                return str(existing_archive)

        self.logger.info("Downloading APK to retrieve server URL...")
        with self.snapshot_store.staging_directory(
            context,
            release.version,
            directory_name="Package",
        ) as staged_package_dir:
            apk_path = Path(
                download_package_file(
                    self.http_client,
                    self.logger,
                    release.package_url,
                    str(staged_package_dir),
                )
            )
            extract_xapk_file(
                str(apk_path),
                str(staged_package_dir / "Extracted"),
                str(staged_package_dir / "Parts"),
            )
            shutil.rmtree(staged_package_dir / "Parts", ignore_errors=True)
            if not self._has_required_package_assets(staged_package_dir):
                raise PackageArchiveError(
                    "JP package extraction is missing metadata, runtime binary, "
                    "or globalgamemanagers from this package."
                )
            relative_archive = apk_path.relative_to(staged_package_dir)
            published_dir = self.snapshot_store.publish_directory(
                context,
                release.version,
                staged_package_dir,
                directory_name="Package",
            )
            return str(published_dir / relative_archive)

    @staticmethod
    def _find_package_archive(package_dir: Path) -> Path | None:
        return next(
            (
                path
                for path in sorted(package_dir.iterdir())
                if path.is_file() and path.suffix.lower() in {".apk", ".xapk"}
            ),
            None,
        )

    @staticmethod
    def _has_required_package_assets(package_dir: Path) -> bool:
        extracted_dir = package_dir / "Extracted"
        metadata_path = (
            extracted_dir / "assets/bin/Data/Managed/Metadata/global-metadata.dat"
        )
        managers_path = extracted_dir / "assets/bin/Data/globalgamemanagers"
        runtime_dir = extracted_dir / "lib/arm64-v8a"
        return (
            metadata_path.is_file()
            and managers_path.is_file()
            and (
                (runtime_dir / "libgedenedo.so").is_file()
                or (runtime_dir / "libil2cpp.so").is_file()
            )
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
        data_root = Path(self.apk_extract_folder(context)) / "assets/bin/Data"
        url, version = self.server_info_extractor.find_server_info(str(data_root))
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
