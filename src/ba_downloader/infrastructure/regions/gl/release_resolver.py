from __future__ import annotations

from ba_downloader.domain.models.asset import ResolvedRelease
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.infrastructure.packages.apkpure import (
    ApkPurePackageRelease,
    ApkPureReleaseClient,
)


class GLReleaseResolver:
    PACKAGE_NAME = "com.nexon.bluearchive"

    def __init__(self, http_client: HttpClientPort) -> None:
        self.release_client = ApkPureReleaseClient(
            http_client,
            package_name=self.PACKAGE_NAME,
        )

    def get_latest_release(self) -> ApkPurePackageRelease:
        return self.release_client.get_latest_release()

    def resolve_latest(self, context: ExecutionContext) -> ResolvedRelease:
        release = self.get_latest_release()
        return ResolvedRelease(
            region=context.region,
            version=release.version,
            package_url=release.download_url,
        )

    def resolve_version(
        self, context: ExecutionContext, version: str
    ) -> ResolvedRelease:
        release = self.release_client.get_release(version)
        return ResolvedRelease(
            region=context.region,
            version=release.version,
            package_url=release.download_url,
        )
