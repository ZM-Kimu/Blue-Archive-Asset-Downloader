from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    write_json_atomic,
)
from ba_downloader.infrastructure.files.checksum import calculate_source_fingerprint
from ba_downloader.infrastructure.files.lock import wait_for_interprocess_lock

ASSETRIPPER_VERSION = "2.0.0"
ASSETRIPPER_COMMIT = "1ac666f47d8e9dedf96afb0b914c70d7656151ea"
ASSETRIPPER_ARCHIVE_URL = (
    f"https://github.com/AssetRipper/AssetRipper/archive/{ASSETRIPPER_COMMIT}.zip"
)
ASSETRIPPER_OVERLAY_SCHEMA_VERSION = 0


class AssetRipperSourceError(RuntimeError):
    pass


class AssetRipperSourceOverlayError(AssetRipperSourceError):
    pass


class AssetRipperSourceResolver:
    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        *,
        cancellation: CancellationPort | None = None,
        repository_root: Path | None = None,
        archive_url: str = ASSETRIPPER_ARCHIVE_URL,
        commit: str = ASSETRIPPER_COMMIT,
    ) -> None:
        self._http_client = http_client
        self._logger = logger
        self._cancellation = cancellation or NeverCancelled()
        self._repository_root = repository_root or Path(__file__).resolve().parents[5]
        self._archive_url = archive_url
        self._commit = commit

    def resolve(self, context: ExecutionContext) -> Path:
        self._cancellation.raise_if_cancelled()
        submodule_root = self._repository_root / "third_party" / "AssetRipper"
        if self._is_valid_source(submodule_root):
            return submodule_root

        cache_root = self._cache_root(context)
        if self._is_valid_source(cache_root):
            return cache_root

        with wait_for_interprocess_lock(
            context.workspace.locks / "assetripper-source.lock",
            operation="AssetRipper source preparation",
            cancellation_check=self._cancellation.raise_if_cancelled,
        ):
            if self._is_valid_source(cache_root):
                return cache_root
            self._logger.warn(
                "AssetRipper source is missing. Downloading fallback source package..."
            )
            last_error: Exception | None = None
            for _attempt in range(max(1, context.max_retries + 1)):
                try:
                    self._download_to_cache(cache_root)
                    return cache_root
                except OperationCancelledError:
                    raise
                except (
                    AssetRipperSourceError,
                    BadZipFile,
                    OSError,
                    ValueError,
                ) as exc:
                    last_error = exc

        raise AssetRipperSourceError(
            "Unable to resolve AssetRipper source. Initialize the submodule or "
            f"retry the fallback download. Details: {last_error}"
        ) from last_error

    def resolve_patched(self, context: ExecutionContext) -> Path:
        source_root = self.resolve(context)
        overlay_root = Path(__file__).with_name("overlay")
        manifest_path = overlay_root / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise AssetRipperSourceOverlayError(
                "AssetRipper source overlay manifest is invalid."
            ) from exc
        if not isinstance(manifest, dict):
            raise AssetRipperSourceOverlayError(
                "AssetRipper source overlay manifest must be an object."
            )
        if manifest.get("schema_version") != ASSETRIPPER_OVERLAY_SCHEMA_VERSION:
            raise AssetRipperSourceOverlayError(
                "AssetRipper source overlay schema is unsupported."
            )
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise AssetRipperSourceOverlayError(
                "AssetRipper source overlay has no replacement files."
            )

        cache_key = self.overlay_hash()
        cache_root = self._overlay_cache_root(context, cache_key)
        marker = cache_root / "overlay.json"
        if self._is_valid_overlay_cache(cache_root, marker, cache_key):
            return cache_root

        lock_path = context.workspace.locks / "assetripper-patched-source.lock"
        with wait_for_interprocess_lock(
            lock_path,
            operation="AssetRipper patched source preparation",
            cancellation_check=self._cancellation.raise_if_cancelled,
        ):
            if self._is_valid_overlay_cache(cache_root, marker, cache_key):
                return cache_root
            staging = cache_root.with_name(f".{cache_root.name}.staging-{uuid4().hex}")
            shutil.rmtree(staging, ignore_errors=True)
            self._logger.info("Preparing patched AssetRipper source...")
            marker_payload = {
                "schema_version": ASSETRIPPER_OVERLAY_SCHEMA_VERSION,
                "overlay_key": cache_key,
            }
            try:
                shutil.copytree(source_root, staging)
                self._apply_overlay(staging, overlay_root, files)
                write_json_atomic(
                    staging / "overlay.json",
                    marker_payload,
                    indent=2,
                    sort_keys=True,
                )
                publish_staged_directory(staging, cache_root)
            except (OSError, ValueError, AssetRipperSourceOverlayError):
                shutil.rmtree(staging, ignore_errors=True)
                raise
        return cache_root

    def _is_valid_overlay_cache(
        self,
        cache_root: Path,
        marker: Path,
        cache_key: str,
    ) -> bool:
        if not marker.is_file():
            return False
        try:
            cached = json.loads(marker.read_text(encoding="utf8"))
        except (OSError, ValueError):
            return False
        return (
            isinstance(cached, dict)
            and cached.get("schema_version") == ASSETRIPPER_OVERLAY_SCHEMA_VERSION
            and cached.get("overlay_key") == cache_key
            and self._is_valid_source(cache_root)
        )

    def _apply_overlay(
        self,
        source_root: Path,
        overlay_root: Path,
        files: list[object],
    ) -> None:
        for item in files:
            if not isinstance(item, dict):
                raise AssetRipperSourceOverlayError(
                    "AssetRipper source overlay entry is invalid."
                )
            relative_path = item.get("path")
            replacement = item.get("replacement")
            if not isinstance(relative_path, str) or not isinstance(replacement, str):
                raise AssetRipperSourceOverlayError(
                    "AssetRipper source overlay entry is incomplete."
                )
            target = (source_root / relative_path).resolve(strict=False)
            overlay_file = (overlay_root / replacement).resolve(strict=True)
            try:
                target.relative_to(source_root.resolve(strict=True))
                overlay_file.relative_to(overlay_root.resolve(strict=True))
            except ValueError as exc:
                raise AssetRipperSourceOverlayError(
                    "AssetRipper source overlay contains an unsafe path."
                ) from exc
            temporary = target.with_name(f".{target.name}.overlay-{uuid4().hex}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(overlay_file, temporary)
            temporary.replace(target)

    def _overlay_cache_root(
        self,
        context: ExecutionContext,
        cache_key: str,
    ) -> Path:
        return context.workspace.tools_cache / (
            f"AssetRipper-{self._commit[:12]}-overlay-{cache_key[:20]}"
        )

    @staticmethod
    def overlay_hash(*, content_only: bool = False) -> str:
        overlay_root = Path(__file__).with_name("overlay")
        manifest_path = overlay_root / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise AssetRipperSourceOverlayError(
                "AssetRipper source overlay manifest is unavailable."
            ) from exc
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != ASSETRIPPER_OVERLAY_SCHEMA_VERSION
            or not isinstance(manifest.get("files"), list)
        ):
            raise AssetRipperSourceOverlayError(
                "AssetRipper source overlay manifest is invalid."
            )
        identities = [("schema", str(ASSETRIPPER_OVERLAY_SCHEMA_VERSION))]
        sources: list[Path] = []
        for index, item in enumerate(manifest["files"]):
            if not isinstance(item, dict):
                raise AssetRipperSourceOverlayError(
                    "AssetRipper source overlay entry is invalid."
                )
            if content_only and item.get("content_affecting") is False:
                continue
            path = item.get("path")
            replacement = item.get("replacement")
            if not isinstance(path, str) or not isinstance(replacement, str):
                raise AssetRipperSourceOverlayError(
                    "AssetRipper source overlay entry is incomplete."
                )
            prefix = f"entry-{index:04d}"
            identities.extend(
                (
                    (f"{prefix}-path", path),
                    (f"{prefix}-replacement", replacement),
                )
            )
            sources.append(overlay_root / replacement)
        return calculate_source_fingerprint(
            overlay_root,
            sources,
            identities=identities,
        )

    def _download_to_cache(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        archive = destination.parent / f"AssetRipper-{self._commit}.zip"
        staging = destination.with_name(f".{destination.name}.staging-{uuid4().hex}")
        archive.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        try:
            self._http_client.download_to_file(self._archive_url, str(archive))
            self._cancellation.raise_if_cancelled()
            with ZipFile(archive) as source_archive:
                source_archive.extractall(staging)
            source_root = next(
                (
                    path
                    for path in staging.iterdir()
                    if path.is_dir() and self._is_valid_source(path)
                ),
                None,
            )
            if source_root is None:
                raise AssetRipperSourceError(
                    "Downloaded AssetRipper archive is missing required projects."
                )
            publish_staged_directory(source_root, destination)
        finally:
            archive.unlink(missing_ok=True)
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _is_valid_source(path: Path) -> bool:
        return all(
            (path / "Source" / project / f"{project}.csproj").is_file()
            for project in (
                "AssetRipper.Export.PrimaryContent",
                "AssetRipper.Export.Modules.Models",
                "AssetRipper.Export.Modules.Textures",
            )
        )

    def _cache_root(self, context: ExecutionContext) -> Path:
        return context.workspace.tools_cache / f"AssetRipper-{self._commit[:12]}"
