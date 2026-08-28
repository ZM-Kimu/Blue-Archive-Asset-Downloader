from __future__ import annotations

from ba_downloader.domain.models.asset import ResolvedRelease
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.infrastructure.packages.apkpure import (
    ApkPurePackageRelease,
    ApkPureReleaseClient,
)


class JPReleaseResolver:
    PACKAGE_NAME = "com.YostarJP.BlueArchive"

    def __init__(self, http_client: HttpClientPort) -> None:
        self.http_client = http_client
        self.release_client = ApkPureReleaseClient(
            http_client,
            package_name=self.PACKAGE_NAME,
        )

    @classmethod
    def parse_package_info(cls, payload: bytes) -> ApkPurePackageRelease:
        return ApkPureReleaseClient.parse_releases(payload, cls.PACKAGE_NAME)[-1]

    def get_latest_package_info(self) -> ApkPurePackageRelease:
        return self.release_client.get_latest_release()

    def resolve(self, context: ExecutionContext) -> ResolvedRelease:
        package_info = self.get_latest_package_info()
        return ResolvedRelease(
            region=context.region,
            version=package_info.version,
            package_url=package_info.download_url,
        )
