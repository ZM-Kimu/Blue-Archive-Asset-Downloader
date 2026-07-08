from __future__ import annotations

from dataclasses import dataclass
from os import getcwd
from typing import cast

from ba_downloader.application.region_paths import normalize_region_directories
from ba_downloader.domain.models.asset_type_selection import ResourceTypeSelection
from ba_downloader.domain.models.region import Platform, Region
from ba_downloader.domain.models.region_profile import RegionSettingsPolicy
from ba_downloader.domain.models.runtime import RuntimeContext


@dataclass(frozen=True, slots=True)
class AppSettings:
    region: Region
    threads: int = 20
    version: str = ""
    raw_dir: str = "RawData"
    extract_dir: str = "Extracted"
    temp_dir: str = "Temp"
    extract_while_download: bool = False
    resource_type: tuple[str, ...] = ("all",)
    proxy_url: str = ""
    max_retries: int = 5
    search: tuple[str, ...] = ()
    advanced_search: tuple[str, ...] = ()
    work_dir: str = ""
    platform: Platform = "android"
    platform_explicit: bool = False
    sqlcipher_key_hex: str = ""

    def normalized(self, settings_policy: RegionSettingsPolicy) -> AppSettings:
        region = cast(Region, self.region.lower())
        platform = cast(Platform, self.platform.lower())
        directories = normalize_region_directories(
            region=region,
            platform=platform,
            settings_policy=settings_policy,
            raw_dir=self.raw_dir,
            extract_dir=self.extract_dir,
            temp_dir=self.temp_dir,
        )

        resource_type = ResourceTypeSelection.from_values(
            value.lower() for value in self.resource_type
        ).as_strings()

        sqlcipher_key_hex = (
            self.sqlcipher_key_hex.strip()
            if settings_policy.retain_sqlcipher_key_hex
            else ""
        )

        return AppSettings(
            region=region,
            threads=max(1, self.threads),
            version=self.version,
            raw_dir=directories.raw_dir,
            extract_dir=directories.extract_dir,
            temp_dir=directories.temp_dir,
            extract_while_download=self.extract_while_download,
            resource_type=resource_type,
            proxy_url=self.proxy_url,
            max_retries=max(0, self.max_retries),
            search=tuple(self.search),
            advanced_search=tuple(self.advanced_search),
            work_dir=self.work_dir or getcwd(),
            platform=platform,
            platform_explicit=self.platform_explicit,
            sqlcipher_key_hex=sqlcipher_key_hex,
        )

    def to_runtime_context(
        self, settings_policy: RegionSettingsPolicy
    ) -> RuntimeContext:
        normalized = self.normalized(settings_policy)
        return RuntimeContext(
            region=normalized.region,
            threads=normalized.threads,
            version=normalized.version,
            raw_dir=normalized.raw_dir,
            extract_dir=normalized.extract_dir,
            temp_dir=normalized.temp_dir,
            extract_while_download=normalized.extract_while_download,
            resource_type=normalized.resource_type,
            proxy_url=normalized.proxy_url,
            max_retries=normalized.max_retries,
            search=normalized.search,
            advanced_search=normalized.advanced_search,
            work_dir=normalized.work_dir,
            platform=normalized.platform,
            platform_explicit=normalized.platform_explicit,
            sqlcipher_key_hex=normalized.sqlcipher_key_hex,
        )
