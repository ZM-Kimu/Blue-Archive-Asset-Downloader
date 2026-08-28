from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar
from urllib.parse import urlsplit

from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.infrastructure.packages.apkpure_protocol import (
    ApkPurePackageVariant,
    ApkPureProtocolError,
    decode_apkpure_variants,
)


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
    VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")

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
        try:
            variants = decode_apkpure_variants(payload)
        except ApkPureProtocolError as exc:
            raise LookupError(
                f"Unable to parse APKPure package releases for '{package_name}': {exc}"
            ) from exc

        grouped: defaultdict[str, list[ApkPurePackageVariant]] = defaultdict(list)
        for variant in variants:
            if variant.package_name != package_name:
                continue
            if cls.VERSION_PATTERN.fullmatch(variant.version) is None:
                continue
            if variant.package_format.upper() != "XAPK":
                continue
            if not cls._is_valid_xapk_url(variant.download_url):
                continue
            grouped[variant.version].append(variant)

        releases = [
            cls._select_release(version, version_variants, package_name)
            for version, version_variants in grouped.items()
        ]
        if not releases:
            raise LookupError(
                f"Unable to parse APKPure package releases for '{package_name}'."
            )
        return tuple(sorted(releases, key=lambda item: cls._version_key(item.version)))

    @classmethod
    def _select_release(
        cls,
        version: str,
        variants: list[ApkPurePackageVariant],
        package_name: str,
    ) -> ApkPurePackageRelease:
        by_url: dict[str, ApkPurePackageVariant] = {}
        for variant in variants:
            current = by_url.get(variant.download_url)
            if current is None or cls._timestamp_key(
                variant.release_timestamp
            ) > cls._timestamp_key(current.release_timestamp):
                by_url[variant.download_url] = variant

        candidates = list(by_url.values())
        if len(candidates) == 1:
            selected = candidates[0]
        else:
            if any(candidate.release_timestamp is None for candidate in candidates):
                raise LookupError(
                    "Unable to select an APKPure XAPK variant for package "
                    f"'{package_name}' version {version}: release timestamps are "
                    "missing."
                )
            latest_timestamp = max(
                cls._timestamp_key(candidate.release_timestamp)
                for candidate in candidates
            )
            latest = [
                candidate
                for candidate in candidates
                if cls._timestamp_key(candidate.release_timestamp) == latest_timestamp
            ]
            if len(latest) != 1:
                raise LookupError(
                    "Unable to select an APKPure XAPK variant for package "
                    f"'{package_name}' version {version}: multiple variants have the "
                    "same release timestamp."
                )
            selected = latest[0]
        return ApkPurePackageRelease(
            version=selected.version,
            download_url=selected.download_url,
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
        if not response.content:
            raise LookupError(
                f"APKPure returned an empty release response for '{self.package_name}'."
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
    def _is_valid_xapk_url(url: str) -> bool:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "download.pureapk.com"
            and parsed.path.startswith("/b/XAPK/")
        )

    @staticmethod
    def _timestamp_key(timestamp: datetime | None) -> tuple[bool, float]:
        if timestamp is None:
            return False, 0.0
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return True, timestamp.timestamp()

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in version.split("."))
