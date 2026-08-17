from __future__ import annotations

import shutil
from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import ProgressReporterFactoryPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort
from ba_downloader.infrastructure.packages import (
    PackageArchiveError,
    download_package_file,
    extract_xapk_file,
)
from ba_downloader.infrastructure.regions.gl.release_resolver import GLReleaseResolver
from ba_downloader.infrastructure.runtime import RuntimeSnapshotStore


class GLRuntimeAssetPreparer(RuntimeAssetPreparerPort):
    METADATA_SOURCE = Path("assets/bin/Data/Managed/Metadata/global-metadata.dat")
    BINARY_SOURCE = Path("lib/arm64-v8a/libil2cpp.so")
    GLOBALGAMEMANAGERS_SOURCE = Path("assets/bin/Data/globalgamemanagers")
    METADATA_NAME = "global-metadata.dat"
    BINARY_NAME = "libil2cpp.so"
    GLOBALGAMEMANAGERS_NAME = "globalgamemanagers"

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        *,
        snapshot_store: RuntimeSnapshotStore | None = None,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.release_resolver = GLReleaseResolver(http_client)
        self.cancellation = cancellation or NeverCancelled()
        self.snapshot_store = snapshot_store or RuntimeSnapshotStore(
            cancellation=self.cancellation
        )
        self.progress_factory = progress_factory

    def prepare(self, context: RuntimeContext) -> PreparedRuntimeAssets:
        self.cancellation.raise_if_cancelled()
        if context.version:
            prepared = self.snapshot_store.load(context, context.version)
            if prepared is not None:
                return prepared
        release = (
            self.release_resolver.resolve_version(context, context.version)
            if context.version
            else self.release_resolver.resolve_latest(context)
        )
        if prepared := self.snapshot_store.load(context, release.version):
            return prepared

        self.logger.info(
            f"Downloading GL package {release.version} to prepare runtime assets..."
        )
        try:
            with self.snapshot_store.staging_runtime(
                context,
                release.version,
            ) as runtime_dir:
                package_dir = runtime_dir.parent / "Package"
                extracted_dir = package_dir / "Extracted"
                package_path = download_package_file(
                    self.http_client,
                    self.logger,
                    release.package_url,
                    str(package_dir),
                    progress_factory=self.progress_factory,
                    cancellation=self.cancellation,
                )
                extract_xapk_file(
                    package_path,
                    str(extracted_dir),
                    str(package_dir / "Parts"),
                    cancellation=self.cancellation,
                )
                self.cancellation.raise_if_cancelled()
                self._copy_runtime_assets(extracted_dir, runtime_dir)
                self.cancellation.raise_if_cancelled()
                return self.snapshot_store.publish(
                    context,
                    release.version,
                    runtime_dir,
                    binary_name=self.BINARY_NAME,
                    metadata_name=self.METADATA_NAME,
                    globalgamemanagers_name=self.GLOBALGAMEMANAGERS_NAME,
                )
        except PackageArchiveError as exc:
            raise LookupError(
                f"Failed to prepare GL runtime assets from package {release.version}: "
                f"{exc}"
            ) from exc

    @classmethod
    def _copy_runtime_assets(
        cls,
        extracted_dir: Path,
        runtime_dir: Path,
    ) -> None:
        sources = {
            cls.METADATA_NAME: extracted_dir / cls.METADATA_SOURCE,
            cls.BINARY_NAME: extracted_dir / cls.BINARY_SOURCE,
            cls.GLOBALGAMEMANAGERS_NAME: (
                extracted_dir / cls.GLOBALGAMEMANAGERS_SOURCE
            ),
        }
        missing = [name for name, path in sources.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "GL package is missing required runtime files from this extraction: "
                f"{', '.join(missing)}."
            )
        for name, source in sources.items():
            shutil.copy2(source, runtime_dir / name)
