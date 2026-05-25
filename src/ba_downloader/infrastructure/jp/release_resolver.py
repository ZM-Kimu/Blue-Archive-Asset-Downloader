from __future__ import annotations

import re
from typing import ClassVar

from ba_downloader.domain.models.asset import ResolvedRelease
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.infrastructure.jp.models import APKPackageInfo


class JPReleaseResolver:
    PUREAPK_VERSION_URL = (
        "https://api.pureapk.com/m/v3/cms/app_version"
        "?hl=en-US&package_name=com.YostarJP.BlueArchive"
    )
    PUREAPK_HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        "x-sv": "29",
        "x-abis": "arm64-v8a,armeabi-v7a,armeabi",
        "x-gp": "1",
    }
    PUREAPK_PACKAGE_PATTERN = re.compile(
        rb"com\.YostarJP\.BlueArchive.*?"
        rb"(\d+\.\d+\.\d+).*?"
        rb"("
        rb"https://download\.pureapk\.com/b/XAPK/"
        rb"[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%_-]+"
        rb")",
        re.S,
    )

    def __init__(self, http_client: HttpClientPort) -> None:
        self.http_client = http_client

    @classmethod
    def parse_package_info(cls, payload: bytes) -> APKPackageInfo:
        matches = cls.PUREAPK_PACKAGE_PATTERN.findall(payload)
        if not matches:
            raise LookupError("Unable to parse latest JP package info from PureAPK.")

        candidates = [
            APKPackageInfo(
                version=version.decode("utf-8"),
                download_url=download_url.decode("ascii"),
            )
            for version, download_url in matches
        ]

        return max(
            candidates,
            key=lambda item: tuple(int(part) for part in item.version.split(".")),
        )

    def get_latest_package_info(self) -> APKPackageInfo:
        payload = self.http_client.request(
            "GET",
            self.PUREAPK_VERSION_URL,
            headers=self.PUREAPK_HEADERS,
        ).content
        return self.parse_package_info(payload)

    def resolve(self, context: RuntimeContext) -> ResolvedRelease:
        package_info = self.get_latest_package_info()
        return ResolvedRelease(
            region=context.region,
            version=package_info.version,
            package_url=package_info.download_url,
        )
