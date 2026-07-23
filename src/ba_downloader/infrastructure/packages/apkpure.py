from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from ba_downloader.domain.ports.http import HttpClientPort


@dataclass(frozen=True, slots=True)
class ApkPurePackageRelease:
    version: str
    download_url: str


class ApkPureReleaseClient:
    API_URL = "https://api.pureapk.com/m/v3/cms/app_version"
    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        "x-sv": "29",
        "x-abis": "arm64-v8a,armeabi-v7a,armeabi",
        "x-gp": "1",
    }
    VERSION_PATTERN = re.compile(rb"\d+\.\d+\.\d+")
    DOWNLOAD_URL_PATTERN = re.compile(
        rb"https://download\.pureapk\.com/b/XAPK/"
        rb"[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%_-]+"
    )

    def __init__(
        self,
        http_client: HttpClientPort,
        *,
        package_name: str,
        language: str = "en-US",
    ) -> None:
        self.http_client = http_client
        self.package_name = package_name
        self.language = language

    @classmethod
    def parse_releases(
        cls,
        payload: bytes,
        package_name: str,
    ) -> tuple[ApkPurePackageRelease, ...]:
        package_bytes = package_name.encode("ascii")
        package_offsets = [
            match.start() for match in re.finditer(package_bytes, payload)
        ]
        releases: dict[str, ApkPurePackageRelease] = {}

        for index, start in enumerate(package_offsets):
            end = (
                package_offsets[index + 1]
                if index + 1 < len(package_offsets)
                else len(payload)
            )
            record = payload[start:end]
            version_match = cls.VERSION_PATTERN.search(record)
            download_match = cls.DOWNLOAD_URL_PATTERN.search(record)
            if version_match is None or download_match is None:
                continue

            version = version_match.group().decode("ascii")
            releases[version] = ApkPurePackageRelease(
                version=version,
                download_url=download_match.group().decode("ascii"),
            )

        if not releases:
            raise LookupError(
                f"Unable to parse APKPure package releases for '{package_name}'."
            )

        return tuple(
            sorted(
                releases.values(),
                key=lambda item: cls._version_key(item.version),
            )
        )

    def fetch_releases(self) -> tuple[ApkPurePackageRelease, ...]:
        response = self.http_client.request(
            "GET",
            self.API_URL,
            headers=self.HEADERS,
            params={"hl": self.language, "package_name": self.package_name},
        )
        if response.status_code != 200:
            raise LookupError(
                "Failed to fetch APKPure package releases for "
                f"'{self.package_name}': HTTP {response.status_code}."
            )
        return self.parse_releases(response.content, self.package_name)

    def get_latest_release(self) -> ApkPurePackageRelease:
        return self.fetch_releases()[-1]

    def get_release(self, version: str) -> ApkPurePackageRelease:
        for release in self.fetch_releases():
            if release.version == version:
                return release
        raise LookupError(
            f"APKPure does not provide package '{self.package_name}' version {version}."
        )

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in version.split("."))
