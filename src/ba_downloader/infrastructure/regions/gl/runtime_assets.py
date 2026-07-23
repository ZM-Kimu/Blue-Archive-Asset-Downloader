from __future__ import annotations

from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort
from ba_downloader.infrastructure.packages import (
    PackageArchiveError,
    download_package_file,
    extract_xapk_file,
)
from ba_downloader.infrastructure.regions.gl.release_resolver import GLReleaseResolver

GL_RUNTIME_DIR_NAME = "GL_Runtime"
GL_RUNTIME_VERSION_FILE = ".release-version"


def resolve_gl_runtime_dir(context: RuntimeContext) -> Path:
    return Path(context.temp_dir) / GL_RUNTIME_DIR_NAME


class GLRuntimeAssetPreparer(RuntimeAssetPreparerPort):
    RUNTIME_FILES = (
        "global-metadata.dat",
        "libil2cpp.so",
        "globalgamemanagers",
    )

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger
        self.release_resolver = GLReleaseResolver(http_client)

    def prepare(self, context: RuntimeContext) -> None:
        runtime_dir = resolve_gl_runtime_dir(context)
        if context.version and self._has_runtime_assets(runtime_dir, context.version):
            return

        release = (
            self.release_resolver.resolve_version(context, context.version)
            if context.version
            else self.release_resolver.resolve_latest(context)
        )
        if self._has_runtime_assets(runtime_dir, release.version):
            return

        self.logger.info(
            f"Downloading GL package {release.version} to prepare runtime assets..."
        )
        try:
            package_path = download_package_file(
                self.http_client,
                self.logger,
                release.package_url,
                context.temp_dir,
            )
            extract_xapk_file(
                package_path,
                str(runtime_dir),
                context.temp_dir,
            )
        except PackageArchiveError as exc:
            raise LookupError(
                f"Failed to prepare GL runtime assets from package {release.version}: "
                f"{exc}"
            ) from exc

        missing = self._missing_runtime_files(runtime_dir)
        if missing:
            raise FileNotFoundError(
                f"GL package {release.version} is missing required runtime files: "
                f"{', '.join(missing)}."
            )

        (runtime_dir / GL_RUNTIME_VERSION_FILE).write_text(
            release.version,
            encoding="utf8",
        )

    def _has_runtime_assets(self, runtime_dir: Path, version: str) -> bool:
        marker_path = runtime_dir / GL_RUNTIME_VERSION_FILE
        try:
            marker_version = marker_path.read_text(encoding="utf8").strip()
        except OSError:
            return False
        return marker_version == version and not self._missing_runtime_files(
            runtime_dir
        )

    def _missing_runtime_files(self, runtime_dir: Path) -> list[str]:
        if not runtime_dir.exists():
            return list(self.RUNTIME_FILES)
        return [
            file_name
            for file_name in self.RUNTIME_FILES
            if not any(runtime_dir.rglob(file_name))
        ]
