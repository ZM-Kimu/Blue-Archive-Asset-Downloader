from __future__ import annotations

import base64
import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from ba_downloader.domain.models.asset import BootstrapSession, ResolvedRelease
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import ProgressReporterFactoryPort
from ba_downloader.infrastructure.extraction.assetripper.exporter import (
    AssetRipperRuntimeMetadata,
    assetripper_exporter_cache_key,
)
from ba_downloader.infrastructure.packages import (
    PackageArchiveError,
    download_package_file,
)
from ba_downloader.infrastructure.packages import (
    extract_jp_xapk_file as extract_xapk_file,
)
from ba_downloader.infrastructure.packages.jp_server_info import JPServerInfoDecoder
from ba_downloader.infrastructure.regions.jp.platform import build_jp_platform_profile
from ba_downloader.infrastructure.regions.jp.runtime_assets import (
    locate_jp_runtime_payload,
)
from ba_downloader.infrastructure.runtime import RuntimeSnapshotStore


class RuntimeMetadataInspector(Protocol):
    def inspect(
        self,
        context: RuntimeContext,
        data_root: Path,
    ) -> AssetRipperRuntimeMetadata: ...


class ServerInfoDecoder(Protocol):
    def decode_server_url(self, data: bytes) -> str: ...


class _MissingRuntimeMetadataInspector:
    def inspect(
        self,
        context: RuntimeContext,
        data_root: Path,
    ) -> AssetRipperRuntimeMetadata:
        _ = (context, data_root)
        raise RuntimeError("JP runtime metadata inspector is not configured.")


class JPBootstrapper:
    METADATA_CACHE_SCHEMA_VERSION = 1

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        runtime_metadata_inspector: RuntimeMetadataInspector | None = None,
        server_info_decoder: ServerInfoDecoder | None = None,
        snapshot_store: RuntimeSnapshotStore | None = None,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.runtime_metadata_inspector = (
            runtime_metadata_inspector or _MissingRuntimeMetadataInspector()
        )
        self.server_info_decoder = server_info_decoder or JPServerInfoDecoder()
        self.snapshot_store = snapshot_store or RuntimeSnapshotStore()
        self.progress_factory = progress_factory
        self.cancellation = cancellation or NeverCancelled()

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

        cached_metadata = self._load_runtime_metadata_cache(context)
        runtime_manifest = (
            self.snapshot_store.runtime_dir(context, context.version) / "manifest.json"
        )
        apk_path = ""
        if cached_metadata is None or not runtime_manifest.is_file():
            try:
                apk_path = self._prepare_package(release, context)
            except PackageArchiveError as exc:
                raise LookupError(
                    "Downloaded JP package is invalid or incomplete. "
                    "Retry may solve the issue, and proxy or network instability may have "
                    f"caused the package to be corrupted. Details: {exc}"
                ) from exc
        server_url = self.get_server_url(context)
        addressables_response = self.http_client.request("GET", server_url)
        if not 200 <= addressables_response.status_code < 300:
            raise LookupError(
                "JP addressables request returned HTTP "
                f"{addressables_response.status_code} for {server_url}."
            )
        if not addressables_response.content:
            raise LookupError("JP addressables response was empty.")
        try:
            addressables_payload = addressables_response.json()
        except (TypeError, ValueError) as exc:
            raise LookupError("JP addressables response is not valid JSON.") from exc
        if not isinstance(addressables_payload, Mapping):
            raise LookupError("JP addressables response must be a JSON object.")
        catalog_roots = self._resolve_catalog_roots(addressables_payload)
        return BootstrapSession(
            release=release,
            server_url=server_url,
            catalog_root=catalog_roots[0],
            metadata={
                "bundle_patch_dir": build_jp_platform_profile(context).bundle_patch_dir,
                "catalog_root_candidates": catalog_roots,
                **({"apk_path": apk_path} if apk_path else {}),
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
                    progress_factory=self.progress_factory,
                    cancellation=self.cancellation,
                )
            )
            extract_xapk_file(
                str(apk_path),
                str(staged_package_dir / "Extracted"),
                str(staged_package_dir / "Parts"),
                cancellation=self.cancellation,
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
        if not package_dir.is_dir():
            return None
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
            and locate_jp_runtime_payload(runtime_dir) is not None
        )

    @staticmethod
    def _resolve_catalog_root(addressable_payload: Mapping[str, Any]) -> str:
        return JPBootstrapper._resolve_catalog_roots(addressable_payload)[0]

    @staticmethod
    def _resolve_catalog_roots(
        addressable_payload: Mapping[str, Any],
    ) -> tuple[str, ...]:
        connection_groups = addressable_payload.get("ConnectionGroups", [])
        if not connection_groups:
            raise LookupError("ConnectionGroups not found in JP addressables response.")

        override_groups = connection_groups[0].get("OverrideConnectionGroups", [])
        roots: list[str] = []
        for group in override_groups:
            if not isinstance(group, Mapping):
                continue
            raw_root = group.get("AddressablesCatalogUrlRoot")
            if not isinstance(raw_root, str) or not raw_root.strip():
                continue
            root = raw_root.strip().rstrip("/") + "/"
            parsed = urlparse(root)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if root not in roots:
                roots.append(root)

        if roots:
            return tuple(roots)

        raise LookupError(
            "AddressablesCatalogUrlRoot not found in JP addressables response."
        )

    def get_server_url(self, context: RuntimeContext) -> str:
        self.logger.info("Retrieving game info...")
        cached = self._load_runtime_metadata_cache(context)
        if cached is not None:
            url, version = cached
            self._log_runtime_metadata(url, version, context)
            return url

        data_root = Path(self.apk_extract_folder(context)) / "assets/bin/Data"
        metadata = self.runtime_metadata_inspector.inspect(context, data_root)
        url = self.server_info_decoder.decode_server_url(metadata.game_main_config)
        version = metadata.bundle_version
        parsed_url = urlparse(url)
        if (
            not url
            or parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            raise LookupError("Cannot find server url from apk.")
        package_archive = self._find_package_archive(self.package_dir(context))
        if package_archive is not None:
            self._publish_runtime_metadata_cache(
                context,
                metadata,
                url,
                package_archive,
            )
        self._log_runtime_metadata(url, version, context)
        return url

    def _metadata_cache_path(self, context: RuntimeContext) -> Path:
        return (
            self.snapshot_store.version_root(context, context.version)
            / "Metadata"
            / "manifest.json"
        )

    def _load_runtime_metadata_cache(
        self,
        context: RuntimeContext,
    ) -> tuple[str, str] | None:
        manifest_path = self._metadata_cache_path(context)
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf8"))
        except (OSError, json.JSONDecodeError):
            return None
        package = payload.get("package") if isinstance(payload, dict) else None
        if not (
            isinstance(payload, dict)
            and payload.get("schema_version") == self.METADATA_CACHE_SCHEMA_VERSION
            and payload.get("region") == context.region
            and payload.get("platform") == context.platform
            and payload.get("release") == context.version
            and payload.get("tool_fingerprint") == assetripper_exporter_cache_key()
            and isinstance(package, dict)
            and isinstance(package.get("size"), int)
            and package.get("size", 0) > 0
            and isinstance(package.get("sha256"), str)
            and len(package["sha256"]) == 64
            and isinstance(payload.get("server_url"), str)
            and isinstance(payload.get("bundle_version"), str)
            and isinstance(payload.get("game_main_config_base64"), str)
        ):
            return None
        try:
            base64.b64decode(payload["game_main_config_base64"], validate=True)
        except ValueError:
            return None
        url = payload["server_url"]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return url, payload["bundle_version"]

    def _publish_runtime_metadata_cache(
        self,
        context: RuntimeContext,
        metadata: AssetRipperRuntimeMetadata,
        server_url: str,
        package_archive: Path,
    ) -> None:
        with self.snapshot_store.staging_directory(
            context,
            context.version,
            directory_name="Metadata",
        ) as metadata_dir:
            payload = {
                "schema_version": self.METADATA_CACHE_SCHEMA_VERSION,
                "region": context.region,
                "platform": context.platform,
                "release": context.version,
                "tool_fingerprint": assetripper_exporter_cache_key(),
                "package": {
                    "size": package_archive.stat().st_size,
                    "sha256": self._sha256(package_archive),
                },
                "server_url": server_url,
                "bundle_version": metadata.bundle_version,
                "game_main_config_base64": base64.b64encode(
                    metadata.game_main_config
                ).decode("ascii"),
            }
            (metadata_dir / "manifest.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf8",
            )
            self.snapshot_store.publish_directory(
                context,
                context.version,
                metadata_dir,
                directory_name="Metadata",
            )

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                self.cancellation.raise_if_cancelled()
                digest.update(chunk)
        return digest.hexdigest()

    def _log_runtime_metadata(
        self,
        url: str,
        version: str,
        context: RuntimeContext,
    ) -> None:
        self.logger.info(f"Resolved server URL: {url}")
        if version:
            self.logger.info(f"The apk version is {version}.")
        if version and version != context.version:
            self.logger.warn("Server version is different with apk version.")
        elif not version:
            self.logger.warn("Cannot retrieve apk version data.")
